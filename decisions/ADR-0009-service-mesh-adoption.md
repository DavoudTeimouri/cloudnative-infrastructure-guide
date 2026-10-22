# ADR-0009 — Service mesh adoption

- **Status**: Accepted (provisional pending Phase 1 review)
- **Date**: 2026-10-22
- **Deciders**: Platform Architect / SecOps / SRE
- **Supersedes / superseded by**: none

## Context

The master prompt asks for a mesh evaluation, and the requirement to explain benefits and acceptance criteria.

## Requirements

See `requirements/requirements-and-assumptions.md` (R-01..R-14, D-01..D-14).

## Options considered

- 1. Adopt Istio now.
- 2. Adopt Linkerd now.
- 3. Defer until a threshold is met.

## Decision

Defer. No mesh in the initial platform. Adopt only when a documented threshold is met: >=30 services requiring mTLS, cross-team traffic policy requirements, and >=2 application clusters. Istio is the first candidate, Linkerd the lighter alternative.

## Rationale and trade-offs

- Istio has the largest feature set and ecosystem.
- Linkerd is lighter and simpler.
- No mesh means fewer artifacts, less CPU, fewer upgrades.
- Native Kubernetes networking plus NetworkPolicy covers the current requirement. Adopting a mesh before it is needed adds operational cost with no benefit.

## Security and operational implications

A mesh adds a sidecar (or ambient) data path, its own control plane, CRDs, and a large artifact set that must all be mirrored offline. It also creates new failure modes: a bad DestinationRule can blackhole traffic.

## Dependencies

Istio/Linkerd control plane, sidecar, and gateway ports, plus the Envoy/xDS ports. Verify per release.

## Failure scenarios

Mesh misconfiguration can break service-to-service traffic cluster-wide. The blast radius is larger than any other add-on, and it is silent until traffic is affected.

## Migration considerations

Removing a mesh later means removing sidecars from every workload and cleaning up CRDs; it is disruptive but not a data migration.
