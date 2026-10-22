# ADR-0010 — Management Cluster design and what runs inside it

- **Status**: Accepted (provisional pending Phase 1 review)
- **Date**: 2026-10-22
- **Deciders**: Platform Architect / SecOps / SRE
- **Supersedes / superseded by**: none

## Context

The master prompt asks which platform services run in the Management Cluster and which stay outside.

## Requirements

See `requirements/requirements-and-assumptions.md` (R-01..R-14, D-01..D-14).

## Options considered

- 1. Everything platform-related in the Management Cluster.
- 2. Everything outside, on dedicated hosts.
- 3. Split by criticality.

## Decision

Split by criticality. The Management Cluster runs Rancher, Argo CD, Prometheus, Grafana, Loki, and platform dashboards. It does NOT run Vault, GitLab, the registry, or the artifact repositories — those run on dedicated infrastructure outside Kubernetes so that a cluster loss cannot remove the secrets, source, or images needed to rebuild it.

## Rationale and trade-offs

- Cluster-scoped visibility and control in one place.
- Independent services are more work to run.
- Split avoids the circular dependency of rebuilding a cluster from tools inside it.
- Keeping the restore-critical services outside the cluster is what makes the rebuild path work. The cost is running a few more plain services on dedicated hosts.

## Security and operational implications

Running Vault inside the cluster it protects is the classic circular dependency: losing the cluster can lock you out of the secrets needed to restore it.

## Dependencies

All platform service ports are in the network matrix. Cross-cluster traffic rules: Management -> Application on 6443, Argo CD -> Vault on 8200, and Application -> Harbor on 443.

## Failure scenarios

Management Cluster loss does not stop running workloads. It stops new deployments (Argo CD sync), cluster registration, and dashboards. This is the intended blast radius.

## Migration considerations

Moving a service out of the Management Cluster later is a deployment change; moving Vault out is a data migration with an unseal procedure.
