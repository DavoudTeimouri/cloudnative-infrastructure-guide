# Ceph storage (cephadm path)

## A. Purpose and architecture

Ceph deployed by cephadm on dedicated Linux hosts, consumed by Kubernetes through the external CSI driver, and optionally exposed as S3 via RGW.

```
        K8s cluster                    Ceph cluster (dedicated hosts)
  +-------------------+           +-----------------------------------+
  | CSI driver pod   |---------->| MON x3 (10.40.0.x:6789)            |
  | (external)       |           | MGR x2 (active/standby)              |
  +-------------------+           | OSD x N (10.40.0.x:6800-7568)      |
                                  | MDS x N (CephFS, optional)         |
                                  | RGW x N (S3, optional)              |
                                  +-----------------------------------+
```

Two supported deployment models exist in this platform: this one (cephadm on dedicated hosts) and Rook-Ceph inside the cluster (`storage/rook-ceph/`). cephadm runs every Ceph daemon as a container under one container engine — Docker or Podman, picked per cluster and never mixed — and orchestrates placement, upgrades, and recovery across the dedicated hosts.

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

#### Which roles can be hosted together

Co-location is a deliberate trade-off: fewer hosts, higher blast radius. The safest default is one role type per host. Co-locate only when the site cannot spare the hosts.

Allowed co-location:
- MON + MGR may share a host (never all three MONs on one host).
- OSD + RGW may share a host; RGW is stateless.
- MDS + MGR may share a host.
- MON + OSD on the same host only with ≥ 3 hosts; losing one host loses a monitor and a third of the data at once.

Never co-locate the only MON store with the OSD DB device.

#### Minimum requirements: VM vs physical

| Concern | Physical (bare metal) | Virtual machine |
|---|---|---|
| Ceph OSD | Recommended; direct disk access, predictable latency | Acceptable with raw/SCSI-passthrough disks; never a shared virtual disk |
| MON / etcd | Local SSD required | Local SSD + dedicated vCPUs; never shared storage |
| GPU (if present) | Full PCIe passthrough; MIG on H100/H200 SXM | vGPU/SR-IOV; MIG generally not virtualizable; pass the whole card |
| Failure domain | Physical host | Host + hypervisor + storage array |

#### Requirements calculations

State the assumptions; do not use a single formula.

**Replicated (3x) usable capacity:**

```
usable_raw = Σ(disk_size_available) × (1 - reserved_fraction)
usable_3x  = usable_raw / 3
```

`reserved_fraction` is typically 0.05–0.10 (filesystem, WAL, DB). Working target: 70% of usable — keep 25–30% of raw capacity free so a failed OSD can be replaced and rebalanced without filling the pool.

**Erasure coding (k+m):**

```
usable_ec = raw × (k / (k + m))
```

A 4+2 pool gives ~67% usable. EC saves space but read-decode on recovery is slow; not recommended for write-heavy databases.

**IOPS:** derived from disk type and queue depth.

**Network:** a 3x pool writes 2 copies to the network per 1 GB of client write. A 10 GbE link supports roughly 1.25 GB/s of client write throughput before saturation.

**Compute resources (vCPU and RAM):** Ceph is not CPU-heavy; the drivers are network, decompression, and per-OSD memory. These are per-host starting points, sized from the role count, not from disk size.

| Role | vCPU per host | RAM per host | Basis |
|---|---|---|---|
| MON | 2 | 8 GiB | Monitor store is small but latency-sensitive; CPU is light |
| MGR | 2 | 8 GiB | Dashboard and orchestrator run here; one active, one standby |
| OSD | 1 per OSD daemon, min 4 | 4 GiB per OSD daemon, min 16 GiB | Each OSD holds memory for its data and DB/WAL cache |
| MDS | 4 | 16 GiB | CephFS metadata server; more than 3 is rarely worth it |
| RGW | 4 | 8 GiB | Stateless; scale by request rate, not by data size |

**Per-OSD memory estimate:** each OSD daemon reserves roughly 4 GiB for its own cache plus the BlueStore DB/WAL working set. A host with 8 OSDs needs ~32 GiB just for OSD processes, plus OS overhead. Do not size RAM from disk capacity alone — size from the OSD count per host.

**vCPU oversubscription:** Ceph tolerates CPU oversubscription better than memory oversubscription. If hosts are RAM-bound, reduce OSDs per host before reducing vCPU.

**Example 3-host site (1 OSD per host, replicated 3x):**

| Host | Roles | vCPU | RAM | Disk |
|---|---|---|---|---|
| ceph-mon-1 | MON + MGR | 4 | 16 GiB | 100 GiB SSD |
| ceph-mon-2 | MON + MGR | 4 | 16 GiB | 100 GiB SSD |
| ceph-mon-3 | MON + OSD x1 | 5 | 20 GiB | 100 GiB SSD + 1 data disk |

Always add ~2 GiB RAM and 1 vCPU for the OS and the container engine overhead on top of the role totals.


### 1.2 OS and kernel — mandatory or best practice?

**Mandatory:** OS (Oracle Linux 8/9 or Ubuntu 22.04/24.04) and XFS with `ftype=1` for BlueStore. Ceph does not install or fix the OS.

**Best practice:** Kernel 5.4+ (OL9) / 5.15 (Ubuntu 24.04), dedicated NVMe for OSD DB/WAL, chrony for NTP. Confirm the exact kernel floor against the Ceph release notes for the pinned version.

Required kernel modules (mandatory for networking and RBD):

```bash
modprobe br_netfilter
modprobe nf_conntrack
modprobe rbd

cat > /etc/modules-load.d/ceph.conf <<'EOF'
br_netfilter
nf_conntrack
rbd
EOF
```

**How to check:**

```bash
cat /etc/os-release
uname -r
lsmod | grep -E 'br_netfilter|nf_conntrack|rbd'
getenforce || aa-status --enabled   # SELinux / AppArmor
```

**Impact if not applied:**
- Missing `br_netfilter` / `nf_conntrack`: bridged container traffic and Ceph replication traffic can be dropped or misrouted by netfilter; daemons may appear down.
- Missing `rbd`: RBD block devices cannot be mapped; the external CSI driver cannot attach volumes.
- No XFS `ftype=1`: BlueStore refuses the device; OSD creation fails.
- Wrong kernel: Ceph daemons may crash or refuse to start on unsupported kernels.

### 1.3 Time and name resolution

All Ceph hosts must agree on time; monitor quorum depends on timestamp agreement. A drifting clock can drop a monitor from quorum.

**NTP (internal only; air-gapped site):**

```bash
chronyc sources -v
chronyc tracking
```

Use at least two internal NTP sources; a third on a different switch is recommended.

**Name resolution:** every Ceph host must resolve every other Ceph host by name:

```bash
getent hosts ceph-mon-1 ceph-mon-2 ceph-mon-3 ceph-osd-1
```

**No DNS environment:** If there is no DNS server, use `/etc/hosts` on every Ceph host and keep it identical everywhere:

```bash
cat >> /etc/hosts <<'EOF'
10.40.0.11  ceph-mon-1
10.40.0.12  ceph-mon-2
10.40.0.13  ceph-mon-3
10.40.0.14  ceph-osd-1
10.40.0.15  ceph-osd-2
10.40.0.16  ceph-osd-3
EOF
```

Name resolution failures prevent cephadm from adding hosts and daemons from forming quorum.

### 1.4 Disks and filesystems (node preparation)

One data device per OSD. XFS with `ftype=1` is required by BlueStore.

```bash
lsblk -d -o NAME,SIZE,TYPE,ROTA,MODEL

# Destructive: wipes stale filesystems/signatures from data devices
wipefs -a /dev/sdb
```

Reserve a separate NVMe device per host for the OSD BlueStore DB/WAL when data devices are HDD or SATA SSD. Do not share the DB/WAL device with the OS.

### 1.5 Network

**Two NICs/VLANs (recommended):** one public (client/MON/RGW traffic, `10.40.0.0/24`) and one cluster (replication/OSD traffic, `10.41.0.0/24`). Replication traffic is the driver; 10 GbE is the minimum for production.

**One network:** If the site has only one network, put MON and OSD traffic on the same subnet/VLAN. Ceph still works, but replication traffic competes with client traffic on the same link. Mitigations:
- Size the link for the combined load (replication is roughly 2× the client write volume for a 3x pool).
- Use separate IP ranges within the same VLAN so firewall rules can still distinguish MON vs OSD traffic.
- Prefer 10 GbE or faster; 1 GbE is not suitable for production Ceph.

Verify reachability between every pair of hosts:

```bash
ping -c 3 10.40.0.12
```

### 1.6 SSH access

The bootstrap host must reach every other Ceph host over SSH without a password prompt, because cephadm installs the engine and daemons on remote hosts itself.

**Non-root user:** SSH as a non-root user with passwordless `sudo` is preferred over direct root login. cephadm elevates via sudo when needed.

```bash
# From the bootstrap host, as the deploy user
ssh cephadm@ceph-osd-2 'hostname'
ssh cephadm@ceph-osd-3 'sudo hostname'
```

Ensure the deploy user can run sudo without a password on each Ceph host:

```bash
# On each Ceph host
echo "cephadm ALL=(ALL) NOPASSWD:ALL" | sudo tee /etc/sudoers.d/cephadm
```

**AD authentication:** Hosts must NOT be joined to Active Directory/LDAP (ADR-0015). Identity is application-layer only; nodes keep local accounts plus an offline break-glass key. Do not rely on AD/Kerberos for the SSH access cephadm uses — use local key-based authentication with the break-glass key installed for `root` or the deploy user.

Verify:

```bash
ssh cephadm@ceph-osd-2 'sudo cephadm --version'
```

---

## C. Step 2 — Prepare air-gap repositories/registries

cephadm pulls Ceph container images at bootstrap and whenever it deploys or upgrades a daemon. In an air-gapped site there is no internet, so the images must already live in your internal registry and every host must pull from it.

Pick **one** registry manager per site and do not mix them. Supported options:

| Registry manager | Best for | Notes |
|---|---|---|
| Harbor (platform default) | Image + OCI chart registry with projects, robot accounts, vulnerability scanning | Already referenced throughout this platform as `harbor.internal` |
| Nexus | Single manager for images **and** OS packages (yum/apt) plus docker repos | Good when one tool must own both artifacts and packages |
| Self-hosted OCI registry (suggested alternative) | Smaller air-gap sites that only need image mirroring | Single binary, filesystem storage, OCI-compatible; lighter than Harbor/Nexus |

The engine-side configuration (Docker `daemon.json`, Podman `registries.conf`) is in section D, per deployment method. This section covers the registry side: what to mirror and where.

### C.2.1 Harbor (platform default)

Mirror Ceph images into Harbor ahead of time from a connected build machine:

```bash
# Run on a connected machine, never on an air-gapped host
skopeo copy docker://quay.io/ceph/ceph:v18 docker://harbor.internal/ceph/ceph:v18 --dest-tls-verify=false
skopeo copy docker://quay.io/ceph/ceph:v17 docker://harbor.internal/ceph/ceph:v17 --dest-tls-verify=false
```

**What is skopeo?** `skopeo` is a tool for inspecting and copying container images between registries without running a daemon. It copies image layers and metadata directly from one registry to another (e.g. from the public `quay.io` to your internal Harbor), so you can stage Ceph images on a connected machine and push them into the air-gapped registry. Install it from your internal mirror (`dnf install -y skopeo` on Oracle Linux, `apt install -y skopeo` on Ubuntu).

Create a `ceph` project in Harbor and a robot account with `pull` permission for `cephadm` to use. Record the exact image tags in `compatibility/version-matrix.md` so the pinned version propagates through the build.

### C.2.2 Nexus

Mirror Ceph images into a Nexus docker (group) repository, e.g. `nexus.internal:8083` or `nexus.internal/repository/ceph/`:

```bash
# Run on a connected machine, never on an air-gapped host
skopeo copy docker://quay.io/ceph/ceph:v18 docker://nexus.internal:8083/ceph/ceph:v18 --dest-tls-verify=false
skopeo copy docker://quay.io/ceph/ceph:v17 docker://nexus.internal:8083/ceph/ceph:v17 --dest-tls-verify=false
```

Nexus can also serve OS packages (yum/apt group repos) so the same manager holds both images and packages. When Nexus is the registry, replace `harbor.internal` with `nexus.internal:<port>` everywhere below, and point Docker/Podman at the Nexus docker repository.

### C.2.3 Suggested alternative: self-hosted OCI registry (distribution)

For smaller air-gap sites that only need image mirroring and do not need Harbor's projects/robot accounts or Nexus's package repos, run a minimal OCI-compatible registry (the Docker `distribution` image) on a filesystem-backed store:

```bash
# Run on a connected machine, mirror into the self-hosted registry
skopeo copy docker://quay.io/ceph/ceph:v18 docker://registry.internal:5000/ceph/ceph:v18 --dest-tls-verify=false
skopeo copy docker://quay.io/ceph/ceph:v17 docker://registry.internal:5000/ceph/ceph:v17 --dest-tls-verify=false
```

Run it as a single container or systemd unit backed by a persistent volume. Configure it as insecure (or terminate TLS at the edge load balancer) and point Docker/Podman at `registry.internal:5000`.

---

## D. Step 3 — Deployment type: Docker, Podman, Cephadm

cephadm runs every Ceph daemon in a container. It supports Podman (upstream default) and Docker. Pick one engine **per cluster** and never mix engines inside one cluster — the orchestrator records the engine at bootstrap and reuses it for every daemon. Whichever engine is chosen, it must already be installed, enabled, and pulling from the internal registry *before* `cephadm bootstrap`; cephadm will not install the engine.

### D.1 Engine: Docker

Docker must be installed from the internal mirror, pointed at the internal registry, and allowed through the host firewall before `cephadm bootstrap`. cephadm does not install or configure the engine.

#### D.1.1 Install Docker from the internal mirror

```bash
# Oracle Linux (from the internal OL mirror)
dnf install -y docker-ce docker-ce-cli containerd.io

# Ubuntu (from the internal Ubuntu mirror)
apt install -y docker-ce docker-ce-cli containerd.io

systemctl enable --now docker
docker info | grep -i server-version
```

#### D.1.2 Configure daemon.json for air-gap

`/etc/docker/daemon.json` on every Ceph host:

```json
{
  "registry-mirrors": ["https://harbor.internal"],
  "insecure-registries": ["harbor.internal"],
  "live-restore": true,
  "storage-driver": "overlay2",
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "100m",
    "max-file": "3"
  },
  "dns": ["10.10.0.10"],
  "iptables": false,
  "bridge": "none",
  "default-address-pools": [
    { "base": "172.20.0.0/16", "size": 24 }
  ]
}
```

- `registry-mirrors` — pulls are redirected to Harbor so daemon and cephadm never reach quay.io.
- `insecure-registries` — Harbor terminates TLS at an internal load balancer; Docker treats it as insecure without this flag and refuses to pull.
- `live-restore` — containers keep running if the Docker daemon restarts.
- `iptables: false` / `bridge: none` — the platform manages the network and firewall with nftables/firewalld; Docker must not punch its own holes.
- `dns` — internal DNS so containers resolve `harbor.internal`, `ceph-mon-1`, etc.

```bash
mkdir -p /etc/docker
cat > /etc/docker/daemon.json <<'EOF'
{ ... }
EOF
systemctl restart docker
```

#### D.1.3 systemd environment drop-in (air-gap)

If the site uses an HTTP proxy for the connected build machine only, exclude it on Ceph hosts and never proxy internal traffic:

```bash
mkdir -p /etc/systemd/system/docker.service.d
cat > /etc/systemd/system/docker.service.d/no-proxy.conf <<'EOF'
[Service]
Environment="NO_PROXY=harbor.internal,10.40.0.0/24,10.41.0.0/24,.internal,localhost,127.0.0.1"
Environment="no_proxy=harbor.internal,10.40.0.0/24,10.41.0.0/24,.internal,localhost,127.0.0.1"
EOF
systemctl daemon-reload
systemctl restart docker
```

#### D.1.4 Firewall rules for Docker (nftables)

Docker daemon traffic to Harbor and between Ceph hosts:

```nft
# Allow outbound to the internal registry
ip daddr @harbor_hosts tcp dport 443 accept
# Allow outbound to the internal registry registry API
ip daddr @harbor_hosts tcp dport { 80, 443 } accept
# Allow Ceph daemon container traffic on the cluster network
ip saddr @storage_hosts ip daddr @storage_hosts tcp dport { 6789, 6800-7568, 7480 } accept
```

Do not open Docker's default `2375/tcp` (unencrypted Docker API). Verify:

```bash
docker info --format '{{ .ServerVersion }}'
curl -sk https://harbor.internal/api/v2.0/systeminfo | head -c 200
```

When bootstrapping with Docker, pass `--docker` to `cephadm bootstrap` and to every subsequent `cephadm` invocation.


### D.2 Engine: Podman

Podman is the upstream default for cephadm. It must be installed from the internal mirror, pointed at Harbor, and configured for air-gap before `cephadm bootstrap`. cephadm does not install or configure the engine.

cephadm runs Ceph daemons as root with privileged host access, so Podman is run **rootful** on Ceph hosts (not rootless).

#### D.2.1 Install Podman from the internal mirror

```bash
# Oracle Linux (from the internal OL mirror)
dnf install -y podman

# Ubuntu (from the internal Ubuntu mirror)
apt install -y podman

systemctl enable --now podman.socket
podman info | grep -i host.version
```

#### D.2.2 Configure registries.conf for air-gap

`/etc/containers/registries.conf` on every Ceph host:

```ini
[registries.search]
registries = ['harbor.internal']

[registries.insecure]
registries = ['harbor.internal']

[registries.block]
registries = ['docker.io', 'quay.io', 'ghcr.io']
```

- `registries.search` — unqualified image names resolve to Harbor first.
- `registries.insecure` — Harbor terminates TLS at an internal load balancer; Podman refuses plain-HTTP registries without this.
- `registries.block` — explicit deny-list so nothing accidentally pulls from the public internet.

```bash
mkdir -p /etc/containers
cat > /etc/containers/registries.conf <<'EOF'
[registries.search]
registries = ['harbor.internal']

[registries.insecure]
registries = ['harbor.internal']

[registries.block]
registries = ['docker.io', 'quay.io', 'ghcr.io']
EOF
```

#### D.2.3 Configure containers.conf for air-gap

`/etc/containers/containers.conf` on every Ceph host:

```ini
[containers]
dns = ["10.10.0.10"]

[storage]
driver = "overlay2"

[containers]
log_driver = "k8s-file"
log_opts = {
  "max-size": "100m",
  "max-file": "3"
}
```

- `dns` — internal DNS so containers resolve `harbor.internal` and Ceph host names.
- `log_driver` / `log_opts` — bounded container logs so a churning Ceph daemon cannot fill the root filesystem.

```bash
cat > /etc/containers/containers.conf <<'EOF'
[containers]
dns = ["10.10.0.10"]

[storage]
driver = "overlay2"

[containers]
log_driver = "k8s-file"
log_opts = {
  "max-size": "100m",
  "max-file": "3"
}
EOF
```

#### D.2.4 systemd environment drop-in (air-gap)

If the site uses an HTTP proxy for the connected build machine only, exclude it on Ceph hosts:

```bash
mkdir -p /etc/systemd/system/podman.socket.d
cat > /etc/systemd/system/podman.socket.d/no-proxy.conf <<'EOF'
[Socket]
Environment="NO_PROXY=harbor.internal,10.40.0.0/24,10.41.0.0/24,.internal,localhost,127.0.0.1"
Environment="no_proxy=harbor.internal,10.40.0.0/24,10.41.0.0/24,.internal,localhost,127.0.0.1"
EOF
systemctl daemon-reload
systemctl restart podman.socket
```

#### D.2.5 Firewall rules for Podman (nftables)

Podman daemon and Ceph daemon container traffic:

```nft
# Allow outbound to the internal registry
ip daddr @harbor_hosts tcp dport { 80, 443 } accept
# Allow Ceph daemon container traffic on the cluster network
ip saddr @storage_hosts ip daddr @storage_hosts tcp dport { 6789, 6800-7568, 7480 } accept
```

Do not expose the Podman API socket over TCP. Verify:

```bash
podman info --format '{{ .Host.Version }}'
curl -sk https://harbor.internal/api/v2.0/systeminfo | head -c 200
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

To assign all roles to one server, apply all labels to that single host and use explicit host placement via labels (E.2). The generated platform layout uses separated hosts by default; co-location is a manual edit and the operator owns that decision.

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
