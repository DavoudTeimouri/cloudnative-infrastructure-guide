# ADR-0006 — CNI selection

- **Status**: Accepted (provisional pending Phase 1 review)
- **Date**: 2026-10-22
- **Deciders**: Platform Architect / SecOps / SRE
- **Supersedes / superseded by**: none

## Context

CNI defines pod networking, network policy, and integration with load balancing and service meshes.

## Requirements

See `requirements/requirements-and-assumptions.md` (R-01..R-14, D-01..D-14).

## Options considered

- 1. Calico.
- 2. Cilium.
- 3. Flannel.

## Decision

Cilium. eBPF datapath, Hubble observability, L7 network policy, native integration with MetalLB, and no kube-proxy dependency, which removes a class of iptables scaling problems.

## Rationale and trade-offs

- eBPF performance, L7 policy, Hubble, kube-proxy-free.
- Calico is mature with more third-party integrations.
- Flannel has no network policy.
- Cilium gives the most capability with the least extra infrastructure, and Hubble materially helps troubleshooting. Calico remains the fallback if kernel constraints bite.

## Security and operational implications

Cilium's eBPF datapath needs a compatible kernel and, for some features, specific kernel versions. It creates a wider kernel-compatibility envelope than Calico.

## Dependencies

Cilium agent and operator ports, Hubble relay/metrics, the agent's health and metrics ports. Verify against the pinned Cilium release.

## Failure scenarios

A CNI failure takes down pod-to-pod connectivity for everything on the node, and can make existing pods unreachable. This is one of the highest-blast-radius components.

## Migration considerations

Swapping CNI requires draining and recreating pods (pod IP and connectivity change), and re-validating network policy. There is no in-place conversion.
