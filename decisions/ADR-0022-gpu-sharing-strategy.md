# ADR-0022 — GPU sharing strategy

- **Status**: Accepted (provisional pending Phase 1 review)
- **Date**: 2026-10-22
- **Deciders**: Platform Architect / SecOps / SRE
- **Supersedes / superseded by**: none

## Context

One physical GPU serving several tenants needs an isolation decision.

## Requirements

See `requirements/requirements-and-assumptions.md` (R-01..R-14, D-01..D-14).

## Options considered

- 1. MIG.
- 2. Time-slicing.
- 3. MPS.
- 4. Exclusive allocation only.

## Decision

MIG for production multi-tenancy, exclusive allocation for maximum throughput, and time-slicing strictly limited to development and burst use. MPS is not adopted by default.

## Rationale and trade-offs

- MIG gives hardware-level memory isolation with predictable capacity.
- Exclusive gives full throughput and no interference.
- Time-slicing is zero-setup but has no isolation.
- MIG is the only option that delivers hard VRAM isolation, which the master prompt explicitly requires for multi-tenant GPU sharing. Time-slicing is retained only where the isolation requirement is knowingly waived, and it is labelled as such everywhere it appears.

## Security and operational implications

MIG requires a supported GPU SKU and a fixed profile set. MIG reconfiguration requires draining the GPU, which is disruptive. Time-slicing has no VRAM isolation at all: one tenant can exhaust memory and kill another tenant's process. MPS shares a single process address space, so a fault in one tenant can affect the others.

## Dependencies

MIG resource names are published by the device plugin (for example a resource per MIG profile) and must be read from the live node rather than assumed.

## Failure scenarios

Time-slicing contention is invisible in the API: a pod scheduled successfully can still fail at runtime with an out-of-memory error caused by a neighbour.

## Migration considerations

MIG is not reversible into a single full GPU without a drain and reconfigure cycle, and only on MIG-capable hardware.
