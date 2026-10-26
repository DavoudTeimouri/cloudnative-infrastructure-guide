# Control plane and etcd

The control plane runs the Kubernetes API server, controller manager, scheduler,
and — in the reference topology — a stacked etcd member on each control-plane node.
Kubespray owns installation and upgrades; this document records the decisions and
the operational boundaries.

## Topology

| Decision | Value | Record |
|---|---|---|
| Control-plane nodes | 3 for the first environment, 5 documented as the reference production topology | `decisions/ADR-0002-*` |
| etcd placement | Stacked on control-plane nodes | `decisions/ADR-0003-*` |
| Failure tolerance | 3 nodes tolerate 1 failure; 5 tolerate 2 | ADR-0002, ADR-0003 |
| Upgrade order | Control plane first, one node at a time | `kubespray/kubespray-deployment.md` |

Inventory grouping follows Kubespray: a node in `[control-plane]` with stacked etcd
must also be in `[etcd]` (`kubespray/kubespray-deployment.md`).

## What lives where

| Path | Content | Owner |
|---|---|---|
| `/etc/kubernetes/pki` | API server, kubelet, front-proxy, and etcd certificates | Kubespray |
| `/etc/kubernetes/manifests` | Static pod manifests for API server, controller manager, scheduler, etcd | Kubespray |
| `/var/lib/etcd` | etcd data directory | etcd |
| `/etc/kubernetes/admin.conf` | Admin kubeconfig (never distributed to users) | Kubespray |

Kubernetes internal PKI is Kubespray's, not cert-manager's. cert-manager issues
ingress and service certificates only (`secrets-management/pki/index.md`).

## Sizing and placement

- Control-plane nodes are not workers: no application pods, taints applied.
- etcd is latency-sensitive. Local SSD or NVMe, and no shared storage.
- Control-plane nodes spread across failure domains
  (`architecture/03-failure-domains.md`).
- API server access is restricted to the management subnet
  (`network-matrix/network-communication-matrix.md`).

## Validation

```bash
kubectl get nodes -l node-role.kubernetes.io/control-plane
kubectl -n kube-system get pods -l tier=control-plane
kubectl -n kube-system exec etcd-<node> -- etcdctl \
  --cacert=/etc/kubernetes/pki/etcd/ca.crt \
  --cert=/etc/kubernetes/pki/etcd/server.crt \
  --key=/etc/kubernetes/pki/etcd/server.key \
  endpoint health --cluster
kubectl -n kube-system exec etcd-<node> -- etcdctl member list
```

All members must report `healthy`; a member list shorter than the inventory means
a member was lost and must be replaced before the next failure.

## Backup

etcd snapshots are separate from Velero. Velero does not back up etcd, and a
cluster restore without an etcd snapshot restores workloads onto a different
control plane.

```bash
kubectl -n kube-system exec etcd-<node> -- etcdctl \
  --cacert=/etc/kubernetes/pki/etcd/ca.crt \
  --cert=/etc/kubernetes/pki/etcd/server.crt \
  --key=/etc/kubernetes/pki/etcd/server.key \
  snapshot save /var/lib/etcd/snapshot-$(date +%F).db
```

Move the snapshot off the node and verify it (`etcdctl snapshot status`). The
cadence and retention are recorded with the backup policy in
`lifecycle/backup/backup-and-dr.md`.

## Failure scenarios

| Failure | Effect | Recovery |
|---|---|---|
| One control-plane node lost | API available through the remaining members; etcd quorum intact at 3 nodes | Rebuild the node, rejoin with `cluster.yml --limit <host>` |
| Two of three control-plane nodes lost | etcd loses quorum, all API writes stop; running pods keep running | Restore quorum from a snapshot; do not attempt partial writes |
| Slow etcd disk | API latency rises, leader elections flap | Replace the disk; etcd is not tunable around bad hardware |
| Certificate expiry | API server or kubelet TLS fails | `cluster.yml` certificate renewal workflow in `kubespray/kubespray-deployment.md` |

## Related

- Deployment: `kubespray/kubespray-deployment.md`
- Versions: `compatibility/version-matrix.md`
- Ports: `network-matrix/port-requirements.md`
- Upgrades: `lifecycle/upgrades/upgrade-procedures.md`
