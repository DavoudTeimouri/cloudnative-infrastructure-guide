# ADR-0013 — GitLab runner architecture

- **Status**: Accepted (provisional pending Phase 1 review)
- **Date**: 2026-10-22
- **Deciders**: Platform Architect / SecOps / SRE
- **Supersedes / superseded by**: none

## Context

CI must not endanger the clusters or the registries it deploys to.

## Requirements

See `requirements/requirements-and-assumptions.md` (R-01..R-14, D-01..D-14).

## Options considered

- 1. Shell runner on the automation server.
- 2. Docker runner on the automation server.
- 3. Kubernetes runner inside the cluster.
- 4. Dedicated VM runner.

## Decision

Docker executor on the automation server for build and unit stages, plus a Kubernetes executor in a dedicated `ci` namespace with namespace-scoped service accounts for integration and deploy stages. No shell executor for anything that touches a cluster, and never a runner on a control-plane node.

## Rationale and trade-offs

- Isolation without a second virtualization layer.
- Real pod isolation for cluster jobs.
- A VM runner isolates the host.
- Docker on the automation server is the simplest isolation that still protects the host. The cluster runner is scoped and separated so a CI job cannot reach production namespaces.

## Security and operational implications

A cluster runner needs an agent token with cluster-scoped power; a misconfigured CI job can then read the whole cluster. The `ci` namespace and a scoped service account reduce that.

## Dependencies

Runner -> GitLab 443, runner -> GitLabLab API, runner -> K8s API 6443, runner -> Harbor 443. All in the network matrix.

## Failure scenarios

A compromised runner that holds a cluster-admin token can read every Secret in the cluster. Keep runner tokens short-lived where possible and scope them.

## Migration considerations

Changing runner type means re-registering runners and updating job tags. Low risk, small operational cost.
