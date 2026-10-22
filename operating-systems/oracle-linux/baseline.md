# Oracle Linux baseline

Distro-specific. Do not copy Ubuntu commands here.

## A. Purpose and scope

Baseline for Oracle Linux 8 and 9 nodes running Kubernetes, Ceph, GitLab, Harbor, Nexus, Vault, and GPU workloads.

Supported releases: Oracle Linux 8 and 9 (both have long support lifetimes). Exact kernel and minor-version support for Kubespray must be confirmed against the pinned Kubespray release's supported-OS list — record the check in `compatibility/version-matrix.md`.

## B. Key differences from Ubuntu

| Area | Oracle Linux | Ubuntu |
|---|---|---|
| Package manager | `dnf` / `yum` | `apt` / `dpkg` |
| Release codename | none (numeric) | jammy, noble |
| Mandatory access control | SELinux, enforcing by default | AppArmor, enforcing by default |
| Firewall | `firewalld` | `ufw` (often disabled) |
| Container storage driver | `overlay2` with `overlay2` on XFS with `ftype=1` | same |
| Kernel default | Oracle UEK, or RHCK | Ubuntu generic kernel |
| System roles | `dnf install ansible-core` available | `apt install ansible` available |
| Python default | 3.6/3.9 (varies by release) | 3.10/3.12 |
| Certificate trust | `/etc/pki/ca-trust/source/anchors/` + `update-ca-trust` | `/usr/local/share/ca-certificates/` + `update-ca-certificates` |
| Repo file format | INI with `baseurl` | one-line `.sources` deb822 (newer) or legacy list |
| Time service | `chronyd` | `systemd-timesyncd` or `chrony` |
| Volume groups | LVM (`vgs`, `pvs`) | LVM optional |
| Upgrade model | `dnf upgrade` with leapp for major versions | `do-release-upgrade` for major versions |

## C. Repository configuration (offline)

```bash
# /etc/yum.repos.d/internal.repo
[internal-base]
name=Internal Oracle Linux base
baseurl=https://nexus.internal/repository/rpm-oraclelinux/8/BaseOS/x86_64/os/
enabled=1
gpgcheck=1
gpgkey=https://nexus.internal/repository/rpm-oraclelinux/keys/ol8.key
sslverify=1
sslcafile=/etc/pki/ca-trust/source/anchors/internal-ca.crt
```

Oracle Linux 8 UEK repos (`ol8_codeready`, `ol8_addons`, `ol8_baseos_latest`) and Oracle Linux 9 equivalents must be mirrored. For RHEL-compatible content, a Red Hat subscription or Satellite is required — entitlement content cannot be mirrored without a licence. Verify the exact repo IDs for the chosen release.

GPG key import:

```bash
curl -fsSL https://nexus.internal/repository/rpm-oraclelinux/keys/ol8.key \
  | gpg --dearmor -o /etc/pki/rpm-gpg/RPM-GPG-KEY-internal
rpm --import /etc/pki/rpm-gpg/RPM-GPG-KEY-internal
```

## D. SELinux

Container runtimes need container SELinux policy installed. Without it, container volumes are mislabelled and the runtime either refuses to run or runs unconfined.

```bash
# Check state
getenforce
sestatus

# Container policy (RHEL-compatible repos)
dnf install container-selinux selinux-policy selinux-policy-targeted

# Persistent permissive for a specific binary (avoid global permissive)
semanage fcontext -a -t container_file_t "/var/lib/ceph(/.*)?"
restorecon -Rv /var/lib/ceph

# Docker/containerd with SELinux
# containerd reads SELinux contexts; Ceph OSD dirs need container_file_t
```

Policy notes:
- Never set `SELINUX=disabled` to "fix" a permission problem. Use the correct context type.
- SELinux denials are logged in `/var/log/audit/audit.log`; use `ausearch -m AVC -ts recent`.
- Put auditd logs into the central logging pipeline; AVC denials are the primary evidence for container runtime issues.

```bash
# Find the right type for a path
semanage fcontext -l | grep -i ceph
```

## E. Sysctl and modules

```bash
# /etc/modules-load.d/k8s.conf
br_netfilter
overlay
```

```bash
# /etc/sysctl.d/99-kubernetes.conf
net.bridge.bridge-nf-call-iptables  = 1
net.bridge.bridge-nf-call-ip6tables = 1
net.ipv4.ip_forward                 = 1
net.ipv4.conf.all.rp_filter         = 1
net.ipv4.tcp_keepalive_time         = 600
net.ipv4.tcp_keepalive_intvl        = 30
net.ipv4.tcp_keepalive_probes       = 10
fs.inotify.max_user_instances       = 8192
fs.inotify.max_user_watches         = 524288
fs.file-max                         = 1048576
vm.max_map_count                    = 262144
vm.swappiness                       = 1
vm.overcommit_memory                = 1
net.core.somaxconn                 = 32768
```

Container runtime requirements (verify against the pinned containerd release notes):

```bash
# XFS with ftype=1 required for overlay2
xfs_info / | grep ftype

# br_netfilter
sysctl net.bridge.bridge-nf-call-iptables
```

## F. Swap

```bash
swapoff -a
sed -i '/\sswap\s/s/^/#/' /etc/fstab
```

Kubernetes requires swap off unless a cgroup v2 swap feature is explicitly enabled and validated.

## G. Time sync

```bash
dnf install chrony
systemctl enable --now chronyd
chronyc tracking
chronyc sources -v
```

Point chrony at the internal NTP source; do not use public pools in an offline environment.

## H. Firewall

```bash
dnf install firewalld
systemctl enable --now firewalld
firewall-cmd --list-all
firewall-cmd --permanent --add-port=6443/tcp
firewall-cmd --reload
```

Firewalld is the default on Oracle Linux. Rule generation from the network matrix: `network-matrix/firewall-rules-generation.md`.

## I. Package and repo hardening

```bash
dnf install dnf-plugins-core
dnf config-manager --set-disabled "*" --save-config=disabled-repos
dnf config-manager --set-enabled internal-base internal-appstream
```

Disable all unmirrored repos so a node can never reach out.

## J. SSH hardening

`/etc/ssh/sshd_config.d/50-hardening.conf`:

```
PermitRootLogin no
PasswordAuthentication no
KbdInteractiveAuthentication no
PubkeyAuthentication yes
X11Forwarding no
AllowAgentForwarding no
MaxAuthTries 3
ClientAliveInterval 300
```

Break-glass: a local `emergency` account with a key held offline, and `sudo` membership.

```bash
useradd -m -s /bin/bash emergency
usermod -aG wheel emergency
```

## K. Audit and logging

```bash
dnf install auditd audispd-plugins
systemctl enable --now auditd
```

Audit rules for container runtime and SSH:

```
-w /etc/ssh/sshd_config -p wa -k sshd_config
-w /etc/passwd -p wa -k identity
-w /etc/sudoers -p wa -k sudoers
-w /var/lib/ceph -p wa -k ceph
```

Ship `/var/log/audit/audit.log` to the central log collector; it is the primary security evidence source.

## L. Certificate trust

```bash
cp internal-ca.crt /etc/pki/ca-trust/source/anchors/
update-ca-trust
# verify
openssl verify -CApath /etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem internal-ca.crt
```

## M. Monitoring and logging agents

Install node_exporter and Fluent Bit from the internal repositories via Ansible. Service names differ from Ubuntu only in unit naming conventions; the packages are the same upstream tarballs.

## N. Filesystem and storage notes

- Ceph OSD: one partition per device, `ceph-volume` manages it. Use raw devices or LVM-backed volumes; do not use a plain file.
- XFS requires `ftype=1` for overlay2.
- For etcd, use a dedicated local disk, not a shared filesystem.

## O. OS upgrade procedure

Major release upgrade: use `leapp` with the supported upgrade path, in a canary node first, then the rest. Minor: `dnf upgrade` with a reboot and a Kubespray re-run afterwards.

Post-upgrade: re-run the Ansible baseline, confirm `node_exporter` and `chronyd` are running, then `kubectl cordon/drain` before rebooting a Kubernetes node.

## P. Validation

```bash
getenforce                       # expect Enforcing
systemctl is-active chronyd
timedatectl
xfs_info / | grep ftype          # expect ftype=1
sysctl net.ipv4.ip_forward       # expect 1
dnf repolist --enabled           # expect only internal repos
curl -I https://nexus.internal    # expect 200/401 from internal TLS
sudo -u emergency sudo -n true   # expect success (break-glass works)
```

## Q. Known Oracle Linux specific traps

1. `dnf` may hang on unreachable repos in an air-gapped network — every repo must be internal or disabled.
2. SELinux blocks container volume access when the path is not labelled `container_file_t`; the symptom is the runtime failing to mount, not a permission error.
3. `firewalld` by default blocks the pod/service CIDR traffic needed for CNI; add the pod and service networks explicitly or trust the internal interface.
4. Oracle Linux ships a Python version that may be older than the Ansible controller requirement — use a virtualenv.
5. RHEL-compatible packages under Oracle Linux ULN have different GPG keys; import the correct key for the repository.
