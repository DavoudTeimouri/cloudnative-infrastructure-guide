# ADR-0011 — Rancher versus alternatives

- **Status**: Accepted (provisional pending Phase 1 review)
- **Date**: 2026-10-22
- **Deciders**: Platform Architect / SecOps / SRE
- **Supersedes / superseded by**: none

## Context

Multi-cluster management is required; Rancher is the named candidate.

## Requirements

See `requirements/requirements-and-assumptions.md` (R-01..R-14, D-01..D-14).

## Options considered

- 1. Rancher.
- 2. Cluster API with a management platform.
- 3. Plain kubectl plus a config repo.

## Decision

Rancher as the primary multi-cluster management plane, with Cluster API evaluated later if the fleet exceeds roughly five clusters or if declarative cluster lifecycle becomes a hard requirement.

## Rationale and trade-offs

- Familiar UI, cluster lifecycle, Fleet GitOps, mature RBAC, provisioning integrations.
- Cluster API is the upstream standard and strongly declarative.
- kubectl alone has no lifecycle story.
- Rancher gives the most usable day-2 experience with the least new machinery. Cluster API is the better long-term standard but is not needed at the current fleet size.

## Security and operational implications

Rancher requires its own cluster to run and has license tiers with feature differences that must be checked for the intended use. Cluster API introduces a bootstrap-provider dependency (ClusterClass or CAPD/CAPM3).

## Dependencies

Rancher server/agent and webhook ports, plus 6443 to managed clusters. Verify per release.

## Failure scenarios

Rancher loss does not affect workloads or Argo CD sync inside each cluster. It removes cluster registration and Fleet-based provisioning.

## Migration considerations

Switching from Rancher to Cluster API is a re-platforming of the management layer; clusters themselves survive because Argo CD and the workload state are independent.
