# Architecture Overview

## Layers

| Layer | Components | Failure impact |
|---|---|---|
| Physical | Servers, PDUs, switches | Node loss; storage designed to tolerate |
| Offline distribution | Harbor, Nexus, RPM/DEB mirrors, GitLab | New deployments blocked; running workloads unaffected |
| Automation | Automation Management Server, Ansible, AWX, GitLab Runner | Changes blocked; workloads unaffected |
| Identity & secrets | Keycloak, SSSD/AD, Vault, internal CA | Login blocked; workloads keep running |
| Storage | Ceph MON/MGR/OSD/MDS/RGW, Rook operator | PVC IO blocks; pod restart loop |
| Kubernetes | Control plane, etcd, CNI, CSI | Scheduling/API blocked; running pods keep IP |
| GitOps | Argo CD, GitLab | New/changed deploys blocked; no auto-revert |
| Management | Rancher, Prometheus, Grafana, Loki | Visibility lost; no data plane impact |

## Control / data plane split

- **Management Cluster** — Rancher, Argo CD, Keycloak, Prometheus/Grafana, GitLab runner. Dedicated infrastructure worker pool, no application workloads.
- **Application Clusters** — general workers, GPU workers, storage-facing workers. No Rancher, no Vault server, no GitLab.

Rationale: `decisions/ADR-0010.md`, `decisions/ADR-0013.md`, `decisions/ADR-0025.md`.

## Networking

| Segment | Purpose | Typical CIDR (PROVISIONAL) |
|---|---|---|
| mgmt | SSH, Ansible, monitoring, GitLab, registry, Vault, identity | 10.10.0.0/24 |
| control-plane | kube-apiserver, etcd peer/client, CNI control | 10.20.0.0/24 |
| pod | pod CIDR per cluster (Cilium native routing) | 10.30.0.0/16, 10.31.0.0/16 |
| service | ClusterIP range | 10.32.0.0/16, 10.33.0.0/16 |
| storage | Ceph public + cluster networks | 10.40.0.0/24 + 10.41.0.0/24 |
| gpu | GPU worker mgmt + NVLink/PCIe fabric | 10.50.0.0/24 |
| dmz | external LB VIP, ingress, reverse proxy | 10.60.0.0/24 |
| nodeport | 30000-32767 or MetalLB pool 10.61.0.10-10.61.0.30 | PROVISIONAL |

Verify every CIDR against the site plan before build. All ports: `network-matrix/network-communication-matrix.md`.
