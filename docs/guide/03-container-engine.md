# 03. Container engine

**Purpose:** Install and configure Docker or Podman on every host so it pulls container images from
the internal registry only — nothing reaches the public internet. Pick **one engine per cluster** and
never mix engines inside one cluster.

## Prerequisites
- Step 02 complete: OS baseline applied, kernel modules loaded, internal OS mirror reachable.
- Step 00.4 understood: air-gap boundary, proxy/mirror address table (`network-matrix/port-requirements.md` §C.2.0).

## Steps

### 03.1 Pick one engine per cluster
| Engine | When to use | Notes |
|---|---|---|
| Podman | Default for cephadm; used by Ceph project CI | Rootful on Ceph hosts (privileged host access needed) |
| Docker | When your site standardizes on Docker | Must run before `--docker` bootstrap |

cephadm runs every Ceph daemon as a container under the chosen engine. It will not install the engine
for you.

### 03.2 Install from the internal mirror
**Docker:**
```bash
# Oracle Linux
dnf install -y docker-ce docker-ce-cli containerd.io
# Ubuntu
apt install -y docker-ce docker-ce-cli containerd.io
systemctl enable --now docker
```

**Podman:**
```bash
# Oracle Linux
dnf install -y podman
# Ubuntu
apt install -y podman
systemctl enable --now podman.socket
```

### 03.3 Configure air-gap registry mirror
Point the engine at your internal registry (Harbor, Nexus, or self-hosted OCI).

**Docker** — `/etc/docker/daemon.json`:
```json
{
  "registry-mirrors": ["https://harbor.internal"],
  "insecure-registries": ["harbor.internal"],
  "live-restore": true,
  "storage-driver": "overlay2",
  "dns": ["10.10.0.10"],
  "iptables": false,
  "bridge": "none"
}
```

**Podman** — `/etc/containers/registries.conf`:
```ini
[registries.search]
registries = ['harbor.internal']

[registries.insecure]
registries = ['harbor.internal']

[registries.block]
registries = ['docker.io', 'quay.io', 'ghcr.io']
```

**Podman** — `/etc/containers/containers.conf`:
```ini
[containers]
dns = ["10.10.0.10"]

[storage]
driver = "overlay2"

[containers]
log_driver = "k8s-file"
log_opts = { "max-size": "100m", "max-file": "3" }
```

Restart the engine after changes:
```bash
systemctl restart docker          # Docker
systemctl restart podman.socket   # Podman
```

Verify pull works offline:
```bash
docker info | grep -i server-version          # Docker
podman info | grep -i host.version            # Podman
```

### 03.4 Air-gap network hygiene
- Set `NO_PROXY`/`no_proxy` to exclude all internal addresses so internal traffic never goes through a
  proxy: `harbor.internal`, `nexus.internal`, `registry.internal`, `10.40.0.0/24`, `10.41.0.0/24`,
  `.internal`, `localhost`, `127.0.0.1`.
- Do not open Docker's default `2375/tcp` (unencrypted Docker API).
- Do not expose the Podman API socket over TCP.

Source: `storage/ceph/cephadm-deployment.md` (section D)

## Validation
- [ ] Engine installed from internal mirror on every host.
- [ ] `docker info` / `podman info` reports the engine version.
- [ ] Engine pulls an image from `harbor.internal` successfully (offline).
- [ ] Public registries (`docker.io`, `quay.io`, `ghcr.io`) are unreachable or blocked on Ceph hosts.
- [ ] Same engine chosen for the whole cluster (no mixing).

## Navigation
**[← Prev · 02. OS baseline](./02-os-baseline.md)** | **[Next → 04. Storage — Ceph](./04-storage-ceph.md)**
