# Ceph storage (cephadm path)

## A. Purpose and architecture

Ceph deployed by cephadm on dedicated Linux hosts, consumed by Kubernetes through the external CSI driver, and optionally exposed as S3 via RGW.

```
        K8s cluster                    Ceph cluster (dedicated hosts)
  +-------------------+           +-----------------------------------+
  | CSI driver pod   |---------->| MON x3 (10.40.0.x:6789)            |
  | (external)       |           | OSD x N (10.40.0.x:6800-7568)      |
  +-------------------+           | MDS x N (CephFS, optional)         |
                                  | RGW x N (S3, optional)              |
                                  +-----------------------------------+
```

Two supported deployment models exist in this platform: this one (cephadm on dedicated hosts) and Rook-Ceph inside the cluster (`storage/rook-ceph/`). Containerized Ceph under Docker or Podman is not a supported model here.

## B. Requirements and compatibility

| Item | Requirement | Notes |
|---|---|---|
| Hosts | 3+ dedicated storage nodes | Minimum for a replicated pool with quorum |
| CPU | 8+ cores per OSD host | Ceph is not CPU-heavy; the requirement is for the network and decompression work |
| RAM | 16 GB+ per host, 2 GB per OSD in the OSD process | Blueprint-driven |
| Disks | Separate device per OSD | Data and journal separation via LVM |
| Journal | colocated NVMe or separate | BlueStore allocator |
| Network | 1x 10 GbE public, 1x 10 GbE cluster (separate NIC/VLAN recommended) | Replication traffic is the driver |
| OS | Oracle Linux 8/9 or Ubuntu 22.04/24.04 | Both supported; check the Ceph package availability for the exact release |
| Kernel | 5.4+ (OL9), 5.15 (Ubuntu 24.04) | Confirm against the Ceph release requirements |
| Filesystem | XFS with ftype=1 | Required by BlueStore |

## C. Sizing worksheet

State the assumptions; do not use a single formula.

**Replicated (3x) usable capacity:**

```
usable_raw = Σ(disk_size_available) × (1 - reserved_fraction)
usable_3x  = usable_raw / 3
```

Assumptions to state: `reserved_fraction` typically 0.05-0.10 (filesystem, WAL, DB), and that all OSDs are in one pool with replication size 3. A 3x pool at 80% utilization degrades recovery behaviour; the working target is 70% of usable.

**Erasure coding (4+2):**

```
usable_ec = raw × (k / (k+m)) = raw × (4/6) = raw × 0.667
```

Erasure coding saves space but has different failure and recovery characteristics: a node failure causes a slow read-decode path, and any single OSD loss consumes read bandwidth. Not recommended for write-heavy databases.

**Recovery headroom:** keep at least 25-30% of raw capacity unallocated so a failed OSD can be replaced and rebalanced without filling the pool. This is the constraint that matters most in practice.

**IOPS:** derived from the disk type and queue depth.

| Media | Typical random IOPS (4K) | Sequential throughput | Use |
|---|---|---|---|
| HDD (7200-10k rpm) | 100-250 | 150-250 MB/s | Capacity, backup, archive |
| SSD/SATA | 50-100k | 500 MB/s | Databases, general |
| NVMe | 200-800k+ | 2-7 GB/s | Hot data, OSD DB, journal |

**Network:** replication of a 3x pool writes 2 copies of the data to the network, plus reads. A 1 GB write consumes roughly 2 GB of network egress. A 10 GbE link supports roughly 1.25 GB/s of client write throughput with 3x replication before it saturates.

**Latency:** OSD commit latency is dominated by the journal device. An NVMe journal is roughly 10x faster than a colocated HDD journal.

## D. CRUSH and failure domains

```
root default
  host osd-1
    osd 0
    osd 1
  host osd-2
    osd 2
    osd 3
  host osd-3
    osd 4
    osd 5
```

Rules:
- Never place all OSDs of a replicated pool in one host. The CRUSH map is the mechanism, not a convention.
- For rack awareness, define a `row` or `room` bucket and map each host to it.
- A pool with 3 hosts and 3 replicas tolerates one host loss. A pool with 2 hosts and 3 replicas does not tolerate a host loss, because CRUSH cannot place 3 replicas on 2 hosts.

## E. Deployment with cephadm

Execution context: **first storage node**, then the others.

```bash
# 1. Install cephadm on the first node
# Oracle Linux
dnf install -y cephadm
# Ubuntu
apt install -y cephadm

# 2. Bootstrap
cephadm bootstrap --mon-ip 10.40.0.11 --cluster-network 10.41.0.0/24

# 3. Copy the ceph.conf and keyring to the other nodes
scp /etc/ceph/ceph.conf /etc/ceph/ceph.client.admin.keyring root@10.40.0.12:/etc/ceph/
scp /etc/ceph/ceph.conf /etc/ceph/ceph.client.admin.keyring root@10.40.0.13:/etc/ceph/

# 4. Add hosts (run on the admin host)
cephadm shell -- ceph orch host add osd-2 10.40.0.12
cephadm shell -- ceph orch host add osd-3 10.40.0.13

# 5. List available devices
cephadm shell -- ceph orch device ls

# 6. Create OSDs
cephadm shell -- ceph orch daemon osd-2 lvm list --format json
cephadm shell -- ceph orch apply osd --all

# 7. Check
cephadm shell -- ceph -s
```

## F. Pools, RBD, CephFS, RGW

```bash
# Replicated pool
cephadm shell -- ceph osd pool create rbd 64 64
cephadm shell -- ceph osd pool application enable rbd rbd

# CephFS
cephadm shell -- ceph mgr module enable cephfs --force
cephadm shell -- ceph fs new cephfs cephfs_metadata cephfs_data
cephadm shell -- ceph orch apply mds --all

# RGW
cephadm shell -- ceph mgr module enable rgw --force
cephadm shell -- ceph orch apply rgw rgw --placement="3 osd-1 osd-2 osd-3"  # placement must respect the CRUSH map
```

## G. RBD images and Kubernetes consumption

```bash
# Create an image
cephadm shell -- rbd create --pool rbd --size 10 --image-type thick vol1
cephadm shell -- rbd info vol1
```

The external CSI driver (`cephcsi`) is deployed separately in the cluster; it uses the same `ceph.conf` and an admin or restricted keyring. Deploy it via Argo CD in the Application Cluster.

StorageClass:

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: ceph-external-rbd
provisioner: rbd.csi.ceph.com
parameters:
  clusterID: <cluster-id>
  fsid: <fsid>
  pool: rbd
  imageFeatures: layering
  csi.storage.k8s.io/provisioner-secret-name: ceph-csi-provisioner
  csi.storage.k8s.io/provisioner-secret-namespace: ceph-csi
  csi.storage.k8s.io/controller-expand-secret-name: ceph-csi-provisioner
  csi.storage.k8s.io/controller-expand-secret-namespace: ceph-csi
  csi.storage.k8s.io/node-stage-secret-name: ceph-csi-node
  csi.storage.k8s.io/node-stage-secret-namespace: ceph-csi
reclaimPolicy: Delete
allowVolumeExpansion: true
volumeBindingMode: Immediate
```

The CSI secrets come from Vault via External Secrets; they are not inline in the StorageClass.

## H. Monitoring

The Ceph manager module exposes Prometheus metrics directly:

```bash
cephadm shell -- ceph mgr module enable prometheus
cephadm shell -- ceph prometheus self-managed
```

Key metrics: `ceph_health_status`, `ceph_osd_up`, `ceph_pg_degraded`, `ceph_pg_incomplete`, `ceph_pool_bytes_used`, `ceph_osd_commit_latency_ms`, `ceph_mon_quorum_status`.

Dashboard + alerts in `monitoring/prometheus.md`.

## I. Recovery procedures

### OSD failure

```bash
cephadm shell -- ceph orch device ls        # identify the failed device
cephadm shell -- ceph osd tree
# Replace the disk on the host, then:
cephadm shell -- ceph orch device ls
cephadm shell -- ceph orch apply osd <host> --replace <osd-id>
```

The pool backfills automatically. Watch `ceph -s` for `HEALTH_WARN` with `pg_degraded` and confirm the backfill completes.

### MON loss

With 3 MONs, losing 1 keeps quorum. Losing 2 does not. Recovery:

```bash
cephadm shell -- ceph mon dump        # find the mons
# On the surviving mon host:
cephadm shell -- ceph mon remove <removed-mon-id>
cephadm shell -- ceph orch apply mon --placement="3 <host1> <host2> <host3>"
```

### Node loss

```bash
cephadm shell -- ceph orch host rm <host>   # after the host is gone
```

### Quorum loss (all MONs down)

Recovery requires a monmap and the OSD map from a backup. This is why `cephadm shell -- ceph mon dump` and the OSD map are backed up along with the data. See `lifecycle/backup/`.

## J. Backup and disaster recovery

Ceph has three different mechanisms, and they are not interchangeable:

| Mechanism | Protects against | Does NOT protect against |
|---|---|---|
| Replication (3x) | Disk/node failure | Logical corruption, cluster-wide loss, ransomware | 
| Snapshots (RBD/CephFS) | Accidental modification | Cluster loss |
| RGW versioning | Object overwrite | Cluster loss |
| Cluster-level backup (CephFS snapshots + RBD export, or a filesystem-level backup of the RGW zone) | Cluster loss, region loss | Bad deletes without versioning |

For Kubernetes volumes, use Velero with the CSI snapshotter for application-consistent backups, and a separate Ceph-side backup for the storage platform itself.

## K. Upgrades

Order matters and Ceph upgrades are not reversible across major versions.

```bash
# 1. Check the upgrade path for the exact versions
cephadm shell -- ceph versions
# 2. Upgrade the manager
cephadm shell -- ceph orch upgrade start cephadm
# 3. Upgrade the monitors (one at a time)
cephadm shell -- ceph orch upgrade start mon
# 4. Upgrade OSDs (one at a time, the orchestrator handles it)
cephadm shell -- ceph orch upgrade start osd
```

The upgrade must not skip a major version. The supported path is in the Ceph release notes for the target version. Record the check in `compatibility/version-matrix.md`.

## L. Best practices

Mandatory:
- One OSD per device, data and journal separated.
- CRUSH failure domains at host level, and rack level when the site has racks.
- 3+ hosts for any replicated pool that must survive host loss.
- Keep 25-30% of raw capacity free for rebalance.
- Back up the monmap, OSD map, and the data. The monmap is what makes a cluster rebuildable.
- Use a restricted cephx user for the CSI driver, not `client.admin`.

Strongly recommended:
- Separate physical network for the Ceph cluster traffic.
- NVMe journal on HDD-backed pools.
- BlueStore with BlueStore DB on NVMe.
- Monitor `HEALTH_WARN` and page on it, not just on `HEALTH_ERR`.
- Test an OSD replacement under load before production.
