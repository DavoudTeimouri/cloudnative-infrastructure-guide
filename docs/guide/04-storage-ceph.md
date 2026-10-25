# 04. Storage — Ceph

**Purpose:** Deploy a Ceph cluster with cephadm on dedicated storage hosts, ready to serve Kubernetes
via the external CSI driver and (optionally) S3 via RGW.

## Prerequisites
- Step 03 complete: container engine (Docker or Podman) installed and pulling from the internal registry.
- Step 01 complete: hosts reachable, time/DNS working, break-glass key installed.
- Storage hosts sized (§00.2) with one data device per OSD and optional NVMe DB/WAL (§02.4).

## Steps — in order

### 04.1 Prepare servers for each role
| Role | Minimum hosts | Placement rule |
|---|---|---|
| MON | 3 | Separate hosts, separate racks if available |
| MGR | 2 | Separate hosts from MON when possible |
| OSD | ≥ 3 | One OSD daemon per data disk; ≥ 3 hosts for 3-replica pool |
| MDS | 2 | Required only for CephFS |
| RGW | 2 | Behind the edge load balancer; stateless |

**Co-location:** MON+MGR may share a host; OSD+RGW may share; MDS+MGR may share. Never all three MONs
on one host. Never co-locate the only MON store with the OSD DB device.

### 04.2 Prepare air-gap registry/repository
Mirror Ceph images into the internal registry (Harbor default, or Nexus / self-hosted OCI) from a
connected build machine:

```bash
skopeo copy docker://quay.io/ceph/ceph:v18 docker://harbor.internal/ceph/ceph:v18 --dest-tls-verify=false
```

`skopeo` copies image layers/metadata between registries without a daemon — the tool used to stage
images into the air-gapped registry. Create a `ceph` project and a robot account with `pull`
permission. Pin image tags in `compatibility/version-matrix.md`.

Source: `storage/ceph/cephadm-deployment.md` (section C)

### 04.3 Deployment type: Docker, Podman, then Cephadm bootstrap
Bootstrap on the **first storage node only**. Pass `--docker` when using Docker; omit for Podman.

```bash
dnf install -y cephadm   # from internal mirror
cephadm --docker bootstrap \
  --mon-ip 10.40.0.11 \
  --cluster-network 10.41.0.0/24 \
  --registry harbor.internal \
  --log-to-file
```

`--registry harbor.internal` makes cephadm pull daemon images from your internal registry. Without it,
cephadm reaches for quay.io and fails in an air-gapped site.

Copy `/etc/ceph/ceph.conf` and `/etc/ceph/ceph.client.admin.keyring` to every other storage host.

### 04.4 Assign roles to nodes
Add hosts and label them by role:

```bash
cephadm shell -- ceph orch host add ceph-mon-2 10.40.0.12
cephadm shell -- ceph orch host label add ceph-mon-1 mon
cephadm shell -- ceph orch host label add ceph-osd-1 osd
cephadm shell -- ceph orch host label add ceph-rgw-1 rgw
```

Labels are the contract between node inventory and service spec. Use explicit host placement in the
service spec (not labels alone) so a typo fails at apply time.

Source: `storage/ceph/cephadm-deployment.md` (section E)

### 04.5 Check services and apply best practices
```bash
cephadm shell -- ceph -s
cephadm shell -- ceph orch ps
cephadm shell -- ceph mon stat
cephadm shell -- ceph mgr services
```

Expect `HEALTH_OK` before creating OSDs/pools. Mandatory best practices:
- One OSD per device; data and journal/DB on separate devices.
- CRUSH failure domains at host level (rack level when racks exist).
- ≥ 3 hosts for any replicated pool that must survive host loss.
- Keep 25–30% of raw capacity free for rebalance.
- Back up monmap + OSD map + data; use a restricted `cephx` user for CSI (not `client.admin`).
- Never mix Docker and Podman in one cluster.

### 04.6 Define OSDs
```bash
cephadm shell -- ceph orch device ls
cephadm shell -- ceph orch apply osd --all-available-devices
```
Verify: `ceph osd tree` — every OSD `up` and `in`.

### 04.7 Define pools (Kubernetes and non-Kubernetes)
**Replicated pool for Kubernetes (RBD / CSI):**
```bash
cephadm shell -- ceph osd pool create kube-rbd 64 64
cephadm shell -- ceph osd pool application enable kube-rbd rbd
cephadm shell -- ceph auth get-or-create client.csi-k8s \
  mon 'allow r' osd 'allow class-read object_prefix rbd_children, allow rwx pool=kube-rbd'
```

**Erasure-coded pool for non-Kubernetes bulk data:**
```bash
cephadm shell -- ceph osd pool create ec-pool 64 64 erasure
```

**CephFS** and **RGW** (S3) as needed. Place RGW behind the edge load balancer.

### 04.8 Prepare monitoring daemons
```bash
cephadm shell -- ceph mgr module enable prometheus
cephadm shell -- ceph prometheus self-managed
```
Key metrics: `ceph_health_status`, `ceph_osd_up`, `ceph_pg_degraded`, `ceph_mon_quorum_status`.
Scrape the MGR endpoint `:9283` from the management network.

Source: `storage/ceph/cephadm-deployment.md` (full ordered guide)

## Validation
- [ ] `ceph -s` reports `HEALTH_OK`.
- [ ] `ceph osd tree` shows every OSD `up` and `in`.
- [ ] MON quorum healthy (`ceph mon stat`).
- [ ] `kube-rbd` pool exists with `rbd` application enabled.
- [ ] Restricted `client.csi-k8s` user created (not `client.admin`).
- [ ] Prometheus module enabled; `:9283/metrics` returns `ceph_health_status`.

## Navigation
**[← Prev · 03. Container engine](./03-container-engine.md)** | **[Next → 05. Kubernetes](./05-kubernetes.md)**
