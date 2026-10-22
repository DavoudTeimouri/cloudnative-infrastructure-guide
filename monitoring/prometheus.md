# Prometheus and Alertmanager

## A. Purpose and scope

Cluster, node, storage, platform service, and GPU metrics with a single scrape pipeline, plus alert routing.

## B. Architecture

```
kube-prometheus-stack (Prometheus Operator)
  Prometheus  -> scrape targets (node_exporter, kube-state-metrics, exporters)
  Alertmanager -> routes -> receivers (email, webhook, chat)
  Grafana  -> dashboards, datasources
  Thanos sidecar -> object storage (long-term, optional)
```

The stack runs in the Management Cluster, and the Application Cluster's Prometheus is scraped by the Management Prometheus, or each cluster runs its own Prometheus with Thanos for global queries. Decision: each cluster runs its own Prometheus; Thanos provides the global view.

## C. Offline preparation

- Chart: `kube-prometheus-stack` from `harbor.internal/charts/`.
- Images: prometheus, alertmanager, node-exporter, kube-state-metrics, pushgateway, thanos, grafana, and the kube-prometheus-stack adapter images. All in `offline-artifacts/artifact-matrix.md`.
- Grafana dashboards: JSON dashboards are stored in the `obs-monitoring` GitLab project and applied by Argo CD, not baked into a container image. That keeps dashboards versioned and reviewable.

## D. Installation

Argo CD Application (in `mgmt-argocd`):

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: kube-prometheus-stack
  namespace: argocd
spec:
  project: platform
  source:
    repoURL: https://gitlab.internal/platform/obs-monitoring.git
    targetRevision: main
    path: kube-prometheus-stack
    helm:
      valueFiles:
        - values.yaml
  destination:
    server: https://kubernetes.default.svc
    namespace: monitoring
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
```

Key Helm values (`values.yaml`):

```yaml
grafana:
  enabled: true
  adminPassword: ""            # from ExternalSecret, not inline
  dashboards:
    enabled: false             # dashboards applied from Git instead
prometheus:
  prometheusSpec:
    retention: 15d
    retentionSize: 80GB
    serviceMonitorSelectorNilUsesHelmValues: false
    resources:
      requests: {cpu: 500m, memory: 2Gi}
      limits: {cpu: "2", memory: 4Gi}
    storageSpec:
      volumeClaimTemplate:
        spec:
          storageClassName: ceph-block
          accessModes: [ReadWriteOnce]
          resources: {requests: {storage: 200Gi}}
alertmanager:
  alertmanagerSpec:
    storage:
      volumeClaimTemplate:
        spec:
          storageClassName: ceph-block
          accessModes: [ReadWriteOnce]
          resources: {requests: {storage: 20Gi}}
```

`serviceMonitorSelectorNilUsesHelmValues: false` is required so ServiceMonitors in other namespaces are scraped — a common cause of "no metrics" in a multi-cluster setup.

## E. Integration

| Integration | Mechanism |
|---|---|
| Nodes | node-exporter DaemonSet |
| Kubernetes objects | kube-state-metrics |
| Control plane | apiserver + scheduler + controller-manager + etcd endpoints, scraped via the K8s SD |
| Ceph | ceph-exporter (or the Ceph mgr prometheus module) |
| GPU | DCGM exporter ServiceMonitor |
| Vault | Vault telemetry/exporter |
| GitLab, Harbor, Nexus, Keycloak | their own metrics endpoints |
| Alert routing | Alertmanager config in Git, receivers from External Secrets |

## F. Validation

```bash
kubectl -n monitoring get pods
kubectl -n monitoring port-forward svc/kube-prometheus-prometheus 9090:9090
curl -s http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | {job: .labels.job, health: .health}'
```

Expect every job to report `health: "up"`. A job with zero targets is a ServiceMonitor selector problem, not a connectivity problem.

Alert test:

```bash
# Fire a test alert
kubectl -n monitoring exec sts/kube-prometheus-prometheus -c prometheus -- \
  wget -qO- 'http://localhost:9090/api/v1/alerts'
```

## G. Operations

| Task | Procedure |
|---|---|
| Add a dashboard | JSON in the Git repo, Argo CD applies it, Grafana provisioning label selects it |
| Add a rule | `PrometheusRule` in Git; validate with `promtool check rules` in CI |
| Retention change | Helm value + PVC size; retention shortening does not shrink the volume |
| Scale Prometheus | Edit `prometheusSpec.replicas`; the operator shards by target hash |
| Long-term storage | Thanos sidecar + object storage; verify with `thanos query` |

## H. Alert rules — required coverage

| Category | Example alert | Condition |
|---|---|---|
| Availability | APIServerDown | `up{job="apiserver"} == 0` |
| Availability | NodeNotReady | `kube_node_status_condition{condition="Ready",status="true"} == 0` |
| Availability | etcdNoLeader | `etcd_server_has_leader == 0` |
| Availability | TargetDown | `up == 0` for 10m |
| Capacity | NodeMemoryPressure | condition True |
| Capacity | PVCNearFull | `kubelet_volume_stats_available_bytes / kubelet_volume_stats_capacity_bytes < 0.15` |
| Capacity | DiskWillFillIn4Hours | standard node-exporter filesystem rule |
| Capacity | PrometheusTSDBCompactionsFailing | `rate(prometheus_tsdb_compactions_failed_total[3h]) > 0` |
| Storage | CephHealthError | `ceph_health_status == 1` |
| Storage | CephOSDDown | `ceph_osd_up == 0` |
| Storage | CephPoolNearFull | `ceph_pool_bytes_used / ceph_pool_bytes_total > 0.85` |
| Storage | CephPGDegraded | `ceph_pg_degraded > 0` |
| Certificates | CertificateExpiringSoon | `probe_ssl_earliest_cert_expiry - time() < 14*24*3600` |
| Certificates | CertificateExpiringIn7Days | same with 7 days, page |
| Backup | VeleroBackupFailed | `velero_backup_status_backup_success == 0` |
| Backup | NoRecentBackup | `time() - velero_backup_last_success_timestamp > 86400*2` |
| Authentication | VaultAuthFailureSpike | `rate(vault_route_auth_login[5m])` with failure labels |
| Authentication | SSHFailedLogins | from logs (log-based rule) |
| Security | GatekeeperConstraintViolation | `gatekeeper_validation_error_count` increase |
| Security | FalcoAlert | `falco_alerts_total` increase |
| Upgrade risk | NodeReadinessDegraded during maintenance | `kube_node_status_condition` per node |
| GPU | DCGM GPU errors | `DCGM_FI_DEV_GPU_XID_ERRORS` |
| GPU | GPU memory pressure | `DCGM_FI_DEV_FB_USED / DCGM_FI_DEV_FB_FREE + USED > 0.95` |
| GPU | GPU temperature | `DCGM_FI_DEV_GPU_TEMP > 85` |
| AI | Inference OOM | vLLM metric for OOM/retries |
| AI | TTFT regression | vLLM histogram quantile above threshold |

Alerting rules that matter:
- Route by severity: `critical` -> pager, `warning` -> ticket queue, `info` -> dashboard only.
- Inhibit: a `ClusterDown` alert inhibits every node-level alert in that cluster, otherwise one node loss produces hundreds of notifications.
- Group by `cluster`, `namespace`, `job` to keep cardinality low.
- Every alert must link to a runbook in `troubleshooting/`.

## I. Best practices

Mandatory:
- All rules and dashboards live in Git, applied by Argo CD. Never `kubectl apply` a rule by hand.
- Validate rules in CI with `promtool check rules`.
- Inhibit duplicates at the cluster level.
- Prometheus storage on a real PVC with a size limit, not emptyDir.
- Scrape credentials and receiver secrets come from Vault via External Secrets, not from a values file.

Strongly recommended:
- Keep the scrape label set small; `pod`, `namespace`, `container`, `job` are enough. Adding `pod_uid` or request ids destroys performance.
- Record rules for expensive queries so dashboards do not recompute them.
- Run a canary Prometheus in the Management Cluster scraping both clusters as a second line of visibility.
- Alert on "no data" separately from "bad data" — a Prometheus that cannot scrape produces silence, not an alert.
