# 01. Infrastructure prep

**Purpose:** Provision and reach every host, set up passwordless SSH access, the break-glass key,
time sync, and name resolution before any OS configuration.

## Prerequisites
- Step 00 complete: hosts sized, network segments chosen, air-gap boundary understood.

## Steps

### 01.1 Provision hosts
Provision one host per planned role (see step 00.2). Record name, IP, MAC, and BMC/IPMI address for
each. Every host must be reachable from the bootstrap/automation host over SSH.

Source: `architecture/02-deployment-topology.md`

### 01.2 SSH access (service user, not root)
SSH as a non-root deploy user (e.g. `cephadm` or `ansible`) with passwordless `sudo` is preferred over
direct root login. cephadm and Ansible elevate via `sudo` when needed. This user is a **local** account
on each host — not a directory account.

```bash
# From the bootstrap host, as the deploy user
ssh deploy@ceph-mon-1 'hostname'
ssh deploy@ceph-mon-1 'sudo hostname'

# On each host, allow passwordless sudo for the deploy user
echo "deploy ALL=(ALL) NOPASSWD:ALL" | sudo tee /etc/sudoers.d/deploy

# Install the same SSH public key (break-glass key) on every host
ssh-copy-id deploy@ceph-mon-1
ssh-copy-id deploy@ceph-mon-2
ssh-copy-id deploy@ceph-mon-3
```

Verify:
```bash
ssh deploy@ceph-mon-1 'sudo cephadm --version'
```

**AD authentication:** Hosts must NOT be joined to Active Directory/LDAP (ADR-0015). Identity is
application-layer only; nodes keep local accounts plus an offline break-glass key. Do not rely on
AD/Kerberos for SSH access.

### 01.3 Break-glass key
Install the offline break-glass public key for `root` (or the deploy user) on every host. Store the
private half offline — not in Git, not in Vault alone. It is the only access path that survives a
directory outage, Vault outage, or broken Keycloak.

### 01.4 Time synchronization (chrony)
All hosts must agree on time; monitor quorum (Ceph) and etcd leadership depend on it. Use internal NTP
sources only — at least two, preferably three on different switches.

```bash
chronyc sources -v
chronyc tracking
```

### 01.5 Name resolution
Every host must resolve every other host by name.

- **With DNS:** confirm from each host:
  ```bash
  getent hosts ceph-mon-1 ceph-mon-2 ceph-mon-3 ceph-osd-1
  ```
- **Without DNS:** maintain an identical `/etc/hosts` on every host:
  ```bash
  cat >> /etc/hosts <<'EOF'
  10.40.0.11  ceph-mon-1
  10.40.0.12  ceph-mon-2
  10.40.0.13  ceph-mon-3
  10.40.0.14  ceph-osd-1
  EOF
  ```

## Validation
- [ ] Every host reachable via SSH as the deploy user with passwordless sudo.
- [ ] Break-glass public key installed on every host; private half stored offline.
- [ ] `chronyc sources -v` shows synced internal NTP sources on every host.
- [ ] `getent hosts` (or identical `/etc/hosts`) resolves all hostnames from every host.
- [ ] No host joined to AD/LDAP (ADR-0015).

## Navigation
**[← Prev · 00. Prerequisites](./00-prerequisites.md)** | **[Next → 02. OS baseline](./02-os-baseline.md)**
