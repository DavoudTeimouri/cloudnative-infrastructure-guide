# Plan: Professional guide + modular configuration sites

## Goal 1 — Professional step-by-step guide (docs/guide/)
Restructure docs into a numbered, interlinked from-scratch guide:
- 00-prerequisites (hardware, VM vs physical, air-gap)
- 01-infrastructure-prep (servers, SSH, network)
- 02-os-baseline (kernel, modules, time, DNS, disks)
- 03-container-engine (Docker/Podman air-gap)
- 04-storage-ceph (nodes, roles, pools, monitoring)
- 05-kubernetes (Kubespray, control plane, workers)
- 06-management-cluster (Rancher, Argo CD, Keycloak, Vault)
- 07-application-cluster (app clusters, sizing)
- 08-traffic-edge (LB, ingress, keepalived)
- 09-platform-services (monitoring, logging, secrets, GitOps)
- 10-backup-upgrade (Velero, Ceph recovery, Kubespray upgrades)

Each page: purpose, prerequisites, steps, validation, "next" / "prev" links, links to related ADR.

## Goal 2 — Modular configuration sites (site/modules/)
Each configuration step becomes its own self-contained site/module:
- `site/modules/ceph/` — Ceph cluster configurator (nodes, roles per node, pools)
- `site/modules/kubernetes/` — Kubespray cluster configurator
- `site/modules/traffic/` — Edge LB configurator
- `site/modules/os-baseline/` — OS baseline configurator

Each module:
- Self-contained HTML + ES5 JS (no let/const/arrow/template literals)
- Reads values from `catalog/catalog.json` (single source of truth)
- Client-side validation with inline error correction (prevent wrong configs)
- Generates a downloadable config file (YAML/JSON)
- Links back to the main guide docs

## Constraints (unchanged)
- ES5 only in site/app.js and module app.js
- Stdlib-only Python for any builder
- No network at deploy time; all from internal mirrors
- Catalog is single source of truth
- Secrets redacted as [REDACTED]

## Immediate next step
Build `site/modules/ceph/` proof of concept: node counts + per-node role assignment + validation (odd MON count, ≥3 OSD hosts for 3-replica, co-location rules). Then create `docs/guide/` index + first steps.
