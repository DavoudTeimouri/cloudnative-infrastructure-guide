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

## E. Role separation and per-role sizing

Ceph is not one role. Each daemon type has its own count, its own failure tolerance and, when the
configurator is used, its own node group. Separate hosts per role are the safe default; co-locating
is an optimisation you make on purpose.

| Role | Default count | Placement rule | Failure tolerance | Notes |
|---|---|---|---|---|
| MON | 3 | Separate hosts, separate racks if available | 1 host | Odd count only. 2 is worse than 1; 4 tolerates the same as 3 |
| MGR | 2 | Separate hosts from MON when possible | 1 host | One active, one standby. The dashboard and the orchestrator die with both |
| OSD | ≥ 3 | One OSD daemon per data disk; at least 3 hosts for a 3-replica pool | 1 host with 3 hosts and 3 replicas | The only role that holds data. Dedicated NVMe for DB/WAL |
| MDS | 2 | Active + standby; 2 hosts minimum | 1 host | Required only for CephFS. More than 3 is rarely worth it |
| RGW | 2 | Behind the edge load balancer | 1 host | Stateless; scale by request rate, not by data size |
| Crash / exporter | all hosts | Co-located | — | Not a capacity role |

Sizing per role, as a starting point for a 3-host site:

| Role | vCPU | RAM | Disk |
|---|---|---|---|
| MON | 2 | 8 GiB | 100 GiB SSD (the monitor store is small but latency-sensitive) |
| MGR | 2 | 8 GiB | 100 GiB |
| OSD | 8 | 32 GiB (≈ 4 GiB per OSD plus cache) | 1 data disk per OSD + 1 DB/WAL NVMe |
| MDS | 4 | 16 GiB | 100 GiB |
| RGW | 4 | 8 GiB | 100 GiB |

Never put MON on the same host as the only OSD of a pool, and never let the DB/WAL device be shared
with the OS. A full DB device stalls the OSD, and a stalled OSD turns into `slow ops` before it
turns into a failed disk.

### Host labels

cephadm places services by label, so labels are the contract between the node inventory and the
service spec:

```bash
cephadm shell -- ceph orch host label add ceph-mon-1 mon
cephadm shell -- ceph orch host label add ceph-mgr-1 mgr
cephadm shell -- ceph orch host label add ceph-osd-1 osd
cephadm shell -- ceph orch host label add ceph-mds-1 mds
cephadm shell -- ceph orch host label add ceph-rgw-1 rgw
```

### Service spec with explicit per-role placement

```yaml
service_type: mon
placement:
  hosts:
    - ceph-mon-1
    - ceph-mon-2
    - ceph-mon-3
---
service_type: mgr
placement:
  hosts: [ceph-mgr-1, ceph-mgr-2]
---
service_type: osd
service_id: data
placement:
  hosts: [ceph-osd-1, ceph-osd-2, ceph-osd-3]
data_devices:
  all: true
db_devices:
  all: false
  paths: [/dev/nvme1n1]
---
service_type: mds
service_id: cephfs
placement:
  hosts: [ceph-mds-1, ceph-mds-2]
---
service_type: rgw
service_id: rgw
placement:
  hosts: [ceph-rgw-1, ceph-rgw-2]
spec:
  rgw_frontend_port: 8080
```

`placement: hosts:` is explicit on purpose. `placement: label:` is shorter and survives a host
replacement only if the new host gets the same label — both are valid, and the generated file uses
explicit hosts so a typo fails at apply time instead of silently placing a MON on an OSD host.

### Co-location rules, when you must

Small sites cannot spare ten hosts. Then:

1. MON and MGR may share a host, but never all three MONs on one host.
2. OSD and RGW may share a host; RGW is stateless.
3. MDS and MGR may share a host.
4. MON and OSD on the same host only with three or more hosts, and accept that losing one host loses
   a monitor and a third of the data at once.
5. Never co-locate the only copy of the MON store with the OSD DB device.

The configurator generates the separated layout by default; co-location is a manual edit of the
generated spec, and the operator owns that decision.

## F. Container engine: Podman or Docker

cephadm runs every Ceph daemon in a container. It supports Podman (the upstream default) and
Docker. Both are supported here; the choice is per cluster and is recorded in the catalog so the
generated scripts match.

| | Podman (default) | Docker |
|---|---|---|
| Upstream posture | Default for cephadm, used by the Ceph project's own CI | Supported, second-class in upstream testing |
| Rootless | Possible, but Ceph daemons need privileged host access; run as root | Not applicable, the daemon is root |
| systemd integration | `podman` units are generated by cephadm itself | `docker` units are generated the same way; the engine must be enabled first |
| Package | `podman` from the OS repos | `docker-ce` from the internal mirror; `docker.io` on Ubuntu is too old for some releases |
| Air-gap | Images pulled from the internal registry via `--registry` | Same, plus `/etc/docker/daemon.json` registry mirror |
| Failure mode | A podman upgrade can restart containers unless `--live-restore`-equivalent settings are set | `live-restore` in `daemon.json` keeps containers alive during a daemon restart |

Whichever engine is chosen, the node baseline must already have it installed, enabled, and pulling
from the internal registry *before* `cephadm bootstrap`. cephadm will not install the engine.

```bash
# Podman
dnf install -y podman && systemctl enable --now podman.socket
# Docker (from the internal mirror)
dnf install -y docker-ce docker-ce-cli containerd.io && systemctl enable --now docker
# registry mirror for the engine, so every image pull is offline-capable
mkdir -p /etc/docker && cat >/etc/docker/daemon.json <<'EOF'
{ "registry-mirrors": ["https://harbor.internal"], "live-restore": true }
EOF
systemctl restart docker
```

## G. Deployment with cephadm

Execution context: **first storage node**, then the others. Pass `--docker` to bootstrap and to
every `cephadm` invocation when Docker is the engine; omit it for Podman.

```bash
# 1. Install cephadm on the first node
# Oracle Linux
dnf install -y cephadm
# Ubuntu
apt install -y cephadm

# 2. Bootstrap. --docker only when Docker is the engine.
cephadm --docker bootstrap \
  --mon-ip 10.40.0.11 \
  --cluster-network 10.41.0.0/24 \
  --registry harbor.internal \
  --log-to-file

# 3. Copy the ceph.conf and keyring to the other nodes
scp /etc/ceph/ceph.conf /etc/ceph/ceph.client.admin.keyring root@10.40.0.12:/etc/ceph/
scp /etc/ceph/ceph.conf /etc/ceph/ceph.client.admin.keyring root@10.40.0.13:/etc/ceph/

# 4. Add hosts (run on the admin host)
cephadm shell -- ceph orch host add osd-2 10.40.0.12
cephadm shell -- ceph orch host add osd-3 10.40.0.13

# 5. Install the engine on the new hosts first, then label them
cephadm shell -- ceph orch host label add osd-2 osd
cephadm shell -- ceph orch host label add osd-3 osd

# 6. List available devices
cephadm shell -- ceph orch device ls

# 7. Create OSDs by label, not by hostname, so replacement keeps working
cephadm shell -- ceph orch apply osd --all-available-devices

# 8. Check
cephadm shell -- ceph -s
cephadm shell -- ceph orch ps
```

Mixed engines are not supported within one cluster: the orchestrator records the engine at
bootstrap and reuses it for every daemon it deploys.

## H. Pools, RBD, CephFS, RGW

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

## I. RBD images and Kubernetes consumption

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

## J. Monitoring

The Ceph manager module exposes Prometheus metrics directly:

```bash
cephadm shell -- ceph mgr module enable prometheus
cephadm shell -- ceph prometheus self-managed
```

Key metrics: `ceph_health_status`, `ceph_osd_up`, `ceph_pg_degraded`, `ceph_pg_incomplete`, `ceph_pool_bytes_used`, `ceph_osd_commit_latency_ms`, `ceph_mon_quorum_status`.

Dashboard + alerts in `monitoring/prometheus.md`.

## K. Recovery procedures

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

## L. Backup and disaster recovery

Ceph has three different mechanisms, and they are not interchangeable:

| Mechanism | Protects against | Does NOT protect against |
|---|---|---|
| Replication (3x) | Disk/node failure | Logical corruption, cluster-wide loss, ransomware | 
| Snapshots (RBD/CephFS) | Accidental modification | Cluster loss |
| RGW versioning | Object overwrite | Cluster loss |
| Cluster-level backup (CephFS snapshots + RBD export, or a filesystem-level backup of the RGW zone) | Cluster loss, region loss | Bad deletes without versioning |

For Kubernetes volumes, use Velero with the CSI snapshotter for application-consistent backups, and a separate Ceph-side backup for the storage platform itself.

## M. Upgrades

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

## N. Best practices

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
