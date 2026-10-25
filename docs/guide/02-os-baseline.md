# 02. OS baseline

**Purpose:** Harden the operating system on every host — kernel, modules, users, disks, filesystems,
time, locale, and security — before any container engine or cluster software is installed.

## Prerequisites
- Step 01 complete: hosts reachable via SSH, break-glass key installed, time and DNS working.

## Steps

### 02.1 Choose and install the OS
Supported: **Oracle Linux 8/9** or **Ubuntu Server 22.04/24.04 LTS**. Install from your internal OS
mirror (Nexus or self-hosted), never from public vendor repos.

Confirm the kernel floor for your Ceph/Kubespray versions:
- Oracle Linux 9: kernel 5.4+
- Ubuntu 24.04: kernel 5.15

Source: `operating-systems/oracle-linux/baseline.md`, `operating-systems/ubuntu/baseline.md`

### 02.2 Required kernel modules
Load and persist on every host:

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

### 02.3 Users and access
- Create the deploy user (e.g. `deploy` / `cephadm`) with passwordless `sudo`.
- Install the break-glass SSH public key for `root` on every host.
- Do not join hosts to Active Directory/LDAP (ADR-0015).

### 02.4 Disks and filesystems
- One data device per Ceph OSD; never a shared virtual disk, never a partition shared with the OS.
- XFS with `ftype=1` is required by BlueStore.
- Reserve a separate NVMe device per host for the OSD BlueStore DB/WAL when data devices are HDD or
  SATA SSD. Do not share the DB/WAL device with the OS or another OSD's data disk.

Do not format OSD disks yourself — cephadm formats and manages them via BlueStore. This step only
clears stale signatures so device detection is clean:

```bash
lsblk -d -o NAME,SIZE,TYPE,ROTA,MODEL
wipefs -a /dev/sdb   # destructive — data devices only
```

Source: `operating-systems/host-configuration.md` (§1.4), `storage/ceph/cephadm-deployment.md` (§1.4)

### 02.5 Security baseline
| Input | Purpose |
|---|---|
| SELinux / AppArmor | Enforcing (OL9) or enabled (Ubuntu) |
| Firewall backend | nftables (preferred) or firewalld |
| SSH | Port from site plan, password auth off, break-glass key only |
| Audit | Retention and rotation configured |
| Unattended updates | Security-only, with a maintenance window (no silent 03:00 reboot) |

Source: `operating-systems/host-configuration.md` (§6 Security baseline)

### 02.6 Per-role overrides
Each role inherits the common baseline, then applies its overrides:

| Role | Key overrides |
|---|---|
| Control plane | High file descriptors, high pid_max, etcd-friendly NTP |
| Worker | maxPodsPerNode, CNI IP pool coverage, static CPU manager (Guaranteed QoS only) |
| Ceph OSD | THP=never, swappiness=1, high file descriptors |
| Ceph MON | Time sync is critical; high file descriptors |
| Load balancer | No containerd/cgroupDriver/maxPodsPerNode; nftables kernel module |
| Operation server | Identity + sudoNopasswd for Ansible; break-glass key here |
| GPU | IOMMU kernel args for passthrough |
| Edge | topologyManagerPolicy=best-effort, smaller maxPodsPerNode |

Source: `operating-systems/host-configuration.md` (per-role sections)

## Validation
Run on every host:
```bash
timedatectl
chronyc tracking
swapon --show                  # empty — swap disabled
sysctl vm.max_map_count fs.file-max kernel.pid_max
getenforce || aa-status --enabled
firewall-cmd --list-all || nft list ruleset | head
crictl info | head -5          # after step 03
lsmod | grep -E 'br_netfilter|nf_conntrack|rbd'
```

## Navigation
**[← Prev · 01. Infrastructure prep](./01-infrastructure-prep.md)** | **[Next → 03. Container engine](./03-container-engine.md)**
