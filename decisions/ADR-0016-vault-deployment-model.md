# ADR-0016 — Vault deployment model

- **Status**: Accepted (provisional pending Phase 1 review)
- **Date**: 2026-10-22
- **Deciders**: Platform Architect / SecOps / SRE
- **Supersedes / superseded by**: none

## Context

Secrets must survive the loss of the cluster they protect.

## Requirements

See `requirements/requirements-and-assumptions.md` (R-01..R-14, D-01..D-14).

## Options considered

- 1. Inside the Management Cluster.
- 2. Inside a dedicated separate Kubernetes cluster.
- 3. On dedicated Linux hosts.

## Decision

On dedicated Linux hosts, 3 nodes, integrated Raft storage. Unseal material held offline. Vault is never deployed inside the Management Cluster.

## Rationale and trade-offs

- Independent of every cluster failure.
- No admission or scheduling problems.
- Manual HA management, no Helm chart.
- Host deployment is the only model that has no circular dependency with the cluster. The cost is a small amount of manual HA configuration that Ansible absorbs.

## Security and operational implications

Running Vault in-cluster means a cluster outage can lock you out of the secrets needed to restore it. The unseal path would depend on the same infrastructure that failed.

## Dependencies

8200 (API), 8201 (cluster, raft), 8202 (HA redirect/clustering), plus the unseal/KMS endpoint. Verify per release.

## Failure scenarios

Vault down means: no new secret issuance, no rotation, no certificate renewal. Running workloads are unaffected unless they read secrets at startup. Applications that need renewed secrets will fail on the next renewal cycle unless they can tolerate the outage.

## Migration considerations

Migrating Vault from hosts into a cluster is a supported but non-trivial move involving the storage backend and the unseal configuration. Keep the host deployment as the long-term state.
