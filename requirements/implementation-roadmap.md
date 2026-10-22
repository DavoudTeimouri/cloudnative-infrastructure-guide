# Deliverable 10 — Implementation Roadmap

Dependency-aware. Each phase lists prerequisites, deliverables, acceptance criteria, risks, effort range, rollback.

Effort is engineering days for one engineer, excluding hardware lead time and network/change-window waits.

## Phase 1 — Requirements and architecture

| | |
|---|---|
| Prerequisites | None |
| Deliverables | `requirements/requirements-and-assumptions.md`, `architecture/*`, `decisions/ADR-0001..0025`, initial `compatibility/version-matrix.md` |
| Acceptance | Every unresolved decision D-01..D-14 has a recorded decision; every version claim has a source URL + check date; failure-domain table reviewed against site topology |
| Risks | Decisions deferred without owner -> rebuild churn later |
| Effort | 8-15 d |
| Rollback | Documentation only; no runtime impact |

## Phase 2 — Offline artifact infrastructure

| | |
|---|---|
| Prerequisites | Phase 1 version baseline; Harbor + Nexus deployed (VM or bare metal); internal CA for TLS |
| Deliverables | `offline-artifacts/artifact-matrix.md` (populated), `staging-and-import.md`, repo/registry config, client configuration runbooks |
| Acceptance | Every artifact in the matrix imports into the internal system; a clean node can install packages, pull images, and deploy a Helm chart with no internet; `skopeo inspect` and `apt-get update` succeed using internal sources only |
| Risks | RK-01 missing transitive dependency -> blocked mid-deploy. Mitigation: staged full dry run on a throwaway cluster before production |
| Effort | 15-25 d |
| Rollback | Repositories are additive; no production dependency until Phase 7 |

## Phase 3 — Foundational infrastructure

| | |
|---|---|
| Prerequisites | Phase 2 registries reachable; network segments allocated |
| Deliverables | DNS (CoreDNS + forwarders), NTP (chrony), PKI (internal CA), identity (Keycloak), load balancer (keepalived/haproxy), SSH/sudo baselines, firewall rules from the matrix |
| Acceptance | DNS resolves forward and reverse; clock skew < 100 ms across nodes; CA cert distributed and trusted; Keycloak issues tokens; LB VIP fails over between nodes; firewall matrix implemented and evidenced by `nmap`/`ss` from allowed and denied hosts |
| Risks | Network misconfiguration is hard to diagnose later; keep a `firewall-rules-generation.md` mapping |
| Effort | 10-18 d |
| Rollback | Standalone services; no cluster dependency |

## Phase 4 — Automation

| | |
|---|---|
| Prerequisites | Phase 3 identity + Vault hosts; GitLab installed |
| Deliverables | Automation Management Server (Ansible + AWX), GitLab runner, Vault (standalone, 3 nodes), inventories, `site-<env>` overlays, CI pipeline templates |
| Acceptance | `ansible all -m ping` from AWX succeeds; a GitLab MR triggers lint -> ansible syntax -> helm lint -> policy -> scan and blocks on failure; Vault seals/unseals with offline shares; AWX job audit log retrievable; Vault backup snapshot created and verified |
| Risks | RK-02 automation SPOF -> second standby node + documented rebuild |
| Effort | 12-20 d |
| Rollback | Ansible/GitLab are not yet load-bearing for runtime workloads |

## Phase 5 — OS preparation

| | |
|---|---|
| Prerequisites | Phase 4 automation + inventories; internal package repos configured |
| Deliverables | `operating-systems/oracle-linux/*`, `operating-systems/ubuntu/*`: repo config, sysctl, security baselines, SSSD/realmd, TLS trust, monitoring/logging agents |
| Acceptance | Provisioned host from bare metal to a hardened, domain-joined, monitored node with one Ansible run; `ansible all -m setup` idempotent (0 changed on second run); SSSD login works; break-glass local account works; `auditd`/journald shipping verified; package install works with no internet |
| Risks | SELinux/AppArmor blocking container runtime; AppArmor profile mismatch on Ubuntu; documented per-distro |
| Effort | 12-20 d |
| Rollback | Re-run playbook; hosts rebuildable from PXE/ISO + Ansible |

## Phase 6 — Storage foundation

| | |
|---|---|
| Prerequisites | Phase 5 hardened OS on storage nodes; storage VLAN; Phase 2 repos for Ceph packages/images |
| Deliverables | `storage/ceph/*` (cephadm path), `storage/rook-ceph/*` (in-cluster path), CRUSH map, capacity worksheet, monitoring, recovery procedures |
| Acceptance | `ceph -s` reports HEALTH_OK; 3 MON quorum survives one MON loss; OSD failure triggers automatic rebalance; RBD + CephFS + RGW (if selected) functional test passes; Ceph exporter feeds Prometheus; capacity worksheet reviewed with real numbers |
| Risks | RK-04 failure domain collapse -> CRUSH host/root mapping; a single-host test pool is not production |
| Effort | 15-25 d |
| Rollback | `ceph orch` decommission; no K8s dependency yet |

## Phase 7 — Kubernetes deployment

| | |
|---|---|
| Prerequisites | Phase 6 storage (or at least node prep), Phase 4 automation, Phase 2 images mirrored |
| Deliverables | `kubespray/` inventories + group vars (version-pinned), `kubernetes/control-plane/*`, offline image override config |
| Acceptance | `kubectl get nodes` shows 3 control-plane Ready; etcd 3/3 healthy; control-plane node loss does not interrupt API access via VIP; a worker can be removed and re-added by Kubespray; no `imagePullBackOff` with internet disabled; `kubectl get pods -A` all Running/Completed |
| Risks | RK-05 Kubespray variable drift -> pin release, keep `inventory/VERSION` file, diff vars on upgrade |
| Effort | 12-20 d |
| Rollback | `kubespray reset` on the node; cluster rebuild from inventory |

## Phase 8 — Cluster services

| | |
|---|---|
| Prerequisites | Phase 7 cluster healthy |
| Deliverables | Cilium CNI + Hubble, MetalLB IPAddressPool + L2Advertisement, NGINX Ingress + Gateway API, Rook-Ceph CSI + StorageClasses, ExternalDNS, cert-manager |
| Acceptance | Pod-to-pod and pod-to-service connectivity across nodes; NetworkPolicy enforced (allowed and denied test); `type: LoadBalancer` service gets a VIP and is reachable; Ingress routes HTTP and TLS terminates correctly; PVC binds and mounts, and expands online; CSI snapshot and restore works |
| Risks | MTU mismatch between overlay and underlay -> measured MTU documented; cert issuance fails offline -> internal CA configured |
| Effort | 15-25 d |
| Rollback | Helm uninstall per component; StorageClass deletion destroys data -> back up first |

## Phase 9 — Management cluster

| | |
|---|---|
| Prerequisites | Phase 7 done; Phase 3 identity; Phase 4 Vault |
| Deliverables | Rancher on dedicated 3-node cluster, cluster registration, Keycloak realm + OIDC clients, Argo CD with SSO, Velero on both clusters, platform dashboards |
| Acceptance | Rancher registers the Application Cluster and can read its nodes; Keycloak login works for Rancher and Argo CD; Argo CD syncs a test app from GitLab; Velero backup completes and a restore into a fresh namespace succeeds; Rancher and Argo CD survive Management Cluster restart |
| Risks | OIDC claim/group mapping mismatch -> groups tested explicitly |
| Effort | 15-25 d |
| Rollback | Uninstall; clusters continue running independently |

## Phase 10 — Secrets and security

| | |
|---|---|
| Prerequisites | Phase 4 Vault; Phase 9 Argo CD; Phase 7 clusters |
| Deliverables | `secrets-management/vault/*` policies, auth methods, PKI, Kubernetes integration; `security/` Gatekeeper constraints, Kyverno policies, Pod Security Standards, Falco ruleset, Trivy/Cosign pipeline integration, CIS baseline scripts |
| Acceptance | App reads a secret through the chosen delivery method and it is not in Git; rotation updates the delivered value within the documented interval; Gatekeeper rejects a privileged pod in audit mode then in enforce mode; Falco raises a test alert; Trivy blocks a CRITICAL image in the pipeline; Cosign verification passes for signed images and fails for unsigned |
| Risks | Policy over-blocking -> deploy in audit mode first, review violations, then enforce |
| Effort | 15-25 d |
| Rollback | Gatekeeper `failurePolicy: Ignore` / uninstall; Vault policies adjustable without restart |

## Phase 11 — Monitoring and logging

| | |
|---|---|
| Prerequisites | Phase 7/8 clusters; Phase 9 Management Cluster |
| Deliverables | `monitoring/` Prometheus Operator stack, Alertmanager routes, Grafana dashboards, recording rules, Thanos (if selected); `logging/` Fluent Bit, Loki/OpenSearch, retention policy, redaction rules |
| Acceptance | Prometheus scrapes node, kube, etcd, CNI, CSI, Ceph, Argo CD, Vault, GitLab, Harbor, GPU targets; a test alert fires end-to-end to the receiver; a pod's logs are searchable within 5 minutes; a deliberately injected secret string is not found in the log backend; dashboards render for each domain |
| Risks | RK-10 log volume -> sampling, retention, cardinality limits |
| Effort | 12-20 d |
| Rollback | Scale down/disable; no data plane impact |

## Phase 12 — GPU and AI infrastructure

| | |
|---|---|
| Prerequisites | Phase 7/8 clusters; Phase 2 GPU artifacts mirrored; GPU node hardware ready |
| Deliverables | `gpu-ai/*` drivers, GPU Operator, device plugin, scheduling labels/taints, sharing matrix applied, inference deployment, model mirror procedure, monitoring dashboards |
| Acceptance | `kubectl get nodes -l nvidia.com/gpu.present=true` shows Ready; a GPU pod runs `nvidia-smi` and sees the correct GPU; MIG partition is visible as a separate resource and memory is hard-isolated (test: allocate beyond the profile and observe failure); time-slicing pod shares the GPU with no memory isolation (documented); vLLM serves a mirrored model and returns a completion; DCGM metrics visible in Prometheus; two concurrent tenants do not OOM each other under MIG |
| Risks | RK-06 version mismatch -> use the driver/toolkit/operator matrix; operator upgrade briefly disrupts GPU pods -> drain window |
| Effort | 15-25 d |
| Rollback | Remove taint, drain node, roll back operator to pinned version |

## Phase 13 — GitOps and CI/CD

| | |
|---|---|
| Prerequisites | Phase 9 Argo CD; Phase 10 policies; Phase 11 dashboards |
| Deliverables | `automation/gitlab-ci/` full pipeline with all 14 stages, protected branches, approval gates, App-of-apps, drift detection job |
| Acceptance | A deliberately broken manifest is rejected at stage 5; a secret in a commit is rejected at stage 7; production job requires 2 approvals and runs from a protected tag; drift job reports a real manual drift without auto-fixing it; post-deploy health check fails the pipeline when a pod is unhealthy |
| Risks | Pipeline over-blocking -> per-stage bypass documented and audited |
| Effort | 12-20 d |
| Rollback | Revert to previous pipeline config; Argo CD self-heal unaffected |

## Phase 14 — Lifecycle and recovery

| | |
|---|---|
| Prerequisites | Phases 7-13 complete |
| Deliverables | `lifecycle/upgrades/*` per component, `lifecycle/backup/*`, `lifecycle/disaster-recovery/*` runbooks, `troubleshooting/*` |
| Acceptance | A K8s minor-version upgrade completes on a staging copy of the cluster with no data loss; a full cluster restore from Velero into a new cluster works; a single-node rebuild from Ansible + Kubespray completes unattended; a complete-environment rebuild procedure is exercised in the offline environment with no internet; RTO/RPO measured against the declared targets |
| Risks | Upgrade path may be one-way for some components -> irreversible steps flagged in each upgrade doc |
| Effort | 20-30 d |
| Rollback | Per-component; some upgrades are irreversible and documented as such |

## Phase 15 — Acceptance and handover

| | |
|---|---|
| Prerequisites | Phase 14 done |
| Deliverables | `tests/acceptance/` executed test suite with evidence, `requirements/acceptance-criteria.md`, runbooks published, known limitations recorded, ownership matrix |
| Acceptance | Every acceptance test in `requirements/acceptance-criteria.md` executed with recorded evidence and a pass/fail verdict; failures either fixed or recorded as accepted risk with owner; handover walkthrough with the operations team completed |
| Risks | Untested claims -> only executed tests are marked passed |
| Effort | 10-18 d |
| Rollback | n/a (documentation and sign-off) |

## Dependency summary

```
1 ─► 2 ─► 3 ─► 4 ─► 5 ─► 6 ─► 7 ─► 8 ─► 9 ─► 10 ─► 11 ─► 12
                    │        │        │    │      │      │
                    └────────┴────────┴────┴──────┴──────┴──► 13 ─► 14 ─► 15
```

Phases 11 and 12 can run in parallel after phase 9.
