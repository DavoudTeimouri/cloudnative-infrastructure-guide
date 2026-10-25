# Cloud-Native Infrastructure Guide

Authoritative, ordered procedures for building an on-premises, air-gapped cloud-native platform from
scratch. Work the numbered steps in `docs/guide/`; each step links to its authoritative procedures.

## Step-by-step guide

| Step | Title | Source |
|---|---|---|
| 00 | Prerequisites | `docs/guide/00-prerequisites.md` |
| 01 | Infrastructure prep | `docs/guide/01-infrastructure-prep.md` |
| 02 | OS baseline | `docs/guide/02-os-baseline.md` |
| 03 | Container engine | `docs/guide/03-container-engine.md` |
| 04 | Storage — Ceph | `docs/guide/04-storage-ceph.md` |
| 05 | Kubernetes | `docs/guide/05-kubernetes.md` |
| 06 | Management cluster | `docs/guide/06-management-cluster.md` |
| 07 | Application cluster | `docs/guide/07-application-cluster.md` |
| 08 | Traffic edge | `docs/guide/08-traffic-edge.md` |
| 09 | Platform services | `docs/guide/09-platform-services.md` |
| 10 | Backup & upgrade | `docs/guide/10-backup-upgrade.md` |

[Start with the guide →](./guide/index.md)

## Authoritative procedures (linked from the guide)

- `architecture/00-overview.md` — platform overview
- `architecture/02-deployment-topology.md` — topology and sizing
- `operating-systems/host-configuration.md` — OS baseline, time, disks, users, security, per-role fields
- `storage/ceph/cephadm-deployment.md` — full Ceph ordered deployment (Docker, Podman, Cephadm)
- `kubespray/kubespray-deployment.md` — Kubespray cluster deployment
- `kubespray/multi-version-support.md` — Kubespray ≥ 5 releases in parallel
- `kubernetes/networking/cilium.md` — CNI
- `kubernetes/networking/metallb.md` — MetalLB
- `network-matrix/port-requirements.md` — ports and flows (43 rows)
- `lifecycle/backup/backup-and-dr.md` — Velero + Ceph recovery
- `lifecycle/upgrades/upgrade-procedures.md` — upgrade procedures

## Decisions

- `decisions/ADR-0015.md` — hosts never joined to AD/LDAP; local accounts + break-glass

## Source of truth

- Versions: `compatibility/version-matrix.md`
- Ports: `network-matrix/port-requirements.md`
- Catalog: `catalog/catalog.json` (drives `site/`)
- Secrets: never in Git — `[REDACTED]`
