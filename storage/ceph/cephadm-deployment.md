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

Two supported deployment models exist in this platform: this one (cephadm on dedicated hosts) and Rook-Ceph inside the cluster (`storage/rook-ceph/`). Containerized Ceph under Docker or Podman is not a supported model here — the container engine only runs the daemons; cephadm orchestrates them.

This document is a full, ordered instruction set for the cephadm path:

1. Prepare servers for each role
2. Prepare air-gap repositories/registries
3. Deployment type: Docker, Podman, then Cephadm bootstrap
4. Assign roles to nodes (and all roles to one server when co-locating)
5. Check services and apply best practices
6. Define OSDs
7. Define pools (Kubernetes and non-Kubernetes) and other
8. Prepare monitoring daemons

---

## B. Step 1 — Prepare servers for each role

Do this on every Ceph host before any cephadm command. Ceph assumes a clean, tuned host; it does not fix the OS for you.

### 1.1 Host roles and counts

| Role | Minimum hosts | Placement rule | Failure tolerance |
|---|---|---|---|
| MON | 3 | Separate hosts, separate racks if available | 1 host (odd count only; 2 is worse than 1; 4 tolerates the same as 3) |
| MGR | 2 | Separate hosts from MON when possible | 1 host (one active, one standby) |
| OSD | ≥ 3 | One OSD daemon per data disk; ≥ 3 hosts for a 3-replica pool | 1 host |
| MDS | 2 | Active + standby; required only for CephFS | 1 host |
| RGW | 2 | Behind the edge load balancer; stateless | 1 host |
| Crash/exporter | all hosts | Co-located | — |

Never put MON on the same host as the only OSD of a pool, and never let the DB/WAL device be shared with the OS.

### 1.2 OS and kernel

Supported: Oracle Linux 8/9 or Ubuntu 22.04/24.04. Kernel 5.4+ (OL9) / 5.15 (Ubuntu 24.04). Confirm against the Ceph release notes for the pinned version.

```bash
# Required kernel modules on every host
modprobe br_netfilter
modprobe nf_conntrack
modprobe rbd

# Persist across reboots
cat > /etc/modules-load.d/ceph.conf <<'EOF'
br_netfilter
nf_conntrack
rbd
EOF
```

### 1.3 Time and name resolution

All Ceph hosts must agree on time; monitor quorum depends on timestamp agreement.

```bash
# NTP (internal servers only; air-gapped site)
chronyc sources -v

# DNS must resolve every Ceph host name from every other Ceph host
getent hosts ceph-mon-1 ceph-mon-2 ceph-mon-3 ceph-osd-1
```

### 1.4 Disks and filesystems

One data device per OSD. XFS with `ftype=1` is required by BlueStore.

```bash
# List candidate devices
lsblk -d -o NAME,SIZE,TYPE,ROTA,MODEL

# Wipe stale filesystem/signatures on data devices (destructive)
wipefs -a /dev/sdb
```

Reserve a separate NVMe device per host for the OSD BlueStore DB/WAL when data devices are HDD or SATA SSD. Do not share the DB/WAL device with the OS.

### 1.5 Network

Use two NICs/VLANs when possible: one public (client/MON/RGW traffic, `10.40.0.0/24`) and one cluster (replication/OSD traffic, `10.41.0.0/24`). Replication traffic is the driver; 10 GbE is the minimum for production.

```bash
# Verify both networks are reachable between every pair of hosts
ping -c 3 10.40.0.12
ping -c 3 10.41.0.12
```

### 1.6 SSH access

The bootstrap host must reach every other Ceph host over SSH as root (or a sudo-capable account) without a password prompt. cephadm installs the engine and daemons on remote hosts itself.

```bash
# From the bootstrap host
ssh root@ceph-osd-2 'hostname'
ssh root@ceph-osd-3 'hostname'
```

---

## C. Step 2 — Prepare air-gap repositories/registries

cephadm pulls Ceph container images at bootstrap and whenever it deploys or upgrades a daemon. In an air-gapped site there is no internet, so the images must already live in your internal registry and every host must pull from it.

### 2.1 Internal registry (Harbor)

Harbor is the platform's image and OCI chart registry (`harbor.internal`, port 443). Ceph images are mirrored into it ahead of time from a connected build machine.

```bash
# Run on a connected machine, never on an air-gapped host
skopeo copy docker://quay.io/ceph/ceph:v18 docker://harbor.internal/ceph/ceph:v18 --dest-tls-verify=false
skopeo copy docker://quay.io/ceph/ceph:v17 docker://harbor.internal/ceph/ceph:v17 --dest-tls-verify=false
```

Record the exact image tags in `compatibility/version-matrix.md` so the pinned version propagates through the build.

### 2.2 Container engine registry mirror

Configure every Ceph host's container engine to pull from the internal registry so bootstrap and daemon deployment never touch the internet.

**Docker** — `/etc/docker/daemon.json`:

```json
{
  "registry-mirrors": ["https://harbor.internal"],
  "live-restore": true
}
```

**Podman** — `/etc/containers/registries.conf`:

```ini
[registries.search]
registries = ['harbor.internal']

[registries.insecure]
registries = ['harbor.internal']
```

(TLS-verified in production; `insecure` is shown only because some air-gap sites terminate TLS at an internal load balancer.)

Restart the engine after the change:

```bash
systemctl restart docker      # Docker
systemctl restart podman.socket   # Podman
```

### 2.3 Air-gap package repository (OS packages)

cephadm and the container engine must come from your internal mirror, not from OS vendor repos. Do not mix OS vendor repos and internal mirrors on the same host; the version pins diverge silently.

```bash
# Oracle Linux
dnf install -y cephadm podman docker-ce docker-ce-cli containerd.io   # from the internal OL mirror

# Ubuntu
apt install -y cephadm podman docker-ce docker-ce-cli containerd.io   # from the internal Ubuntu mirror
```

---

## D. Step 3 — Deployment type: Docker, Podman, Cephadm

cephadm runs every Ceph daemon in a container. It supports Podman (upstream default) and Docker. Pick one engine **per cluster** and never mix engines inside one cluster — the orchestrator records the engine at bootstrap and reuses it for every daemon. Whichever engine is chosen, it must already be installed, enabled, and pulling from the internal registry *before* `cephadm bootstrap`; cephadm will not install the engine.

### D.1 Engine: Docker

```bash
# Install from the internal mirror (OL example; apt on Ubuntu)
dnf install -y docker-ce docker-ce-cli containerd.io
systemctl enable --now docker

cat > /etc/docker/daemon.json <<'EOF'
{ "registry-mirrors": ["https://harbor.internal"], "live-restore": true }
EOF
systemctl restart docker

docker info | grep -i server-version
```

When bootstrapping with Docker, pass `--docker` to `cephadm bootstrap` and to every subsequent `cephadm` invocation.

### D.2 Engine: Podman

```bash
# Install from the internal mirror
dnf install -y podman
systemctl enable --now podman.socket

podman info | grep -i host.version
```

When bootstrapping with Podman, omit `--docker` (Podman is the default).

### D.3 Cephadm bootstrap

Run on the **first storage node only** (the initial MON host). This creates the cluster, the first MON, the MGR, and writes `/etc/ceph/ceph.conf` and `/etc/ceph/ceph.client.admin.keyring`.

```bash
# Install cephadm on the first node (from the internal mirror)
dnf install -y cephadm   # OL
# apt install -y cephadm   # Ubuntu

# Bootstrap. Pass --docker only when Docker is the engine; omit for Podman.
cephadm --docker bootstrap \
  --mon-ip 10.40.0.11 \
  --cluster-network 10.41.0.0/24 \
  --registry harbor.internal \
  --log-to-file

# Verify the bootstrap host is healthy
cephadm shell -- ceph -s
cephadm shell -- ceph orch ps
```

`--registry harbor.internal` tells cephadm to pull daemon images from your internal registry. Without it, cephadm reaches for quay.io, which fails in an air-gapped site.

Copy the cluster config to the other hosts so they can join:

```bash
scp /etc/ceph/ceph.conf /etc/ceph/ceph.client.admin.keyring root@10.40.0.12:/etc/ceph/
scp /etc/ceph/ceph.conf /etc/ceph/ceph.client.admin.keyring root@10.40.0.13:/etc/ceph/
```

---

## E. Step 4 — Assign roles to nodes (and all roles to one server when co-locating)

### E.1 Add hosts

Run from the bootstrap host (or any host with `cephadm shell` access). Ensure the engine is installed on each new host first; cephadm does not install it.

```bash
cephadm shell -- ceph orch host add ceph-mon-2 10.40.0.12
cephadm shell -- ceph orch host add ceph-mon-3 10.40.0.13
cephadm shell -- ceph orch host add ceph-osd-1 10.40.0.14
cephadm shell -- ceph orch host add ceph-osd-2 10.40.0.15
cephadm shell -- ceph orch host add ceph-osd-3 10.40.0.16

cephadm shell -- ceph orch host ls
```

### E.2 Label hosts by role

Labels are the contract between the node inventory and the service spec:

```bash
cephadm shell -- ceph orch host label add ceph-mon-1 mon
cephadm shell -- ceph orch host label add ceph-mon-2 mon
cephadm shell -- ceph orch host label add ceph-mon-3 mon
cephadm shell -- ceph orch host label add ceph-mgr-1 mgr
cephadm shell -- ceph orch host label add ceph-mgr-2 mgr
cephadm shell -- ceph orch host label add ceph-osd-1 osd
cephadm shell -- ceph orch host label add ceph-osd-2 osd
cephadm shell -- ceph orch host label add ceph-osd-3 osd
cephadm shell -- ceph orch host label add ceph-mds-1 mds
cephadm shell -- ceph orch host label add ceph-mds-2 mds
cephadm shell -- ceph orch host label add ceph-rgw-1 rgw
cephadm shell -- ceph orch host label add ceph-rgw-2 rgw
```

### E.3 Assign all roles to one server (co-location)

Small sites cannot spare ten hosts. Co-location is a deliberate trade-off: fewer hosts, higher blast radius.

Allowed co-location:
- MON + MGR may share a host (never all three MONs on one host).
- OSD + RGW may share a host (RGW is stateless).
- MDS + MGR may share a host.
- MON + OSD on the same host only with ≥ 3 hosts; losing one host loses a monitor and a third of the data at once.

Never co-locate the only MON store with the OSD DB device.

To assign all roles to one server, apply all labels to that single host and use explicit host placement in the service spec (§F.5). The generated platform layout uses separated hosts by default; co-location is a manual edit and the operator owns that decision.

Example — all roles on one host (lab/small site only):

```bash
cephadm shell -- ceph orch host label add ceph-all-1 mon,mgr,osd,mds,rgw
```

---

## F. Step 5 — Check services and apply best practices

### F.1 Check services after bootstrap

```bash
# Cluster health
cephadm shell -- ceph -s
cephadm shell -- ceph health detail

# Daemon placement and state
cephadm shell -- ceph orch ps
cephadm shell -- ceph orch host ls

# Monitor quorum
cephadm shell -- ceph mon stat
cephadm shell -- ceph mon dump

# MGR status (active/standby)
cephadm shell -- ceph mgr services
```

Expect `HEALTH_OK` before you create OSDs or pools. `HEALTH_WARN` about missing daemons is normal until placement is applied; `HEALTH_ERR` is not.

### F.2 Best practices (mandatory)

- One OSD per device; data and journal/DB on separate devices.
- CRUSH failure domains at host level, rack level when the site has racks.
- ≥ 3 hosts for any replicated pool that must survive host loss.
- Keep 25–30% of raw capacity free for rebalance.
- Back up the monmap, OSD map, and the data; the monmap is what makes a cluster rebuildable.
- Use a restricted `cephx` user for the CSI driver, not `client.admin`.
- Never mix Docker and Podman in one cluster.

Strongly recommended:
- Separate physical network for Ceph cluster (replication) traffic.
- NVMe journal/DB device on HDD-backed pools.
- Page on `HEALTH_WARN`, not only on `HEALTH_ERR`.
- Test an OSD replacement under load before production.

---

## G. Step 6 — Define OSDs

List devices, then create OSDs. Create OSDs by label so a host replacement keeps working.

```bash
# List available devices on all hosts
cephadm shell -- ceph orch device ls

# Create OSDs across all hosts (uses all available data devices)
cephadm shell -- ceph orch apply osd --all-available-devices

# Or, explicit per-host with DB on a separate NVMe device
cephadm shell -- ceph orch apply osd ceph-osd-1 \
  --data-devices /dev/sdb,/dev/sdc \
  --db-devices /dev/nvme1n1
```

Verify:

```bash
cephadm shell -- ceph osd tree
cephadm shell -- ceph osd stat
cephadm shell -- ceph osd df
```

Each OSD daemon owns one data disk. `ceph osd tree` must show every OSD `up` and `in`.

---

## H. Step 7 — Define pools (Kubernetes and non-Kubernetes)

Pools are where data lives. Choose replicated for low-latency/block workloads and erasure coding (EC) for capacity; never EC for write-heavy databases.

### H.1 Replicated pool for Kubernetes (RBD / CSI)

```bash
cephadm shell -- ceph osd pool create kube-rbd 64 64
cephadm shell -- ceph osd pool application enable kube-rbd rbd

# Restricted user for the CSI driver (not client.admin)
cephadm shell -- ceph auth get-or-create client.csi-k8s \
  mon 'allow r' \
  osd 'allow class-read object_prefix rbd_children, allow rwx pool=kube-rbd'
```

The external CSI driver (`cephcsi`) consumes this pool and is deployed separately in the cluster; it uses `ceph.conf` and a restricted keyring, injected from Vault via External Secrets — never inline.

Kubernetes StorageClass:

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: ceph-external-rbd
provisioner: rbd.csi.ceph.com
parameters:
  clusterID: <fsid-from-`ceph fsid`>
  pool: kube-rbd
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

### H.2 Erasure-coded pool for non-Kubernetes bulk data

```bash
cephadm shell -- ceph osd pool create ec-pool 64 64 erasure
cephadm shell -- ceph osd pool application enable ec-pool rgw
```

EC usable = raw × (k / (k+m)). A 4+2 pool gives ~67% usable. EC saves space but read-decode on recovery is slow; not recommended for write-heavy databases.

### H.3 CephFS (non-Kubernetes or shared filesystem)

```bash
cephadm shell -- ceph mgr module enable cephfs --force
cephadm shell -- ceph fs new cephfs cephfs_metadata cephfs_data
cephadm shell -- ceph orch apply mds --placement="2 ceph-mds-1 ceph-mds-2"
```

### H.4 RGW (S3 object)

```bash
cephadm shell -- ceph mgr module enable rgw --force
cephadm shell -- ceph orch apply rgw rgw \
  --placement="2 ceph-rgw-1 ceph-rgw-2" \
  --spec '{"rgw_frontend_port": 8080}'
```

Place RGW behind the edge load balancer (`network-matrix/external-load-balancer.md`), never expose it directly to clients.

### H.5 RBD images (non-Kubernetes use)

```bash
cephadm shell -- rbd create --pool kube-rbd --size 100 --image-type thick vm-disk-1
cephadm shell -- rbd info vm-disk-1
cephadm shell -- rbd ls kube-rbd
```

---

## I. Step 8 — Prepare monitoring daemons

The Ceph manager exposes Prometheus metrics directly; no separate exporter is needed on every host.

```bash
# Enable Prometheus metrics from the MGR
cephadm shell -- ceph mgr module enable prometheus
cephadm shell -- ceph prometheus self-managed
```

Key metrics to alert on: `ceph_health_status`, `ceph_osd_up`, `ceph_pg_degraded`, `ceph_pg_incomplete`, `ceph_pool_bytes_used`, `ceph_osd_commit_latency_ms`, `ceph_mon_quorum_status`.

Enable the dashboard (optional UI):

```bash
cephadm shell -- ceph mgr module enable dashboard
cephadm shell -- ceph dashboard ac-user-create admin [REDACTED] administrator
```

Dashboard + alerting rules are wired into the platform Prometheus in `monitoring/prometheus.md`. Scrape the MGR metrics endpoint (`:9283`) from the management network.

Verify monitoring:

```bash
cephadm shell -- ceph mgr services
curl -s http://<mgr-host>:9283/metrics | grep ceph_health_status
```

---

## J. Recovery procedures (reference)

### OSD failure

```bash
cephadm shell -- ceph orch device ls
cephadm shell -- ceph osd tree
# Replace the failed disk on the host, then:
cephadm shell -- ceph orch device ls
cephadm shell -- ceph orch apply osd <host> --replace <osd-id>
```

Watch `ceph -s` until `pg_degraded` clears and backfill completes.

### MON loss

With 3 MONs, losing 1 keeps quorum; losing 2 does not.

```bash
cephadm shell -- ceph mon dump
cephadm shell -- ceph mon remove <removed-mon-id>
cephadm shell -- ceph orch apply mon --placement="3 ceph-mon-1 ceph-mon-2 ceph-mon-3"
```

### Quorum loss (all MONs down)

Requires the monmap and OSD map from backup; see `lifecycle/backup/`. Back up `ceph mon dump` and the OSD map alongside the data — without the monmap the cluster is not rebuildable.

---

## K. What this document intentionally does not cover

- Disk partitioning and layout (per-site, manual).
- Joining hosts to Active Directory/LDAP — intentional per ADR-0015; identity is application-layer only.
- Rebooting after kernel args (operator decides when).
- The in-cluster Rook-Ceph model — that is `storage/rook-ceph/rook-ceph.md`.
