# Central logging pipeline

## A. Purpose and scope

One pipeline for node logs, Kubernetes control plane, container stdout/stderr, storage, identity, secrets, CI, registry, security, and AI workloads. Redaction is a pipeline property, not a per-application hope.

## B. Architecture

```
nodes: journald / auditd -> Fluent Bit (DaemonSet + host agent) -> Fluent Bit forwarder
                                                       |
                                     +---------------+----------------+
                                     |                                |
                                  Loki                          OpenSearch (optional)
                                     |                                |
                                 Grafana                     OpenSearch Dashboards
```

Fluent Bit is deployed twice per node:
- A DaemonSet for container logs (reads `/var/log/containers` and `/var/log/pods`).
- A host-level agent (DaemonSet with hostPath, or a systemd unit) for journald, auditd, and kern.log.

Both must redact before forwarding. Container logs and node logs are separate streams so that a container cannot spoof a host log entry.

## C. Offline preparation

- Fluent Bit image and Helm chart: `harbor.internal/platform/fluent-bit`.
- Loki chart and image: `harbor.internal/charts/loki`, `harbor.internal/platform/loki`.
- OpenSearch: optional, `harbor.internal/platform/opensearch`.
- Log shipper config lives in Git, applied by Argo CD.

## D. Installation

Loki Helm values (`values.yaml`):

```yaml
loki:
  auth_enabled: false
  server:
    http_listen_port: 3100
  storage:
    filesystem:
      chunks_directory: /loki/chunks
      rules_directory: /loki/rules
  limits_config:
    retention_period: 720h        # 30 days
    ingestion_rate_mb: 16
    ingestion_burst_size_mb: 32
    max_label_names_length: 512
    max_label_value_length: 2048
  ruler:
    storage:
      local:
        directory: /loki/rules
    rule_path: /loki/rules-temp
    ring:
      kvstore:
        store: inmemory
    enable_api: true
  pattern_ingester:
    enabled: true
```

Fluent Bit DaemonSet (key parts):

```yaml
serviceAccount: fluent-bit
hostNetwork: true
securityContext:
  privileged: false
  capabilities:
    drop: [ALL]
    add: [CHOWN]
volumes:
  - name: varlog
    hostPath: {path: /var/log, type: Directory}
  - name: varlibdockercontainers
    hostPath: {path: /var/lib/docker/containers, type: DirectoryOrCreate}
  - name: containers
    hostPath: {path: /var/log/containers, type: DirectoryOrCreate}
  - name: pods
    hostPath: {path: /var/log/pods, type: DirectoryOrCreate}
```

Output configuration (Loki):

```ini
[OUTPUT]
    Name loki
    Match *
    Host loki-gateway.monitoring.svc
    Port 3100
    Labels job=fluent-bit,namespace=${K8S_NAMESPACE_NAME},pod=${K8S_POD_NAME},container=${K8S_CONTAINER_NAME}
    Retry_Limit False
    Line_Format json
```

## E. Redaction — mandatory

Redaction happens in the Fluent Bit filter stage, before any output. Two layers:

1. **Key/value redaction** — a `modify`/`lua` filter that drops or masks keys whose name matches a secret pattern:

```
password, passwd, secret, token, apikey, api_key, authorization, private_key, client_secret, credential, bearer
```

2. **Value pattern redaction** — regex filters for well-known credential shapes:

```
- Bearer [A-Za-z0-9\-._~+/]+=*
- eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}   # JWT
- -----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----
- (AKIA|ASIA)[0-9A-Z]{16}                                            # AWS access key id
- xox[baprs]-[A-Za-z0-9-]{10,}                                       # Slack token
- glpat-[A-Za-z0-9_-]{20,}                                           # GitLab PAT
- sk-[A-Za-z0-9]{20,}                                                # OpenAI-style key
```

Rule: redact by default. A log field that is known to contain a secret must be explicitly allow-listed, and that allow-list entry is reviewed.

Additional controls:
- Never enable Kubernetes audit log level `RequestResponse` — it records request bodies containing secrets. Use `Metadata` level, or `Request` with a scrub policy.
- auditd rules that record file writes must exclude the secret paths (Vault data, TLS keys).
- Log ingestion is over TLS to the backend, with authentication. Without auth, anyone with network access to the backend can read all logs.

## F. Log model

| Stream | Labels | Notes |
|---|---|---|
| Container stdout/stderr | namespace, pod, container, job, cluster | The core stream. Label cardinality is bounded by pod count |
| Node system log | hostname, unit, severity | No pod labels; keeps queries cheap |
| auditd | hostname, event type | Security evidence; separate retention |
| K8s audit | user, verb, resource, namespace, response code | Do not include request bodies |
| Ceph | hostname, daemon type | From the Ceph hosts, not the container stream |
| GitLab CI | project, pipeline, job, runner | From the GitLab application logs, not the container stream |

Retention: container logs 30 days, node logs 30 days, audit logs 1 year, CI logs 90 days. Apply per-stream retention in the backend, not per-collector.

## G. Storage sizing

Estimate before deploying:

```
daily_volume = avg_lines_per_sec * avg_line_bytes * 86400
compressed_volume ≈ daily_volume * 0.25 (JSON/labels compress well, but index overhead adds back)
retention_storage = compressed_volume * retention_days * 1.3 (index + WAL overhead)
```

Worked example: 2000 lines/s, 500 bytes/line -> 86 GB/day uncompressed -> roughly 22-30 GB/day with compression and index -> 30 days retention ≈ 0.9 TB. Verify against the actual backend after one week of real traffic and correct the estimate.

Guardrails:
- Cap ingestion rate per tenant to protect the backend (Loki `ingestion_rate_mb`).
- Alert when the backend's disk crosses 70% and 85%.
- Do not index full log content in Loki. Use OpenSearch for content search.

## H. Validation

```bash
# Log reaches the backend
kubectl -n logging exec ds/fluent-bit -- sh -c 'echo test | cat'
kubectl -n logging port-forward svc/loki 3100:3100
curl -s "http://localhost:3100/loki/api/v1/query_range?query={namespace=\"default\"}" | jq '.data.result | length'

# Redaction works
kubectl exec deploy/test-app -- sh -c 'echo "password=supersecret123"'
# Then search for "supersecret123" in the backend -> must return no results
```

The redaction test is a mandatory acceptance test (`requirements/validation-strategy.md`, family C/F).

## I. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| No logs | Fluent Bit DaemonSet not running, or the host path is not mounted | `kubectl -n logging logs ds/fluent-bit`; check hostPath types |
| Logs for some pods only | Label filter mismatch, or a container writes to a file instead of stdout | Check the collector's tail pattern |
| Backend 429 | Ingestion rate exceeded | Raise the limit, or reduce the stream |
| Loki OOM | Excessive label cardinality or unbounded query | Check `max_label_names_length`; reduce labels |
| Secrets visible in logs | Redaction filter not applied to that stream | Add the filter, purge affected data, rotate the exposed credential |

## J. Best practices

Mandatory:
- Redaction before forwarding, with a test that proves it.
- TLS plus authentication between the collector and the backend.
- Audit logs retained separately and for longer than application logs.
- No `RequestResponse` audit level.

Strongly recommended:
- Keep the label set small and fixed per stream.
- Use an OpenSearch sidecar only where content search is a hard requirement.
- Ship audit logs off-host as soon as they are generated, so a compromised node cannot delete its own evidence.
- Alert on log ingestion rate, not only on backend health — a silent collector looks identical to a quiet cluster.
