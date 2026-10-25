# Cloud-Native Infrastructure Guide — Step-by-Step

Build an on-premises, air-gapped cloud-native platform from scratch. Each page is one configuration
step, in order, with prerequisites, commands, validation, and links to the authoritative documents.

The platform: **Oracle Linux 9 / Ubuntu 24.04** hosts, **Kubespray** Kubernetes (5 releases in parallel),
**Ceph** (cephadm on dedicated hosts or Rook in-cluster), **Rancher** management cluster + independent
application clusters, **Keycloak** identity (no host AD join), **Vault** secrets, **Harbor**+**Nexus**
artifacts, **external HAProxy/Nginx+Keepalived** edge, **Cilium** CNI.

> All versions are pinned in `compatibility/version-matrix.md`. All ports/flows are in
> `network-matrix/port-requirements.md`. Secrets are never in Git — they are `[REDACTED]` here and
> injected from Vault at deploy time.

## The ten steps

| Step | Title | What you produce |
|---|---|---|
| [00. Prerequisites](./00-prerequisites.md) | Hardware, VM vs physical, air-gap, network segments | Site sizing and network plan |
| [01. Infrastructure prep](./01-infrastructure-prep.md) | Servers, SSH, break-glass, time, DNS | Reachable, time-synced hosts |
| [02. OS baseline](./02-os-baseline.md) | Kernel, modules, users, disks, filesystems | Hardened OS on every host |
| [03. Container engine](./03-container-engine.md) | Docker or Podman, air-gap registry mirror | Engine pulling from internal registry |
| [04. Storage — Ceph](./04-storage-ceph.md) | Nodes, roles per node, OSDs, pools, monitoring | Ceph cluster ready for CSI |
| [05. Kubernetes](./05-kubernetes.md) | Kubespray, control plane, workers, CNI | Application Kubernetes cluster |
| [06. Management cluster](./06-management-cluster.md) | Rancher, Argo CD, Keycloak, Vault | Platform control plane |
| [07. Application cluster](./07-application-cluster.md) | App clusters, sizing, Windows workers | Workload clusters |
| [08. Traffic edge](./08-traffic-edge.md) | External LB, ingress, Keepalived, VIPs | Client-facing entry point |
| [09. Platform services](./09-platform-services.md) | Monitoring, logging, GitOps, add-ons | Observable, operated platform |
| [10. Backup & upgrade](./10-backup-upgrade.md) | Velero, Ceph recovery, Kubespray upgrades | Recoverable, updatable platform |

## How to use this guide

1. Work the steps **in order**. Each step lists its prerequisites — do not skip ahead.
2. Follow the links to the **authoritative documents** for the full procedures; this guide is the
   ordered walkthrough, not a replacement for them.
3. Run the **validation** commands at the end of each step before proceeding. A failed validation
   means the platform is not ready for the next step.
4. All values (versions, CIDRs, ports) come from the repository sources, never from this guide alone.

## Source of truth

| Artifact | Location | Purpose |
|---|---|---|
| Procedures (authoritative) | `docs/` and subdirectories | Full step-by-step procedures |
| Decisions/reasoning | `decisions/ADR-*.md` | Why each choice was made |
| Versions | `compatibility/version-matrix.md` | Pinned, VERIFIED component versions |
| Ports/flows | `network-matrix/port-requirements.md` | Firewall / access rules |
| Site configurator | `site/` | Interactive wizard that generates this plan |
| Ceph module | `site/modules/ceph/` | Self-contained Ceph node/role/pool configurator |
