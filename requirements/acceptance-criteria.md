# Mandatory Acceptance Criteria

The platform is production-ready only when the relevant tests pass. A test is PASSED only if it was executed and evidence is stored in `tests/acceptance/<test-id>/`. Never mark a test passed from documentation.

## Result table

| ID | Test | Phase | Owner | Status | Evidence | Date | Tester |
|---|---|---|---|---|---|---|---|
| F-01 | Offline package installation | 2 | DevOps | NOT RUN | | | |
| F-02 | Offline container image pulls | 2 | DevOps | NOT RUN | | | |
| F-03 | Offline Helm chart deployment | 2 | Platform | NOT RUN | | | |
| A-01 | Kubespray supports the pinned Kubernetes version | 7 | Platform | NOT RUN | | | |
| A-02 | Rook supports the pinned Ceph version | 6 | Storage | NOT RUN | | | |
| A-05 | NVIDIA driver/CUDA/toolkit/operator chain supported | 12 | AI | NOT RUN | | | |
| B-01 | DNS resolution (forward and reverse) | 3 | Network | NOT RUN | | | |
| B-03 | Time sync skew < 100 ms on all nodes | 3 | Ops | NOT RUN | | | |
| B-04 | Control-plane API availability | 7 | Platform | NOT RUN | | | |
| B-05 | etcd quorum and health | 7 | Platform | NOT RUN | | | |
| B-09 | Network policy enforcement (allowed and denied) | 8 | SecOps | NOT RUN | | | |
| B-10 | Firewall matrix fidelity | 3 | SecOps | NOT RUN | | | |
| B-11 | External egress blocked | 3 | SecOps | NOT RUN | | | |
| C-01 | Pod Security Standards enforced | 10 | SecOps | NOT RUN | | | |
| C-02 | Gatekeeper constraint denies a privileged pod | 10 | SecOps | NOT RUN | | | |
| C-04 | Falco raises a test alert | 10 | SecOps | NOT RUN | | | |
| C-05 | Trivy blocks a CRITICAL image in CI | 13 | SecOps | NOT RUN | | | |
| C-06 | Cosign verification passes for signed, fails for unsigned | 10 | SecOps | NOT RUN | | | |
| C-08 | No secrets in Git history | 13 | SecOps | NOT RUN | | | |
| C-11 | Break-glass local access with the IdP down | 10 | SecOps | NOT RUN | | | |
| C-14 | Host baseline: no HIGH CIS findings | 10 | SecOps | NOT RUN | | | |
| D-01 | Control-plane node loss, API stays available | 14 | SRE | NOT RUN | | | |
| D-02 | etcd member loss, quorum maintained | 14 | SRE | NOT RUN | | | |
| D-03 | Worker loss, workload rescheduled | 14 | SRE | NOT RUN | | | |
| D-04 | Ceph OSD loss, pool rebalances | 14 | Storage | NOT RUN | | | |
| D-06 | Vault node loss, failover | 14 | SecOps | NOT RUN | | | |
| D-07 | Management Cluster loss, workloads unaffected | 14 | SRE | NOT RUN | | | |
| D-12 | Node rebuild from OS + Ansible + Kubespray | 14 | Platform | NOT RUN | | | |
| E-01 | Dynamic provisioning, data persists across restart | 8 | Storage | NOT RUN | | | |
| E-02 | Online PVC expansion | 8 | Storage | NOT RUN | | | |
| E-03 | Snapshot and restore with matching checksums | 9 | Storage | NOT RUN | | | |
| S-01 | Secret delivered to a workload, not present in Git | 10 | SecOps | NOT RUN | | | |
| S-02 | Secret rotation reaches the workload | 10 | SecOps | NOT RUN | | | |
| S-03 | Certificate auto-renewal | 10 | SecOps | NOT RUN | | | |
| P-01 | GitLab pipeline validates and blocks on failure | 13 | DevOps | NOT RUN | | | |
| P-02 | Ansible idempotency: second run reports 0 changed | 13 | DevOps | NOT RUN | | | |
| P-03 | Argo CD syncs an application from Git | 9 | Platform | NOT RUN | | | |
| P-04 | Argo CD drift detection reports drift | 13 | Platform | NOT RUN | | | |
| M-01 | Prometheus alert delivered end-to-end | 11 | SRE | NOT RUN | | | |
| M-02 | Log ingestion within 5 minutes | 11 | SRE | NOT RUN | | | |
| M-03 | Injected secret absent from the log backend | 11 | SRE | NOT RUN | | | |
| G-01 | GPU scheduling, pod sees the correct GPU | 12 | AI | NOT RUN | | | |
| G-02 | MIG hard memory isolation | 12 | AI | NOT RUN | | | |
| G-03 | LLM inference functional and benchmarked | 12 | AI | NOT RUN | | | |
| G-04 | DCGM metrics present and scraped | 12 | AI | NOT RUN | | | |
| B-12 | Cluster upgrade completes without data loss | 14 | Platform | NOT RUN | | | |
| B-13 | Full cluster restore from backup | 14 | SRE | NOT RUN | | | |
| B-14 | Full environment rebuild with no internet | 14 | Platform | NOT RUN | | | |

## Test definitions

Each test below states: procedure, expected result, evidence, pass/fail criterion, and the execution context. The full procedure list lives in `requirements/validation-strategy.md`; this section is the acceptance gate.

### Offline operation (phase 2, 8, 9)

| Test | Procedure | Expected | Evidence | Pass/fail | Context |
|---|---|---|---|---|---|
| F-01 | On a host with all external routes removed, `apt-get install <pkg>` / `dnf install <pkg>` | Package installs at the mirrored version | Command output plus `dnf list installed` | Exit 0 and correct version = pass | Linux host, isolated segment |
| F-02 | `crictl pull harbor.internal/<repo>:<tag>` with no external route | Image pulled and unpacked | Command output plus `crictl images` | Exit 0 = pass | Kubernetes node |
| F-03 | `helm install <chart> --set image.repository=harbor.internal/...` | Deployed, pods Ready | helm output plus pod status | All Ready = pass | Cluster |
| B-14 | Run the full rebuild order in `lifecycle/backup/backup-and-dr.md` section G in the isolated environment | The platform is recreated and passes the tests in this table | Runbook log plus test results | All referenced tests pass = pass | Full environment |

### Availability and recovery (phase 14)

| Test | Procedure | Expected | Evidence | Pass/fail | Context |
|---|---|---|---|---|---|
| D-01 | Power off one control-plane node; call the API through the VIP continuously | API responds throughout | Request log during the failure | No failed requests = pass | Staging or approved window |
| D-02 | Stop one etcd member | Quorum maintained, `etcdctl endpoint health` all healthy | etcdctl output | All healthy = pass | Staging |
| D-03 | Drain a node running a replicated deployment | Pod rescheduled, service continues to serve | kubectl events plus a continuous request log | Zero failed requests = pass | Staging |
| D-04 | Remove one OSD | Pool rebalances, `ceph -s` returns to HEALTH_OK | `ceph -s` time series | HEALTH_OK within the rebalance window = pass | Staging |
| D-06 | Stop the active Vault node | A new leader is elected within the documented window | `vault status` | Leader elected = pass | Staging |
| D-07 | Stop the Management Cluster | Application workloads keep serving; new deploys are blocked | Request log plus an Argo CD sync attempt | Workloads serve, sync blocked = pass | Staging |

### Secrets and security (phase 10)

| Test | Procedure | Expected | Evidence | Pass/fail | Context |
|---|---|---|---|---|---|
| S-01 | Deploy a workload that reads a secret via the chosen delivery method; grep the Git history | The workload gets the value; Git contains no value | Pod log plus a `git log -p` search | Value present at runtime, absent from Git = pass | Cluster plus GitLab |
| S-02 | Rotate the secret in Vault; wait for the renewal interval | The workload sees the new value without a redeploy | Pod log before and after | New value observed = pass | Cluster |
| S-03 | Reduce a certificate's lifetime in the CA policy; wait for the renewal cycle | The certificate is re-issued with the new validity | cert-manager logs plus `openssl x509` | New certificate issued = pass | Cluster |
| C-11 | Stop Keycloak; log in with the emergency account; run `sudo -n true` | The login succeeds and sudo works | Session log | Success = pass | Any node |
| C-05 | Push an image with a known CRITICAL CVE | The pipeline fails at the scan stage | Pipeline log | Pipeline failed = pass | GitLab CI |

### GitOps and pipeline (phase 13)

| Test | Procedure | Expected | Evidence | Pass/fail | Context |
|---|---|---|---|---|---|
| P-01 | Open an MR with an invalid manifest | Stage 5 fails, the job is blocked | Pipeline log | Failure at stage 5 = pass | GitLab |
| P-02 | Run the Ansible baseline twice | The second run reports 0 changed | Playbook recap | 0 changed = pass | Automation server |
| P-03 | Merge a change to an application repo | Argo CD syncs and the app becomes Healthy | `argocd app get` | Synced and Healthy = pass | Cluster |
| P-04 | Manually change a live resource | The drift job reports it | Drift report | Drift reported = pass | GitLab scheduled job |

### GPU and AI (phase 12)

| Test | Procedure | Expected | Evidence | Pass/fail | Context |
|---|---|---|---|---|---|
| G-01 | Schedule a pod requesting `nvidia.com/gpu: 1`; run `nvidia-smi` | The pod runs and sees exactly one GPU | Pod log | Correct GPU = pass | GPU cluster |
| G-02 | On a MIG-configured GPU, request more memory than the profile allows | The allocation fails; the workload cannot touch memory outside its slice | kubectl events plus the failing pod log | Hard limit enforced = pass | GPU cluster |
| G-03 | Start vLLM with a mirrored model; send a completion request; run the benchmark | A valid completion; the benchmark reports throughput, TTFT, ITL | Response plus the benchmark report | Valid response = pass | GPU cluster |
| G-04 | `curl http://<gpu-node>:9400/metrics`; check the Prometheus target | Metrics present; the target is UP | curl output plus the target status | Present and UP = pass | GPU node |

### Observability (phase 11)

| Test | Procedure | Expected | Evidence | Pass/fail | Context |
|---|---|---|---|---|---|
| M-01 | Trigger a test alert (for example by stopping an exporter) | The notification arrives at the receiver | Receiver inbox plus the Alertmanager record | Notification received = pass | Management cluster |
| M-02 | Print a timestamped line in a pod; search for it in the backend | The line is searchable | Backend query result | Found within 5 minutes = pass | Cluster |
| M-03 | Print a string that looks like a credential | The string is not retrievable from the backend | Backend query returning nothing | Absent = pass | Cluster |

### Backup and restore (phase 14)

| Test | Procedure | Expected | Evidence | Pass/fail | Context |
|---|---|---|---|---|---|
| E-03 | Snapshot a PVC, restore to a new PVC, compare file checksums | The checksums match | Checksum comparison | Identical = pass | Cluster |
| B-13 | Restore the whole cluster from a Velero backup into a new cluster | The workloads return with their data | Velero restore log plus application checks | Restored = pass | Staging |
| B-12 | Upgrade the cluster one minor version | The upgrade completes and the applications still work | Upgrade log plus post-check results | No data loss = pass | Staging |

## Gate

Production go-live requires:
1. Every test in the relevant phase marked PASSED with evidence.
2. Every failure either fixed, or recorded as an accepted risk with a named owner and a review date in `requirements/requirements-and-assumptions.md`.
3. The offline set (F-01, F-02, F-03, B-11, B-14) passed in the production environment, not only in staging.
4. A handover walkthrough completed with the operations team.
