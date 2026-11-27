# Phase 3 — Storage Lifecycle

## Rook-Ceph Storage Operations

### Install Operator
```bash
kubectl apply -f https://github.com/rook/rook/releases/download/v1.14/crds.yaml
kubectl apply -f https://github.com/rook/rook/releases/download/v1.14/common.yaml
kubectl apply -f https://github.com/rook/rook/releases/download/v1.14/operator.yaml
```

### CephCluster CRD Example
3 MON, storage on `/dev/sdb` per node, 3 replicas, separate storage network.

### Storage Classes Exposed to Kubernetes
- `ceph-rbd` — block PVC for databases
- `cephfs` — shared filesystem for multi-pod workloads
- `ceph-rgw` — S3-compatible object via RGW

### Operational Checklist
- Ceph health `HEALTH_OK` before consuming PVCs
- `ceph df` and `ceph osd df` monitored via Prometheus exporter
- OSD CR respects `deviceFilter` so OS disks are not claimed
- Regular OSD replacement and rebalance procedures
- Backup and restore drills with Velero

### Storage Lifecycle — Kubespray Version Contradictions
The Rook-Ceph version must align with the Kubespray release. Contradictions found:

| Kubespray Release | Rook Version | Issue | Resolution |
|---|---|---|---|
| release-2.32 | rook/1.15 | CRD compatibility mismatch | Use rook/1.14 until release-2.33 |
| release-2.31 | rook/1.14 | OSD upgrade path broken | Pin to rook/1.13 with workaround |
| release-2.30 | rook/1.13 | RGW version conflict | Upgrade RGW separately |

### Recommended Matrix
- Kubespray release-2.32 → Rook 1.14.x
- Kubespray release-2.31 → Rook 1.13.x
- Kubespray release-2.30 → Rook 1.12.x