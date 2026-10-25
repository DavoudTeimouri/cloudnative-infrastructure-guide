# 07. Application cluster

**Purpose:** Deploy one or more application Kubernetes clusters, size node pools per role, and
register them into Rancher as managed clusters.

## Prerequisites
- Step 06 complete: Rancher reachable, management cluster healthy.
- Step 05 complete: Kubespray playbook and image registry pattern proven.

## Steps

### 07.1 Create application control planes
Deploy separate control planes per application cluster (isolation). Register each into Rancher as a
managed cluster via the Rancher cluster registration token.

Source: `kubernetes/multiple-clusters.md`

### 07.2 Size node pools per role
Table-driven sizing — change the catalog value and regenerate:

| Role | vCPU rule | Memory rule | Disk rule | Why |
|---|---|---|---|---|
| Control plane | ≥4 per node | ≥16 GiB per node | ≥100 GiB etcd | etcd write load |
| Worker (general) | +2 per 10 pods | +2 GiB per 10 pods | 50-100 GiB | pod density |
| Storage worker (Ceph) | +2 per OSD | +4 GiB per OSD | dedicated disk | OSD DB/WAL |
| GPU worker | +4 per GPU | +8 GiB per GPU | 100 GiB | passthrough overhead |
| Edge worker | +2 per service | +4 GiB per service | 50 GiB | ingress buffer |

**Reservation:** Reserve **2 vCPU / 4.5 GiB** per host for the OS + monitoring agents before
allocating to workloads.

**PGs:** `(num_osd × 100) / replica_count`, rounded up to the next power of 2.

Source: `catalog/catalog.json` (sizing table), `kubernetes/node-resource-reservation.md`

### 07.3 Windows workers (optional)
If Windows workloads are required, add Windows worker nodes with the same networking (Cilium VXLAN or
Windows HNS) and registry mirror.

Source: `kubernetes/windows-workers.md`

### 07.4 Define workloads
Deploy applications as Helm charts from Nexus/Harbor, or GitOps-managed manifests synced by Argo CD.
Use node selectors/tolerations to land workloads on the right node pool.

## Validation
- [ ] Application cluster registered and `Ready` in Rancher.
- [ ] Node pools sized per table; OS+agent reservation applied.
- [ ] Workloads schedule on intended node pools (node affinity verified).
- [ ] Windows workers (if any) join and run a sample pod.
- [ ] Control plane replicas odd (1/3/5) and healthy.

## Navigation
**[← Prev · 06. Management cluster](./06-management-cluster.md)** | **[Next → 08. Traffic edge](./08-traffic-edge.md)**
