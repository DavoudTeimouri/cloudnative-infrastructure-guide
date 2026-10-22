# Deliverable 12 — Validation Strategy

Seven test families. Every test states: procedure, expected result, evidence artifact, pass/fail criterion, execution context.

Status column is authoritative: a test is PASSED only if it was executed and evidence is stored. Not-run tests read NOT RUN.

## A. Compatibility and version validation

| ID | Test | Procedure | Expected | Evidence | Pass/fail | Status |
|---|---|---|---|---|---|---|
| A-01 | Kubespray version supports target K8s | Read the pinned Kubespray release README supported-versions table | Target K8s version listed | URL + check date in version matrix | Listed = pass | NOT RUN |
| A-02 | Rook-Ceph supports target Ceph version | Rook release notes / docs Ceph compatibility page | Target Ceph version listed | URL + check date | Listed = pass | NOT RUN |
| A-03 | Helm chart appVersion matches deployed app | `helm show chart <chart>` vs deployed version | Match or documented deviation | CLI output | Match = pass | NOT RUN |
| A-04 | CRD schema compatibility | Apply CRDs in staging, deploy app, check for conversion errors | No errors | kubectl output | No errors = pass | NOT RUN |
| A-05 | NVIDIA driver -> CUDA -> toolkit -> operator chain | Consult NVIDIA support matrix for the pinned versions | Every link supported | URL + check date | All supported = pass | NOT RUN |
| A-06 | Vault integration compatibility with Argo CD / ESO | Official integration docs for pinned versions | Documented support | URL + check date | Documented = pass | NOT RUN |
| A-07 | OS release is supported by Kubespray | Kubespray supported OS list | OS listed | URL + check date | Listed = pass | NOT RUN |
| A-08 | GitLab runner version supports GitLab version | GitLab docs | Match | URL + check date | Match = pass | NOT RUN |

## B. Connectivity and network validation

| ID | Test | Procedure | Expected | Evidence | Pass/fail | Status |
|---|---|---|---|---|---|---|
| B-01 | DNS resolution | `dig +short <svc>.<ns>.svc.cluster.local` | Correct IP | dig output | IP = pass | NOT RUN |
| B-02 | Reverse DNS | `dig -x <ip>` | Correct hostname | dig output | Name = pass | NOT RUN |
| B-03 | Time sync | `chronyc tracking` on all nodes | Skew < 100 ms | output from all nodes | < 100 ms = pass | NOT RUN |
| B-04 | Control-plane reachability | `curl -k https://<apiserver>:6443/healthz` | `ok` | curl output | ok = pass | NOT RUN |
| B-05 | etcd health | `etcdctl endpoint health --cluster` | All healthy | etcdctl output | All healthy = pass | NOT RUN |
| B-06 | Service-to-service | `kubectl run nettest --image=... --rm -it -- nslookup <svc>` | Resolves + connects | command output | Success = pass | NOT RUN |
| B-07 | Cross-node pod traffic | Pod A -> pod B on a different node | Connectivity | output | Success = pass | NOT RUN |
| B-08 | MTU | `ping -M do -s 1472 <peer>` from each node | No fragmentation | ping output | Success = pass | NOT RUN |
| B-09 | NetworkPolicy enforced | Deny-all policy + allowed exception | Denied flow fails, allowed flow succeeds | curl exit codes | Both as expected = pass | NOT RUN |
| B-10 | Firewall matrix fidelity | From an allowed and a denied source, probe every matrix port | Allowed open, denied filtered | nmap output per host | Matches matrix = pass | NOT RUN |
| B-11 | External egress blocked | `curl -I https://example.com` from a pod | Fails/blocked | curl output | No connection = pass | NOT RUN |
| B-12 | Internal registry only | `docker pull`/`crictl pull` of an upstream image | Fails; internal mirror succeeds | command output | External fails, internal works = pass | NOT RUN |

## C. Security validation

| ID | Test | Procedure | Expected | Evidence | Pass/fail | Status |
|---|---|---|---|---|---|---|
| C-01 | Pod Security Standards enforced | Deploy a privileged pod in the enforced namespace | Admission denied | kubectl output | Denied = pass | NOT RUN |
| C-02 | Gatekeeper constraint | Deploy a pod with hostPath | Denied (enforce mode) | kubectl output | Denied = pass | NOT RUN |
| C-03 | Kyverno policy | Deploy a disallowed image tag | Denied | kubectl output | Denied = pass | NOT RUN |
| C-04 | Falco detection | Trigger a test event (write to /etc, exec in container) | Alert raised | Falco alert + Alertmanager record | Alert = pass | NOT RUN |
| C-05 | Image scan blocks CRITICAL | Push a test image with a known CVE | Pipeline fails | pipeline log | Fail = pass | NOT RUN |
| C-06 | Cosign verification | Verify a signed and an unsigned image | Signed passes, unsigned fails | cosign output | Both as expected = pass | NOT RUN |
| C-07 | SBOM generated | `syft` on built image | Valid SBOM | SBOM file + schema validation | Valid = pass | NOT RUN |
| C-08 | No secrets in Git | `gitleaks`/`trufflehog` over the full history | No findings | scan report | No findings = pass | NOT RUN |
| C-09 | No secrets in images | Trivy secret scanner on built images | No findings | scan report | No findings = pass | NOT RUN |
| C-10 | TLS everywhere | Scan all DMZ VIPs with `nmap --script ssl-cert` or `testssl.sh` | Valid cert, no weak ciphers | scan report | Clean = pass | NOT RUN |
| C-11 | Break-glass access | Disable IdP, SSH as break-glass user, escalate with sudo | Works | session log | Success = pass | NOT RUN |
| C-12 | Vault sealed state protected | `vault status` on a sealed node | `sealed: true`, no unseal possible without keys | output | Sealed = pass | NOT RUN |
| C-13 | Audit log integrity | Verify audit device has entries for admin reads | Entries present, values not exposed | audit log excerpt | Present + masked = pass | NOT RUN |
| C-14 | Host baseline | Run OpenSCAP CIS profile | No HIGH failures | scan report | No HIGH = pass | NOT RUN |

## D. Availability and recovery validation

| ID | Test | Procedure | Expected | Evidence | Pass/fail | Status |
|---|---|---|---|---|---|---|
| D-01 | Control-plane node loss | Power off one control-plane | API still serves via VIP | API output during failure | Available = pass | NOT RUN |
| D-02 | etcd member loss | Stop one etcd member | Quorum maintained, cluster healthy | `ceph`/`etcdctl` output | Healthy = pass | NOT RUN |
| D-03 | Worker loss | Drain a node with a running workload | Pod rescheduled, service stays up | pod events | Rescheduled + no errors = pass | NOT RUN |
| D-04 | Ceph OSD loss | Remove an OSD | Pool rebalances, IO continues | `ceph -s` over time | HEALTH_OK eventually = pass | NOT RUN |
| D-05 | Ceph MON loss | Stop 1 of 3 MONs | Quorum retained | `ceph -s` | HEALTH_OK = pass | NOT RUN |
| D-06 | Vault node loss | Stop the active Vault node | Failover within the documented window | `vault status` | Leader elected = pass | NOT RUN |
| D-07 | Management Cluster loss | Stop the Management Cluster | Application workloads unaffected; deployments blocked | workload + Argo CD output | Workloads up, deploys blocked = pass | NOT RUN |
| D-08 | IdP outage | Stop Keycloak | Existing sessions continue; new logins fail | auth test output | As expected = pass | NOT RUN |
| D-09 | Registry outage | Stop Harbor | Running workloads fine; new pulls fail | pull test output | As expected = pass | NOT RUN |
| D-10 | GitLab outage | Stop GitLab | Workloads fine; CI blocked | pipeline attempt | As expected = pass | NOT RUN |
| D-11 | Automation server loss | Stop the automation server | Workloads fine; changes blocked | ansible attempt | As expected = pass | NOT RUN |
| D-12 | Node rebuild | Rebuild a node from OS + Ansible + Kubespray | Node rejoins Ready, workloads rescheduled | node status + events | Ready = pass | NOT RUN |

## E. Storage validation

| ID | Test | Procedure | Expected | Evidence | Pass/fail | Status |
|---|---|---|---|---|---|---|
| E-01 | Dynamic provisioning | Apply a PVC, mount it, write/read | Data persists across pod restart | test output | Pass = pass | NOT RUN |
| E-02 | Online expansion | Expand the PVC, write more data | Expansion succeeds, data intact | test output | Pass = pass | NOT RUN |
| E-03 | Snapshot and restore | Snapshot a PVC, restore to a new PVC, compare checksums | Content identical | checksum comparison | Identical = pass | NOT RUN |
| E-04 | Access modes | Mount RWO and RWX volumes | Correct behavior per mode | test output | As expected = pass | NOT RUN |
| E-05 | CSI controller failover | Kill the CSI controller pod | New PVC provisioning still works | events | Works = pass | NOT RUN |
| E-06 | S3 API (if RGW) | `aws s3` put/get/list against RGW | Works | CLI output | Pass = pass | NOT RUN |
| E-07 | Ceph health sustained | `ceph -s` at 5-minute intervals for 24 h | HEALTH_OK throughout | time series | No HEALTH_WARN = pass | NOT RUN |
| E-08 | Replica/erasure overhead verified | `ceph osd df` + PG mapping | Actual overhead matches the worksheet | output vs worksheet | Matches = pass | NOT RUN |

## F. Offline operation validation

| ID | Test | Procedure | Expected | Evidence | Pass/fail | Status |
|---|---|---|---|---|---|---|
| F-01 | Offline package install | On a network-isolated host: `apt-get install` / `dnf install` from internal repo | Installs correct version | command output | Success = pass | NOT RUN |
| F-02 | Offline image pull | `crictl pull harbor.internal/...` | Image pulled | command output | Success = pass | NOT RUN |
| F-03 | Offline Helm deploy | `helm install` with chart from internal repo | Deployed, pods Ready | helm output | Ready = pass | NOT RUN |
| F-04 | Offline GitOps sync | Argo CD syncs an app from internal GitLab | Synced Healthy | argocd output | Healthy = pass | NOT RUN |
| F-05 | Offline Ansible run | `ansible-playbook` with all deps from internal Nexus | Runs clean | playbook output | Success = pass | NOT RUN |
| F-06 | No external calls | Capture traffic on the isolated segment during a full deploy | Zero outbound calls to public IPs | packet capture summary | Zero = pass | NOT RUN |
| F-07 | Full environment rebuild | Rebuild the entire platform in the isolated environment | Recreated to acceptance state | runbook log + test results | Pass = pass | NOT RUN |
| F-08 | Certificate trust in offline | Service call to a TLS endpoint with the internal CA | Validated, no warning | command output | Success = pass | NOT RUN |

## G. Performance and GPU validation

| ID | Test | Procedure | Expected | Evidence | Pass/fail | Status |
|---|---|---|---|---|---|---|
| G-01 | etcd latency | `etcdctl endpoint status` under load | p99 within the declared budget | output | Within budget = pass | NOT RUN |
| G-02 | Ceph IOPS/throughput | `fio` against a RBD pool | Matches the worksheet | fio output | Within 20% = pass | NOT RUN |
| G-03 | API server latency | `kube-burner` or `hey` against the API | Within the declared budget | load test report | Within budget = pass | NOT RUN |
| G-04 | GPU visible in pod | `nvidia-smi` in a GPU pod | Correct GPU and driver | output | Correct = pass | NOT RUN |
| G-05 | GPU isolation (MIG) | Allocate beyond the MIG memory profile | Allocation/OOM failure, not silent use of another tenant's memory | test output | Hard limit enforced = pass | NOT RUN |
| G-06 | Time-slicing shared (documented) | Two pods share one GPU | Both run; no memory isolation | test output + note | Documented behavior = pass | NOT RUN |
| G-07 | LLM inference functional | vLLM serves a mirrored model, returns a completion | Valid response | response + metrics | Pass = pass | NOT RUN |
| G-08 | Inference throughput | Load test with recorded concurrency | Documented tokens/s, TTFT, ITL | load report | Within 20% of baseline = pass | NOT RUN |
| G-09 | DCGM metrics | `curl http://gpu-node:9400/metrics` + Prometheus target up | Metrics present, target UP | output | Present = pass | NOT RUN |
| G-10 | Multi-GPU model sharding | vLLM tensor parallel across 2 GPUs | Model loads, serves | vLLM log | Works = pass | NOT RUN |
| G-11 | GPU node drain | Drain a GPU node with running inference | Pods rescheduled or terminated cleanly | events | Clean = pass | NOT RUN |

## Evidence storage

```
tests/acceptance/<test-id>/
  procedure.md     # exact commands used
  result.md        # observed output, timestamped
  verdict.md       # PASS/FAIL, tester, date
```

## Execution rules

1. A test is PASSED only when executed and evidence exists. Never mark a test passed from documentation.
2. Run destructive tests (node loss, cluster loss) only in staging or in an approved maintenance window, with the operator present.
3. Record the exact version of every tool in the evidence.
4. Re-run the whole suite after any upgrade that touches a tested component.
