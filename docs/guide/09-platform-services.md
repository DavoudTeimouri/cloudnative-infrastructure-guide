# 09. Platform services

**Purpose:** Make the platform observable and operated — monitoring (Prometheus/Alertmanager), log
shipping, GitOps (Argo CD), and platform add-ons (Harbor, Nexus, GitLab, Velero).

## Prerequisites
- Step 06 complete: Argo CD and Rancher running.
- Step 08 complete: edge reachable.

## Steps

### 09.1 Monitoring
Deploy Prometheus + Alertmanager in the management cluster. Scrape:
- Kubernetes components (kubelet, API, scheduler, controller-manager)
- Ceph MGR endpoint `:9283`
- Node exporters on every host
- Edge LB health

Source: `monitoring/prometheus.md`

### 09.2 Logging
Ship logs from nodes and clusters to a central store (Loki or Elasticsearch). Ship from the operation
server and each cluster via a DaemonSet.

Source: `monitoring/prometheus.md` (§logging)

### 09.3 GitOps
Ensure Argo CD syncs every platform component from `config/` in the internal GitLab. Use the
`platform` GitLab project for platform manifests, `apps` for workloads.

Source: `management-cluster/argocd/argocd.md`

### 09.4 Platform add-ons
| Add-on | Purpose |
|---|---|
| Harbor | Container image registry + vulnerability scanning |
| Nexus | Artifact cache (Helm, PyPI, npm, Maven) |
| GitLab | Source control + pipelines |
| Velero | Cluster backup/restore (to Ceph) |

Source: `addons/platform-addons.md`

## Validation
- [ ] Prometheus scrapes all targets; no `DOWN` targets for > 5 min.
- [ ] Alertmanager routes critical alerts (node down, disk full, etcd quorum lost).
- [ ] Logs searchable from a central store.
- [ ] Argo CD auto-syncs platform manifests from internal GitLab.
- [ ] Velero backup job succeeds against a Ceph-backed repository.

## Navigation
**[← Prev · 08. Traffic edge](./08-traffic-edge.md)** | **[Next → 10. Backup & upgrade](./10-backup-upgrade.md)**
