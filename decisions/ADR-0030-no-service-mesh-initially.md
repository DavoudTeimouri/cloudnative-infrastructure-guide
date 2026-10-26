# ADR-0030 — No service mesh initially

- **Status**: Accepted (provisional pending Phase 1 review)
- **Date**: 2026-10-22
- **Deciders**: Platform Architect / SecOps / SRE
- **Supersedes / superseded by**: none

## Context

A service mesh adds mTLS, retries, traffic shifting, and per-request policy, at the cost of a control plane and a sidecar or node proxy on every workload path. The reference design must decide whether that belongs in the first deployment or waits for a requirement that justifies it.

## Requirements

See `requirements/requirements-and-assumptions.md` (R-01..R-14, D-01..D-14).

## Options considered

- 1. No mesh: native Kubernetes networking plus NetworkPolicy and ingress.
- 2. Istio ambient mode (ztunnel per node, waypoint only where L7 policy is needed).
- 3. Istio sidecar mode (Envoy injected into every pod).

## Decision

No mesh in the first deployment. Kubernetes NetworkPolicy provides namespace and pod isolation, ingress provides TLS termination, and the platform's own components handle identity at the application layer. Istio ambient is the documented next step, adopted when a concrete requirement appears: cross-namespace mTLS with workload identity, canary traffic shifting, or per-request authorization that NetworkPolicy cannot express.

## Rationale and trade-offs

- Zero additional control plane, zero proxy on the data path, and one less upgrade to sequence against Kubernetes.
- NetworkPolicy is L3/L4 only, so L7 policy and workload-identity mTLS stay unsolved until a mesh is added.
- Ambient mode keeps the sidecar cost off the pod but still adds ztunnel to every node and a waypoint for L7.
- Sidecar mode is the most capable and the most invasive; it is not the first choice for an air-gapped estate with mixed application teams.

## Security and operational implications

Without a mesh, service-to-service traffic inside the cluster is unencrypted unless the application does it. The mitigation is namespace isolation plus a documented rule that cross-namespace traffic is allowed only through an ingress or an explicit NetworkPolicy. Adopting ambient mode later adds mTLS without application changes, which is the reason ambient is preferred over sidecar when the requirement arrives.

## Dependencies

NetworkPolicy requires a CNI that enforces it; Calico and Cilium both do, and the choice is recorded in the CNI decision. Istio ambient needs a Kubernetes version and kernel (eBPF) supported by the pinned Istio release, plus its own images mirrored offline. No application change is required to adopt ambient later.

## Failure scenarios

A mesh control-plane outage in sidecar mode affects only new connections, not established ones; in ambient mode a ztunnel failure affects the node's pod traffic. Without a mesh, the failure mode is simpler: policy is enforced by the CNI, and a CNI failure is already a cluster-level incident.

## Migration considerations

Adopting ambient later is additive: install the control plane, enroll namespaces, then move L7 policy to waypoints. There is no data migration. Retiring a mesh means removing enrollment and falling back to NetworkPolicy, which must still be maintained as the baseline even while a mesh is present.
