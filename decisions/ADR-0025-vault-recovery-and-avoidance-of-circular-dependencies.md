# ADR-0025 — Vault recovery and avoidance of circular dependencies

- **Status**: Accepted (provisional pending Phase 1 review)
- **Date**: 2026-10-22
- **Deciders**: Platform Architect / SecOps / SRE
- **Supersedes / superseded by**: none

## Context

The restore path must work when the cluster, the identity provider, and the network are all in a bad state.

## Requirements

See `requirements/requirements-and-assumptions.md` (R-01..R-14, D-01..D-14).

## Options considered

- 1. Vault inside the Management Cluster, unsealed with a KMS inside the same cluster.
- 2. Vault on dedicated hosts with offline Shamir shares.
- 3. Vault with a cloud KMS auto-unseal.

## Decision

Vault on dedicated hosts with offline Shamir key shares (or an external HSM/KMS that is not in the cluster). Restore order is fixed: Vault first, then identity, then the Management Cluster, then Application Clusters. Argo CD is never the only path to restore a cluster it manages.

## Rationale and trade-offs

- The unseal path does not depend on anything that can be lost in the incident.
- The restore path is not circular.
- Manual unseal is slower than auto-unseal but has no infrastructure dependency.
- The whole point of the architecture is that a total loss is recoverable with a documented sequence of manual steps and offline material. Every other design choice is subordinate to that.

## Security and operational implications

Manual unseal needs a documented, practiced procedure with a quorum of custodians. It is a human process during an incident, which is exactly when human processes fail. Auto-unseal needs a KMS outside the cluster, which adds a dependency but removes the human step.

## Dependencies

Vault 8200 for the API, 8201/8202 for cluster communication, plus the KMS endpoint if auto-unseal is used.

## Failure scenarios

An extended Vault outage stops secret renewal. Certificates expiring during the outage, and applications that read secrets only at startup, are the two hard failure modes to test.

## Migration considerations

Restoring a Vault cluster from a snapshot requires the storage snapshot plus the unseal material plus the root token, and they must come from different places. Vault backup and Kubernetes backup are separate procedures; a Velero backup does not include Vault data in this model.
