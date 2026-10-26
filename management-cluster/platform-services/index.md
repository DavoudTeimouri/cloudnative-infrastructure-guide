# Platform services

**Purpose:** Make the platform observable and operated — monitoring, logging, GitOps, and platform add-ons (Harbor, Nexus, GitLab, Velero).

## Components

| Component | Purpose | Document |
|---|---|---|
| Prometheus + Alertmanager | Metrics collection and alerting | `monitoring/prometheus.md` |
| Log shipping | Centralized logs from nodes and clusters | `monitoring/prometheus.md` (§logging) |
| Argo CD | GitOps — sync manifests from internal GitLab | `management-cluster/argocd/argocd.md` |
| Harbor | Container image registry + vulnerability scanning | `addons/platform-addons.md` |
| Nexus | Artifact cache (Helm, PyPI, npm, Maven) | `addons/platform-addons.md` |
| GitLab | Source control + pipelines | `automation/` |
| Velero | Cluster backup/restore (to Ceph) | `lifecycle/backup/backup-and-dr.md` |

## Scrape targets

Prometheus scrapes:
- Kubernetes components (kubelet, API server, scheduler, controller-manager)
- Ceph MGR endpoint `:9283`
- Node exporters on every host
- Edge load balancers

Alertmanager routes critical alerts: node down, disk full, etcd quorum lost.

## GitOps

Argo CD auto-syncs every platform component from `config/` in the internal GitLab. Use the `platform` GitLab project for platform manifests, `apps` for workloads.

## Navigation

**[← Prev · 07. Traffic edge](./../rancher/rancher.md)** | **[Next → 09. Backup & upgrade](./../../lifecycle/backup/backup-and-dr.md)**
