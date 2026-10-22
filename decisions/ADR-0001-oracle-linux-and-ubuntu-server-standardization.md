# ADR-0001 — Oracle Linux and Ubuntu Server standardization

- **Status**: Accepted (provisional pending Phase 1 review)
- **Date**: 2026-10-22
- **Deciders**: Platform Architect / SecOps / SRE
- **Supersedes / superseded by**: none

## Context

Both are required by the master prompt. Full standardization on one distro would reduce test surface but conflicts with the stated requirement and with hardware/support realities (GPU driver availability, enterprise support contracts).

## Requirements

See `requirements/requirements-and-assumptions.md` (R-01..R-14, D-01..D-14).

## Options considered

- 1. Support both with a shared control plane, but keep OS-specific playbooks separate.
- 2. Standardize on one distro and mirror it elsewhere.
- 3. Standardize on one and drop the other.

## Decision

Support both. Common automation is factored into shared roles; distro-specific behaviour lives in separate role directories with distinct package names, paths, security modules, and service managers.

## Rationale and trade-offs

- Boring: one control plane, two well-tested variants.
- Twice the OS test surface.
- SELinux vs AppArmor both need policy work.

## Security and operational implications

Security posture differs: SELinux is more granular and blocks more by default (container runtimes need explicit labeling); AppArmor is path-based, more permissive by default, easier to break silently.

## Dependencies

Ubuntu 22.04/24.04 LTS and Oracle Linux 8/9 (both have long support windows; exact supported releases must be confirmed against Kubespray's supported-OS list at the pinned release).

## Failure scenarios

A node built for one distro is not portable to the other without a rebuild. Nodes are disposable and rebuilt by Ansible, so a rebuild is a routine operation, not an incident.

## Migration considerations

Standardization on a single distro would halve OS-level test effort, but drops a mandated platform and risks unsupported hardware paths. The mitigation is a shared-role factoring discipline.
