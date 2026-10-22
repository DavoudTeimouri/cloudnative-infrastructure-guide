# CSI and persistent storage troubleshooting

## Symptoms

- A PVC stays `Pending`.
- A pod that mounts a PVC stays in `ContainerCreating` with a mount error.
- `kubectl describe pvc` shows `ProvisioningFailed` or `failed to provision volume`.
- Volume expansion is rejected.
- A snapshot exists but the restore fails.

## Likely causes

| Cause | Discriminator |
|---|---|
| The StorageClass does not exist or the name is wrong | `kubectl get storageclass` |
| The CSI provisioner pod is not running | `kubectl -n rook-ceph get pods -l app=rook-csi-*` |
| The CSI controller cannot reach the Ceph MON | `ceph -s` from the CSI pod's network namespace |
| The secrets the CSI driver needs are missing | The StorageClass references a secret that does not exist |
| The Ceph cluster is not HEALTH_OK | `ceph -s` reports HEALTH_WARN or HEALTH_ERR |
| The pool has no space or no free PGs | `ceph df`, `ceph osd pool ls` |
| The `reclaimPolicy: Delete` destroyed the PV | `kubectl get pv` shows `Released` or the PV is gone |
| Expansion not enabled | The StorageClass lacks `allowVolumeExpansion: true` |
| Node staging fails | The node's kubelet cannot reach the OSD network |

## Diagnostic commands

```bash
# PVC and PV state
kubectl get pvc -n <ns>
kubectl describe pvc <name> -n <ns>
kubectl get pv

# CSI driver pods
kubectl -n rook-ceph get pods -l app=rook-csi-provisioner -o wide
kubectl -n rook-ceph logs deploy/rook-csi-provisioner --tail=100
kubectl -n rook-ceph logs ds/rook-csi-nodeplugin --tail=100

# Controller logs for the specific PVC
kubectl -n rook-ceph logs deploy/rook-csi-provisioner -c csi-provisioner --tail=200 | grep -i <pvc-name>

# StorageClasses
kubectl get storageclass -o yaml
kubectl describe storageclass <sc-name>

# Ceph health from the CSI pod's viewpoint
kubectl -n rook-ceph exec deploy/rook-ceph-operator -- ceph -s
kubectl -n rook-ceph exec deploy/rook-ceph-operator -- ceph df

# Snapshot classes
kubectl get volumesnapshotclass
kubectl get volumesnapshot -n <ns>
kubectl describe volumesnapshot <name> -n <ns>

# Node-level view
lsblk
mount | grep rook
dmesg | grep -i "ceph\|blk"
```

## Expected healthy state

```yaml
# kubectl get pvc
NAME       STATUS   VOLUME     CAPACITY   ACCESS MODES   STORAGECLASS   AGE
app-data   Bound    pvc-xxxx   10Gi       RWO            ceph-rbd       5m
```

```bash
# Ceph
HEALTH_OK
# ceph df
POOL_NAME  USED  %USED  MAX_AVAIL  OBJECTS
replicapool 1.2T  12%  8.8T       1024
```

## Remediation

### PVC stuck Pending

```bash
# Read the actual reason
kubectl describe pvc <name> -n <ns> | tail -20
```

Common causes and fixes:

| Message | Cause | Fix |
|---|---|---|
| `no such volume` / `failed to provision` with a CSI error | The CSI controller cannot reach the cluster | Check the CSI pod's network path to the MON |
| `storageclass not found` | Wrong StorageClass name | `kubectl get storageclass` and correct the PVC |
| `secret "..." not found` | The CSI secret is missing | Restore it from Vault via External Secrets |
| `rpc error: code = ResourceExhausted` | No space in the pool | Free space or add OSDs |
| `pool ... has insufficient replicas` | Not enough PGs for the requested replica size | Increase the number of hosts, or lower the pool replica size |

### Volume expansion

```bash
# The StorageClass must allow it
kubectl patch storageclass ceph-rbd -p '{"allowVolumeExpansion":true}'
# Then expand the PVC
kubectl patch pvc <name> -n <ns> -p '{"spec":{"resources":{"requests":{"storage":"20Gi"}}}}'
kubectl get pvc <name> -n <ns> -w
```

If the expansion is rejected with "only dynamically provisioned pvc can be resized and no storageclass has allowVolumeExpansion set", the StorageClass was never patched. This is a StorageClass property, not a PVC property.

### Snapshot restore failure

```bash
kubectl get volumesnapshotclass
kubectl describe volumesnapshot <name> -n <ns>

# The snapshot must have a bound content
kubectl get volumesnapshotcontents
```

Common causes:
- No `VolumeSnapshotClass` matching the StorageClass's `deletionPolicy`.
- The `csi.storage.k8s.io/snapshotter-secret` secret is missing from the CSI namespace.
- The snapshot content exists but the source volume was deleted (the snapshot becomes unusable for restore when its backing object is gone).

### Mount failure in a pod

```bash
# Node-side
kubectl describe pod <pod> -n <ns> | grep -A5 "Mount"
dmesg -T | grep -i ceph
kubectl -n rook-ceph logs ds/rook-csi-nodeplugin --tail=100
```

The node's kubelet stages the volume. If the node cannot reach the OSD ports (6800-7568), the mount hangs. Check the firewall matrix row for the storage network.

## Risks

- `reclaimPolicy: Delete` removes the PV and, with it, the Ceph image, when the PVC is deleted. Confirm before deleting a PVC.
- A `failed to delete` PV can leave a Ceph image in a `leaked` state, consuming space. Check `ceph fs ls` and `rbd ls` for orphaned images.
- `ceph osd pool delete` is irreversible and destroys data. Never run it to "clean up" a pool that a PVC still references.

## Verification after remediation

```bash
kubectl get pvc -A
kubectl run pvc-test --rm -it --restart=Never --image=busybox:1.36 -- \
  sh -c 'dd if=/dev/zero of=/data/test bs=1M count=100 && sync && wc -c /data/test'
```

Then re-run acceptance tests E-01 (dynamic provisioning), E-02 (expansion), and E-03 (snapshot and restore).
