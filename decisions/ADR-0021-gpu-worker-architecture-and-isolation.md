# ADR-0021 — GPU worker architecture and isolation

- **Status**: Accepted (provisional pending Phase 1 review)
- **Date**: 2026-10-22
- **Deciders**: Platform Architect / SecOps / SRE
- **Supersedes / superseded by**: none

## Context

GPU workers are expensive and have distinct failure modes.

## Requirements

See `requirements/requirements-and-assumptions.md` (R-01..R-14, D-01..D-14).

## Options considered

- 1. Shared general worker pool with GPU nodes added to it.
- 2. Dedicated GPU worker pool with taints and labels.
- 3. Dedicated GPU hosts outside Kubernetes.

## Decision

Dedicated GPU worker pool: GPU nodes form their own node pool with a `nvidia.com/gpu` taint, their own network segment, and their own resource quota. Non-GPU workloads cannot land there by default; GPU workloads require an explicit toleration.

## Rationale and trade-offs

- No noisy-neighbour impact on CPU/memory workloads.
- Isolated failure and upgrade domain.
- Explicit capacity accounting for GPU hours.
- Dedicated GPU pools are the standard practice for inference fleets and keep the AI capacity predictable.

## Security and operational implications

Dedicated pools consume some scheduling efficiency: a GPU node with a free GPU but no tolerating pod sits idle. Mitigated with a controlled burst policy allowing a non-GPU workload class to tolerate the GPU taint.

## Dependencies

GPU node -> API 6443, DCGM exporter 9400, model store 443, node-to-node NVLink/PCIe is local traffic, and the NVIDIA container runtime talks to the driver locally.

## Failure scenarios

A GPU node loss removes that capacity and may interrupt in-flight inference requests. Clients must handle connection resets and retry.

## Migration considerations

Converting a general node into a GPU node is a hardware change and a node rebuild. Keeping a small, separately-managed general pool for burst removes the scheduling dead time.
