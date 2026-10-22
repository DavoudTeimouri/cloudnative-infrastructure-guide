# Rook-Ceph in Kubernetes

## A. Purpose and architecture

Ceph managed by the Rook operator inside a Kubernetes cluster, exposing RBD, CephFS, and RGW through the Rook CSI driver.

```
Kubernetes cluster
  +---------------------------------------------------+
  | rook-ceph-operator (Deployment)                    |
  |   CRDs: CephCluster, CephBlockPool, ...            |
  |                                                    |
  |  rook-ceph-mon (3)  rook-ceph-osd (N)             |
  |  rook-ceph-mds (N) rook-ceph-rgw (N)              |
  |  rook-csi-* (DaemonSet + provisioner)              |
  +---------------------------------------------------+
```

## B. When to use Rook versus cephadm

| Criterion | Rook-Ceph | cephadm (external) |
|---|---|---|
| Storage scope | One cluster | Shared across clusters |
| Deployment model | Operator-managed in K8s | Managed on dedicated hosts |
| Failure coupling | A cluster-wide network/CNI failure can affect storage | Independent of the cluster |
| K8s integration | Native CRDs, CSI, PVC lifecycle | External CSI driver, still good |
| Operational overhead | Higher (two control loops) | Lower (vendor lifecycle) |
| Best for | Cluster-local storage, simpler estates | Shared capacity, strict independence, multi-cluster |

This platform supports both. Choose per cluster and document which one a given StorageClass belongs to.

## C. Offline preparation

- CRDs: `crds.yaml` from the pinned Rook release.
- Operator: `operator.yaml`, `common.yaml`.
- Images: operator, CSI provisioner, cephcsi, and the Ceph daemon images for the pinned Ceph version. All listed in `offline-artifacts/artifact-matrix.md`.
- Rook needs the Ceph container images matching the Ceph version it supports. The Rook release notes state which Ceph version it ships with — record it in `compatibility/version-matrix.md`.

## D. Installation

```bash
# CRDs first — they must be applied before the operator
kubectl apply -f https://github.com/rook/rook/releases/download/<VERSION>/crds.yaml
kubectl apply -f https://github.com/rook/rook/releases/download/<VERSION>/common.yaml
kubectl apply -f https://github.com/rook/rook/releases/download/<VERSION>/operator.yaml

kubectl -n rook-ceph rollout status deployment/rook-ceph-operator --timeout=300s
```

CephCluster (`manifests/cluster/cephcluster.yaml`):

```yaml
apiVersion: rook.io/v1
kind: CephCluster
metadata:
  name: rook-ceph
  namespace: rook-ceph
spec:
  cephVersion:
    image: quay.io/ceph/ceph:v18.2.x     # VERIFY against the pinned Rook release
  dataDirHostPath: /var/lib/rook
  mon:
    count: 3
    allowMultiplePerNode: false
  mgr:
    count: 2
    modules:
      - name: rook
        enabled: true
      - name: pg_autoscaler
        enabled: true
      - name: rook-cephfs
        enabled: true
      - name: rook-rgw
        enabled: true
  dashboard:
    enabled: true
    ssl: true
  network:
    provider: host
    # Or use a dedicated StorageClass for the public/cluster network
  storage:
    useAllNodes: false
    useAllDevices: false
    nodes:
      - name: "node1"
        devices:
          - name: "sdb"
            config:
              osdsPerDevice: "1"
      - name: "node2"
        devices:
          - name: "sdb"
            config:
              osdsPerDevice: "1"
      - name: "node3"
        devices:
          - name: "sdb"
            config:
              osdsPerDevice: "1"
  resources:
    osd:
      requests:
        cpu: "2"
        memory: 4Gi
  priorityClassNames: [system-node-critical]
```

`useAllDevices: false` with explicit `devices` is mandatory in production. `useAllDevices: true` claims every unmounted disk, including a disk that an operator intends to use for something else.

## E. Pools, filesystems, object store

```yaml
# CephBlockPool
apiVersion: rook.io/v1
kind: CephBlockPool
metadata:
  name: replicapool
  namespace: rook-ceph
spec:
  failureDomain: host
  replicated:
    size: 3
  crushRoot: "my-root"
  deviceClass: ssd
  parameters:
    targetSizeRatio: 0.5
```

```yaml
# CephFilesystem
apiVersion: rook.io/v1
kind: CephFilesystem
metadata:
  name: myfs
  namespace: rook-ceph
spec:
  metadataPool:
    replicated:
      size: 3
  dataPool:
    name: replicapool
  metadataServer:
    activeCount: 2
    activeStandby: true
```

```yaml
# CephObjectStore (RGW)
apiVersion: rook.io/v1
kind: CephObjectStore
metadata:
  name: my-store
  namespace: rook-ceph
spec:
  storePool:
    name: replicapool
  gateway:
    port: 80
    instances: 2
  hostNetwork:
    enable: false
  security:
    kms:
      connectionDetails:
        # Vault KMS integration (optional)
        vaultBackend: vault
  users:
    - name: "app-user"
      displayName: "Application user"
      capabilities:
        - "buckets=*"
        - "users=*"
```

## F. StorageClasses

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: ceph-rbd
  annotations:
    storageclass.kubernetes.io/is-default-class: "true"
provisioner: rook-ceph.cephcsi.com
allowVolumeExpansion: true
reclaimPolicy: Delete
volumeBindingMode: Immediate
parameters:
  csi.storage.k8s.io/provisioner-secret-name: rook-csi-cephfs-provisioner
  csi.storage.k8s.io/provisioner-secret-namespace: rook-ceph
  csi.storage.k8s.io/controller-expand-secret-name: rook-csi-cephfs-provisioner
  csi.storage.k8s.io/controller-expand-secret-namespace: rook-ceph
  csi.storage.k8s.io/node-stage-secret-name: rook-csi-cephfs-node
  csi.storage.k8s.io/node-stage-secret-namespace: rook-ceph
  csi.storage.k8s.io/fstype: ext4
  csi.storage.k8s.io/pool: replicapool
  csi.storage.k8s.io/clusterID: rook-ceph
```

CephFS StorageClass is the same with `provisioner: rook-ceph.cephcsi.com` and `csi.storage.k8s.io/fstype: ext4` pointing at the filesystem name.

## G. Validation

```bash
kubectl -n rook-ceph get pods
kubectl -n rook-ceph exec deploy/rook-ceph-operator -- ceph -s
kubectl get storageclass
kubectl -n rook-ceph get cephcluster -o yaml | head -40

# Function test
kubectl apply -f - <<'EOF'
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: rook-test
spec:
  accessModes: [ReadWriteOnce]
  resources:
    requests:
      storage: 1Gi
  storageClassName: ceph-rbd
EOF
```

## H. Operations

| Task | Procedure |
|---|---|
| Add an OSD | Add the node to `spec.storage.nodes`, apply, Rook creates the OSD |
| Replace a failed OSD | The OSD pod goes `Crashed`; replace the disk, then remove the OSD from the node list and re-apply |
| Scale a pool | Edit `CephBlockPool.spec.replicated.size`, apply; the data rebalances |
| Expand a pool | Edit `spec.parameters.targetSizeRatio` upward, apply |
| Enable snapshots | The CSI snapshotter is deployed by Rook by default; create `VolumeSnapshot` objects |
| Back up | Velero with the CSI snapshot integration, or `rbd export` to object storage |

## I. Upgrades — the sequence matters

Ceph upgrades are not reversible across major versions, and Rook adds a layer. The order:

1. Upgrade the Rook operator (via Argo CD).
2. Upgrade Ceph (the `cephVersion.image` in the CephCluster) — the operator orchestrates the daemon upgrade in the correct order (mon, mgr, osd, mds, rgw).
3. Upgrade the CSI driver if required by the Rook release.

Never set a Ceph image version that the installed Rook release does not support. The Rook release notes list the supported Ceph version — this is the single most common cause of a broken Rook upgrade.

## J. Best practices

Mandatory:
- Explicit device list, never `useAllDevices: true`.
- `failureDomain: host` for replicated pools, plus rack awareness where the site has racks.
- The Rook operator excluded from admission-policy enforcement (it needs broad permissions).
- Node labels marking storage nodes so OSD pods land on them.
- A node drain procedure that stops OSDs gracefully before a node maintenance window.

Strongly recommended:
- Dedicated storage node pool, separate from the general worker pool.
- Separate the Ceph public and cluster networks with a StorageClass-based network definition where the site has the VLANs.
- Enable the pg_autoscaler module and alert on PG state.
- Keep the Ceph dashboard enabled but behind the site access policy.
