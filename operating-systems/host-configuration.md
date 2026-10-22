# Host configuration inputs

Every host setting the configurator exposes, what it changes, and the check that proves it. Distro
differences are shown per item. The generated `10-os-baseline.sh` applies this list in order; this
document explains each line so an operator can review it before running it.

Scope: nodes only. Identity is application-level (ADR-0015) — there is no SSSD, realmd or AD join
in this baseline.

## 1. Identity and access

| Input | Effect | Oracle Linux 9 | Ubuntu 24.04 | Verify |
|---|---|---|---|---|
| `adminUser` | The only non-root account with sudo | `useradd -m -G wheel` | `useradd -m -G sudo` | `id <user>` |
| `sshPort` | SSH listener port | `/etc/ssh/sshd_config.d/10-hardening.conf` | same | `ss -ltnp \| grep <port>` |
| `sshPasswordAuth` | Password login (off by default) | `PasswordAuthentication no` | same | `sshd -T \| grep passwordauthentication` |
| `sudoNopasswd` | Passwordless sudo for automation | `/etc/sudoers.d/90-automation` | same | `sudo -n true` |
| `breakGlassKey` | Offline public key, installed for `root` | `authorized_keys`, mode 0600 | same | `ssh -i <key> root@node` |

The break-glass key is not optional. It is the only access path that survives a directory outage, a
Vault outage and a broken Keycloak. Store the private half offline, not in Git and not in Vault
alone.

`sudoNopasswd` is for the Ansible account only, never for the human admin account: passwordless
sudo on a shared account removes the last audit signal.

## 2. Time and locale

| Input | Effect | Both distros | Verify |
|---|---|---|---|
| `osTimezone` | System timezone, and the timezone every log line is written in | `timedatectl set-timezone <tz>` | `timedatectl` |
| `ntpServers` | Chrony sources; comma-separated, internal servers only | `/etc/chrony.conf` → `server <ip> iburst prefer` | `chronyc sources -v` |
| `osLocale` | Locale for tooling output consistency | `localectl set-locale LANG=en_US.UTF-8` | `locale` |

Clock skew breaks etcd (it refuses leadership churn beyond the election timeout), TLS validity,
Kerberos-less OIDC token validation and Ceph monitor quorum. Two internal NTP sources minimum, and
a third that is not on the same switch as the first two.

## 3. Name resolution

| Input | Effect | Both distros | Verify |
|---|---|---|---|
| `dnsServers` | Resolver list, internal DNS first | `nmcli con mod <con> ipv4.dns "<ip1> <ip2>"` | `resolvectl status` or `cat /etc/resolv.conf` |
| `dnsSearchDomain` | Search suffix | `ipv4.dns-search` | `resolvectl domain` |
| `dnsOverTls` | Disable DoT for the internal resolver | `systemd-resolved` off on Oracle Linux | `resolvectl status \| grep -i '+DNSOverTLS'` |

Kubernetes resolves service names through CoreDNS, but the kubelet, the container runtime and the
CSI driver resolve the registry and the Ceph monitors through the host resolver. A host that cannot
resolve `harbor.internal` fails image pulls even though the cluster DNS is healthy.

## 4. Kernel and memory

| Input | Effect | Both distros | Verify |
|---|---|---|---|
| `swapDisabled` | `swapoff -a` and a persistent mask; kubelet requires it | `swapoff -a`, comment the fstab line | `swapon --show` (empty) |
| `transparentHugePages` | `madvise` for latency-sensitive workloads, `never` for Ceph OSDs | `/sys/kernel/mm/transparent_hugepage/enabled` | `cat /sys/.../enabled` |
| `vmMaxMapCount` | Elasticsearch, Trivy and many JVM workloads need 262144+ | `vm.max_map_count=262144` | `sysctl vm.max_map_count` |
| `fileDescriptorsMax` | 1048576 for the kubelet, containerd and Ceph | `fs.file-max`, `LimitNOFILE` drop-in | `ulimit -n` in the unit |
| `pidMax` | 4194304; container churn exhausts the default | `kernel.pid_max` | `sysctl kernel.pid_max` |
| `kernelModules` | `overlay`, `br_netfilter`, `nf_conntrack`, `rbd` | `/etc/modules-load.d/` | `lsmod \| grep br_netfilter` |
| `kernelArgs` | Extra boot parameters (hugepages, IOMMU for GPU passthrough) | `grubby --update-kernel=ALL --args=` | `cat /proc/cmdline` |

Ceph OSD hosts: `transparent_hugepage=never` and `vm.swappiness=1`. A THP stall shows up as
`slow ops` in `ceph -s`, not as a CPU problem, which is why it is set before the OSD exists.

GPU hosts: `intel_iommu=on iommu=pt` in `kernelArgs` when the card is passed through, and
`pci=realloc` on some firmware. Reboot required; the generated script marks that step.

## 5. Limits and scheduling

| Input | Effect | Where | Verify |
|---|---|---|---|
| `maxPodsPerNode` | kubelet `--max-pods`; the CNI's IP pool must cover it | Kubespray `kubelet_max_pods` | `kubectl describe node \| grep -i pods` |
| `cpuManagerPolicy` | `static` pins guaranteed pods to cores | kubelet config | `cat /var/lib/kubelet/config.yaml` |
| `topologyManagerPolicy` | `best-effort` or `restricted` for GPU/NUMA | kubelet config | same |
| `reservedSystemCpu` | `--system-reserved` so the node does not starve | kubelet config | `kubectl describe node` Allocatable |

With `cpuManagerPolicy: static`, only pods in the Guaranteed QoS class get exclusive cores. Mixed
policy without Guaranteed requests gives the illusion of pinning with none of the isolation.

## 6. Security baseline

| Input | Effect | Oracle Linux 9 | Ubuntu 24.04 | Verify |
|---|---|---|---|---|
| `selinuxMode` | `enforcing` (default) or `permissive` during a migration | `/etc/selinux/config` | AppArmor instead | `getenforce` |
| `firewallBackend` | `firewalld`, `nftables` or `none` | `firewalld` | `ufw` or `nftables` | `firewall-cmd --state` |
| `auditRetentionDays` | auditd retention and rotation | `/etc/audit/auditd.conf` | same | `auditctl -s` |
| `unattendedSecurityUpdates` | Nightly security-only updates | `dnf-automatic` | `unattended-upgrades` | `systemctl status dnf-automatic.timer` |
| `sshCiphers` | Restrict to the approved set | `sshd_config.d` | same | `ssh -Q cipher` |

Unattended upgrades on a Kubernetes node are a trade-off: they close CVEs without a maintenance
window, and they change packages under a running kubelet. The platform's position is security-only
updates with `dnf-automatic`/`unattended-upgrades`, a reboot window, and a node drain before the
reboot. Not a silent reboot at 03:00.

## 7. Container runtime prerequisites

| Input | Effect | Verify |
|---|---|---|
| `containerdVersion` | Pinned by the Kubespray release; do not hand-install | `containerd --version` |
| `registryMirrors` | `registries.yaml` mirror + auth for the internal registry | `crictl pull <image>` |
| `insecureRegistries` | Only for a registry whose CA cannot be distributed | `crictl pull` succeeds |
| `cgroupDriver` | `systemd`, matching kubelet | `cat /etc/containerd/config.toml \| grep SystemdCgroup` |

`insecureRegistries` is a last resort. If the internal CA is installed in the host trust store,
there is no reason to disable verification: the generated preflight checks the chain instead.

## 8. What the generated script does not do

- It does not partition disks. Disk layout is a per-site decision and stays manual.
- It does not join a directory. That is intentional (ADR-0015).
- It does not reboot. Kernel arguments and hugepages need one, and the operator decides when.
- It does not open ports beyond the network matrix. The matrix is the authority.

## Verify a host after the baseline

```bash
timedatectl
chronyc tracking
swapon --show
sysctl vm.max_map_count fs.file-max kernel.pid_max
getenforce || aa-status --enabled
firewall-cmd --list-all || nft list ruleset | head
crictl info | head -5
```

A host that fails any of these is not ready for Kubespray, regardless of what the playbook says.
