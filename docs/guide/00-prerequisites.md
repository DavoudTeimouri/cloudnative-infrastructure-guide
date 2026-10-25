# 00. Prerequisites

**Purpose:** Size the site, choose bare metal vs VM, define the air-gap boundary and network segments,
and confirm what must exist before any server is touched.

## Prerequisites
None — this is the first step. You need:
- Access to the hardware/hypervisor where hosts will be provisioned.
- A connected build machine (for mirroring images/packages before air-gap).
- Decisions on OS (Oracle Linux 9 or Ubuntu 24.04) and Kubespray release.

## Steps

### 00.1 Choose deployment model: bare metal or VM
| Concern | Bare metal | Virtual machine |
|---|---|---|
| Ceph OSD | Recommended; direct disk, predictable latency | Acceptable with raw/SCSI-passthrough disks; never shared virtual disk |
| MON / MGR / OSD | Local SSD for MON store and OSD DB/WAL | Local SSD + dedicated vCPUs; never shared storage |
| Failure domain | Physical host | Host + hypervisor + storage array |
| Disk passthrough | N/A (native) | Required for Ceph OSD data disks; shared virtual disks break replication |

Source: `architecture/02-deployment-topology.md`

### 00.2 Size the site
Use the reference sizing below. Adjust counts to your workload; do not go below the production minimum.

| Role | Count (ref) | Min (prod) | Required? | Notes |
|---|---|---|---|---|
| Automation Management Server | 1 (+1 standby) | 1 | Yes | Ansible, AWX, GitLab runner. Not a K8s node |
| Management control-plane | 3 | 3 | Yes | Rancher, Argo CD, Keycloak, Prometheus |
| Management infra workers | 3 | 2 | Yes | System + platform add-ons, no app workloads |
| Application control-plane | 3 | 3 | Yes | Per cluster |
| Application workers (general) | N | 2 | Yes | App workloads |
| Storage workers (Ceph OSD) | 3+ | 3 | Yes | Ceph OSD hosts |
| Artifact/registry services | 2 | 1 | Yes | Harbor + Nexus |
| GitLab | 2 | 1 | Yes | Stateful — back up |
| Identity (Keycloak) | 2 | 1 | Yes | External DB strongly preferred |
| Vault | 3 | 1 | Yes | Standalone, Raft, offline unseal |
| NTP / DNS | 2 | 1 | Yes | chrony; CoreDNS + external |
| Load balancer (edge) | 2 | 2 | Yes | HAProxy + Nginx + Keepalived |

Source: `architecture/02-deployment-topology.md`

**Consolidation risk:** Do not put storage + control plane on one host; do not run Vault inside the
cluster it protects; do not put a GitLab runner on a control-plane node; do not run the identity
provider in the same cluster that consumes its secrets.

### 00.3 Define network segments
| Segment | Purpose | Typical CIDR (provisional) |
|---|---|---|
| mgmt | SSH, Ansible, monitoring, GitLab, registry, Vault, identity | 10.10.0.0/24 |
| control-plane | kube-apiserver, etcd peer/client, CNI control | 10.20.0.0/24 |
| pod | Pod CIDR per cluster (Cilium native routing) | 10.30.0.0/16, 10.31.0.0/16 |
| service | ClusterIP range | 10.32.0.0/16, 10.33.0.0/16 |
| storage | Ceph public + cluster networks | 10.40.0.0/24 + 10.41.0.0/24 |
| gpu | GPU worker mgmt + fabric | 10.50.0.0/24 |
| dmz | External LB VIP, ingress, reverse proxy | 10.60.0.0/24 |
| nodeport | 30000-32767 or MetalLB pool | PROVISIONAL |

Verify every CIDR against your site plan before build. All ports/flows:
`network-matrix/port-requirements.md`

### 00.4 Air-gap boundary
- No host may reach the public internet at deploy time.
- All images, packages, Helm charts, and OS repos must be mirrored to internal registries/repos
  (Harbor, Nexus, or self-hosted OCI) on a connected machine first.
- See step 03 for container-engine mirroring and `network-matrix/port-requirements.md` for the
  proxy/mirror address table.

## Validation
- [ ] Host count per role meets the production minimum.
- [ ] CIDRs assigned and documented (no overlaps).
- [ ] Connected build machine identified for mirroring.
- [ ] Air-gap boundary confirmed: no host has a route to the public internet.

## Navigation
**[Next → 01. Infrastructure prep](./01-infrastructure-prep.md)**
