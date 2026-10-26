# ADR-0030 — Service-mesh none (no control-plane)

- **Status**: Proposed
- **Date**: 2026-10-26
- **Deciders**: Platform Architect / SRE / SecOps
- **Supersedes / superseded by**: none

## Context

The platform requirement specifies no mandatory service-mesh for initial deployment. A service-mesh would add a data-plane sidecar, control-plane artifacts, CRDs, and increased resource usage. The decision must balance zero-cost adoption against future mTLS and traffic‑policy needs.

## Decision

Defer service-mesh adoption until a documented threshold is met. For initial platform launch, operate without a mesh data-plane or control-plane. Native Kubernetes NetworkPolicy and built‑in transport security cover current requirements.

## Consequences

- **Cost**: Zero direct cost; no control-plane resources, no sidecar overhead, no upgrade cycle.
- **Observability**: Reduced surface area for mesh‑related debugging; tracing and mesh‑level metrics are absent initially.
- **Security**: mTLS and fine‑grained traffic policies are not available out‑of‑the-box; rely on Kubernetes primitives (NetworkPolicy, TLS secrets) until a mesh is introduced.
- **Migration path**: Adding a mesh later requires sidecar injection, CRD cleanup, and potential traffic‑shift disruption; the zero‑cost decision simplifies the on-ramp but adds re‑work cost if requirements change.