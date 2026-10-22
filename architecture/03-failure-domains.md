# Failure Domain Analysis

| Scenario | Running workloads | Blocked operations | Recovery path |
|---|---|---|---|
| Single worker node loss | Unaffected (rescheduled if capacity) | Deploys targeting that node | Replace node + uncordon |
| Single control-plane loss | Unaffected | None (HA apiserver) | Replace via Kubespray join |
| etcd quorum loss (2 of 3 down) | Pods keep running; no API | All API ops, all reconciliation | Restore member; etcd snapshot restore last resort |
| etcd quorum loss (1 of 3 down) | Unaffected | None | Replace member |
| Ceph OSD loss | Unaffected; IO degraded briefly | None | OSD auto-rebalance, backfill |
| Ceph MON quorum loss | Storage IO degraded | New pools/PGs blocked | Restore 2 of 3 MONs |
| Management Cluster down | Unaffected | Argo CD sync, Rancher UI, new deploys | Restore from GitLab + Velero |
| Rancher down | Unaffected | Rancher UI, Fleet gitops | Standalone kubectl, restore Rancher |
| Keycloak down | Existing sessions continue (token lifetime) | New logins, OIDC flows | Restore IdP; break-glass local accounts |
| Vault down | Workloads keep running | Secret refresh, new issuance, rotation | Restore snapshot + unseal keys |
| GitLab down | Unaffected | New commits, CI runs | Restore repo + LFS/registry backups |
| Harbor down | Unaffected if images cached | New image pulls | Restore from Nexus/backup |
| Automation server down | Unaffected | Ansible, AWX, CI | Rebuild from GitLab (runbook) |
| Identity + Vault both down | Workloads unaffected | Admin login, secret rotation | Break-glass local sudo + offline unseal material |
| GPU worker loss | Other GPU pods continue | Inference capacity reduced | Replace node, re-apply driver + GPU Operator |

## Anti-circularity rules

1. Vault must not depend on Management Cluster availability for unseal (offline/HSM unseal).
2. GitLab must not depend on the cluster it deploys (dedicated infra, backed up externally).
3. Argo CD must not be the only path to restore the cluster it manages — Kubespray + GitLab + Ansible remain the recovery path.
4. Break-glass access exists on every node: local account + sudo, keys held offline.
