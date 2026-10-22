# Ubuntu baseline

Distro-specific. Do not copy Oracle Linux commands here.

## A. Purpose and scope

Baseline for Ubuntu Server 22.04 LTS and 24.04 LTS nodes running Kubernetes, Ceph, GitLab, Harbor, Nexus, Vault, and GPU workloads.

Supported releases: 22.04 LTS and 24.04 LTS. Confirm against the pinned Kubespray release's supported-OS list before use — record the check in `compatibility/version-matrix.md`.

## B. Key differences from Oracle Linux

| Area | Ubuntu | Oracle Linux |
|---|---|---|
| Package manager | `apt` / `dpkg` | `dnf` / `yum` |
| Mandatory access control | AppArmor | SELinux |
| Firewall | `ufw` (often inactive) | `firewalld` |
| Repo format | deb822 `.sources` on 24.04, legacy `.list` on 22.04 | INI |
| Kernel | Ubuntu generic | Oracle UEK / RHCK |
| Python default | 3.10 (22.04) / 3.12 (24.04) | 3.6/3.9 (OL8), 3.9 (OL9) |
| Certificate trust | `/usr/local/share/ca-certificates/` + `update-ca-certificates` | `/etc/pki/ca-trust/source/anchors/` + `update-ca-trust` |
| Service control | `systemctl` | `systemctl` |

## C. Repository configuration (offline)

24.04 deb822 format (`/etc/apt/sources.list.d/internal.sources`):

```
Types: deb
URIs: https://nexus.internal/repository/deb-ubuntu/
Suites: noble noble-updates noble-security
Components: main universe restricted multiverse
Signed-By: /usr/share/keyrings/internal-nexus.gpg
```

22.04 legacy format (`/etc/apt/sources.list.d/internal.list`):

```
deb [signed-by=/usr/share/keyrings/internal-nexus.gpg] https://nexus.internal/repository/deb-ubuntu/ jammy main universe restricted multiverse
deb [signed-by=/usr/share/keyrings/internal-nexus.gpg] https://nexus.internal/repository/deb-ubuntu/ jammy-updates main universe restricted multiverse
deb [signed-by=/usr/share/keyrings/internal-nexus.gpg] https://nexus.internal/repository/deb-ubuntu/ jammy-security main universe restricted multiverse
```

Key import:

```bash
curl -fsSL https://nexus.internal/repository/deb-ubuntu/keys/internal.gpg \
  | gpg --dearmor -o /usr/share/keyrings/internal-nexus.gpg
apt-get update
```

Disable everything else so a node can never attempt an external fetch:

```bash
# Move any other sources aside
mkdir -p /etc/apt/sources.list.d.disabled
mv /etc/apt/sources.list /etc/apt/sources.list.d.disabled/ 2>/dev/null || true
```

## D. AppArmor

AppArmor is enforcing by default on Ubuntu. It profiles by path, not label, and the container runtime ships its own profiles.

```bash
aa-status
apt install apparmor-utils
```

Common actions:

```bash
# Put a profile in complain mode while diagnosing
aa-complain /usr/bin/containerd

# Inspect loaded profiles
aa-enforce
```

Traps:
- An unconfined profile is not the same as AppArmor being disabled. `aa-status` shows unconfined processes; that is normal for many daemons.
- Do not disable AppArmor to fix a container problem. Find the right path rule.
- `lxc-apparmor-profiles` and the Docker/AppArmor defaults apply; custom paths for Ceph OSD directories usually need an explicit rule.

## E. Sysctl and modules

```bash
# /etc/modules-load.d/k8s.conf
br_netfilter
overlay
```

Same sysctl file content as the Oracle Linux baseline (see `operating-systems/oracle-linux/baseline.md` section E) — the kernel parameter names are the same. Store it at `/etc/sysctl.d/99-kubernetes.conf`.

## F. Swap

```bash
swapoff -a
sed -i '/\sswap\s/s/^/#/' /etc/fstab
```

## G. Time sync

```bash
apt install chrony
systemctl enable --now chrony
chronyc tracking
```

Ubuntu 24.04 defaults to `systemd-timesyncd`; install `chrony` explicitly so the node config is identical across both distros.

## H. Firewall

Ubuntu ships `ufw` but it is usually inactive. Choose one and apply it consistently:

```bash
# Option A: ufw
ufw default deny incoming
ufw default allow outgoing
ufw allow from 10.10.0.0/24 to any port 22 proto tcp
ufw enable
ufw status verbose

# Option B: nftables (preferred, matches the firewall model)
apt install nftables
systemctl enable --now nftables
```

The network matrix is the source of truth for the ruleset; the firewall implementation is a deployment choice.

## I. SSH hardening

Same file content as the Oracle Linux baseline. Ubuntu 22.04+ uses `sshd_config.d/` includes by default; confirm `Include /etc/ssh/sshd_config.d/*.conf` is present at the top of `/etc/ssh/sshd_config`.

Break-glass account:

```bash
adduser --disabled-password --gecos "" emergency
usermod -aG sudo emergency
```

## J. Audit and logging

```bash
apt install auditd audispd-plugins
systemctl enable --now auditd
```

```bash
cat > /etc/audit/rules.d/kubernetes.rules <<'EOF'
-w /etc/ssh/sshd_config -p wa -k sshd_config
-w /etc/passwd -p wa -k identity
-w /etc/group -p wa -k identity
-w /etc/sudoers -p wa -k sudoers
-w /var/lib/ceph -p wa -k ceph
EOF
augenrules --load
```

## K. Certificate trust

```bash
cp internal-ca.crt /usr/local/share/ca-certificates/
update-ca-certificates
# verify
openssl verify -CApath /etc/ssl/certs internal-ca.crt
```

## L. Unattended upgrades and patching

```bash
apt install unattended-upgrades
dpkg-reconfigure -plow unattended-upgrades
```

For controlled maintenance windows, disable automatic reboots and drive patching through Ansible in a change window instead:

```bash
# /etc/apt/apt.conf.d/20auto-upgrades
APT::Periodic::Update-Package-Lists "0";
APT::Periodic::Unattended-Upgrade "0";
```

## M. Container runtime prerequisites

```bash
apt install containerd
# config
mkdir -p /etc/containerd
containerd config default > /etc/containerd/config.toml
# systemd cgroup driver
systemctl enable --now containerd
```

Ubuntu 24.04 uses cgroup v2 by default; the containerd `SystemdCgroup = true` setting is required. Confirm in the rendered config:

```bash
grep SystemdCgroup /etc/containerd/config.toml
```

## N. Filesystem notes

- XFS needs `ftype=1` for overlay2: `xfs_info / | grep ftype`.
- For Ceph OSDs, use raw devices or LVM volumes, never files.
- Ubuntu 24.04 ships an AppArmor profile for `unprivileged_userns` that affects some nested container use cases; it does not affect rootful containerd.

## O. OS upgrade procedure

```bash
do-release-upgrade          # 22.04 -> 24.04
```

After: re-run the Ansible baseline, re-verify AppArmor profiles, then `cordon/drain` before rebooting Kubernetes nodes.

## P. Validation

```bash
aa-status
systemctl is-active chrony
timedatectl
xfs_info / | grep ftype
sysctl net.ipv4.ip_forward
apt-cache policy | grep -c nexus.internal   # expect only internal sources
sudo -u emergency sudo -n true
curl -I https://nexus.internal
```

## Q. Known Ubuntu specific traps

1. `apt` silently keeps the original `sources.list` unless it is moved aside; a node can still try to reach the internet during a package operation.
2. AppArmor blocks the container runtime from reading paths outside the profile; the failure appears as a mount error in the containerd log, not a permission denial.
3. `ufw` and `nftables` can both be active and conflict. Use exactly one.
4. 24.04's `systemd-timesyncd` must be replaced with `chrony` if uniform time config is required.
5. `unattended-upgrades` will reboot a Kubernetes node without draining it, causing disruption — disable it and patch in a window.
