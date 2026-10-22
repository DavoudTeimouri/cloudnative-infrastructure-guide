# ADR-0026 — Kubespray multi-version support

- **Status**: Accepted (provisional pending Phase 1 review)
- **Date**: 2026-10-22
- **Deciders**: Platform Architect / SecOps / SRE
- **Supersedes / superseded by**: none

## Context

A single pinned Kubespray release is a single point of failure. It pins one Kubernetes, etcd, containerd, CNI and Helm set, and when that release ages out, or when a site needs a Kubernetes version it cannot deploy, the whole estate is blocked on one upgrade. Kubespray maintains parallel release branches, each with its own pinned component versions and its own Ansible and Python compatibility window.

## Requirements

See `requirements/requirements-and-assumptions.md` (R-01..R-14, D-01..D-14).

## Options considered

- 1. Support exactly one Kubespray release, the newest.
- 2. Support three Kubespray releases.
- 3. Support five Kubespray releases in parallel, each fully deployable and offline-capable.

## Decision

Support five Kubespray release branches in parallel: release-2.28 through release-2.32. Each release gets its own checkout, its own Python virtualenv, its own inventory directory, and its own mirrored artifact set. A cluster is bound to the release that built it, and that binding is recorded in the inventory.

## Rationale and trade-offs

- Covers five consecutive Kubernetes minor versions, so a cluster that must stay on an older version is still deployable and still rebuildable.
- A release leaves the supported set only when a fifth successor exists, which keeps the set at five.
- Each release is a complete configuration, so a rebuild on an older pinned combination is possible.
- Five virtualenvs, five artifact trees and five inventories is a real maintenance cost, and the offline mirror size grows accordingly.
- Mixing component versions across releases is not supported, so the inventory must not be shared between them.

## Security and operational implications

Each release's artifacts must be mirrored and pull-verified independently, because the image sets differ per Kubernetes and containerd version. A release that is not mirrored cannot be used to rebuild a cluster, which defeats the purpose of keeping it supported.

## Dependencies

Five Kubespray checkouts, five virtualenvs with different Ansible versions, five inventory trees, five files_repo trees, and five Harbor projects. The artifact matrix gains one row set per release.

## Failure scenarios

A cluster moves one Kubernetes minor at a time, using the next-newer release's inventory and virtualenv. Rebuilding a cluster on an older release is a matter of pointing at that release's checkout, inventory and venv, with the same group vars.

## Migration considerations

The supported set is reduced when a Kubernetes version inside it reaches end of life, or when a critical CVE in a pinned Kubernetes version forces an early exit. Either case is recorded as an ADR amendment with the reason and the date.
