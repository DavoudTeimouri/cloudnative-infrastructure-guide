# Service mesh evaluation

**Decision: no mesh at v1.** See ADR-0009. This file records the evaluation and the threshold for revisiting it.

## What a mesh actually provides

| Capability | What it does | Native Kubernetes equivalent |
|---|---|---|
| Service identity | A cryptographic identity per workload, not per IP | None. NetworkPolicy works on IP/label selectors |
| mTLS | Automatic encryption and mutual authentication between services | None natively (service mesh is the standard answer) |
| L7 traffic management | Retries, timeouts, circuit breaking, outlier detection, mirroring, traffic splitting | Ingress handles north-south only |
| Authorization policy | Per-method, per-path authorization between services | NetworkPolicy is L3/L4 |
| Telemetry | Per-request latency, status, and dependency graph | Application-level instrumentation only |
| Ingress/egress gateway | Controlled entry and exit points with policy | Ingress + Gateway API + NetworkPolicy + egress NetworkPolicy |

## Evaluation

### Istio

| Aspect | Assessment |
|---|---|
| Feature breadth | Largest. Ambient mode removes the sidecar but not the control plane |
| mTLS | STRICT mode with automatic certificate rotation via the CA. Well proven |
| Traffic management | VirtualService, DestinationRule, Gateway, Telemetry, AuthorizationPolicy — comprehensive |
| Resource overhead | Sidecar: roughly 10-30 MB memory and a small CPU share per pod. Ambient (ztunnel): a node-level proxy, lower per-pod cost but new operational model |
| Artifact footprint offline | Large: istiod, ingress/egress gateways, ztunnel, CNI plugin, plus the Envoy images the sidecars pull. Every image must be mirrored |
| Version compatibility | Istio supports a defined window of Kubernetes versions. Checking that window is mandatory per upgrade |
| Upgrade complexity | High. The recommended path is a canary control plane, then namespaces in order. An Istio upgrade that skips the canary has caused outages |
| Operational cost | A new control plane, a new failure domain, a new CRD set, and a config model that is powerful enough to break traffic silently |

### Linkerd

| Aspect | Assessment |
|---|---|
| Feature breadth | Smaller than Istio. mTLS, retries, timeouts, traffic splitting, and a strong observability story |
| mTLS | Automatic, per-pod identity |
| Resource overhead | `linkerd-proxy` sidecar, roughly 10-20 MB per pod |
| Artifact footprint offline | Much smaller than Istio: proxy, controller, injector, plus the `linkerd-cni` |
| Version compatibility | Broad Kubernetes support |
| Upgrade complexity | Lower than Istio, but still requires a proxy restart per workload |
| Operational cost | Lower than Istio. Fewer CRDs, smaller surface |

### Cilium's native capabilities (no separate mesh)

| Capability | Cilium equivalent |
|---|---|
| mTLS | Cilium mutual authentication with SPIFFE identities, using certificates from cert-manager or an internal CA |
| L7 policy | CiliumNetworkPolicy L7 rules for HTTP and DNS |
| Load balancing | kube-proxy replacement with eBPF service handling |
| Observability | Hubble: per-flow visibility, DNS logs, and a UI |
| Service identity | Cilium is not a service mesh with an identity control plane in the Istio sense. Its identity model is node and workload certificate based |

The important caveat: Cilium gives encryption, L7 policy, and observability. It does **not** give Istio-level traffic management (retries, circuit breaking, traffic splitting, outlier detection) as a first-class platform feature.

## Decision criteria — the threshold to adopt a mesh

Adopt only when **all three** hold:

1. **>= 30 services** need mutual TLS between them.
2. **Cross-team traffic policy** is required (team A must be able to call team B's `/orders` but not `/admin`, enforced by the platform rather than by the calling code).
3. **>= 2 Application Clusters** are in production, because the mesh's value is in a consistent cross-cluster identity and policy model.

If a mesh is adopted, Istio is the first candidate. Linkerd is the lighter alternative if the requirement set stays within mTLS plus retries and the artifact footprint in an offline environment is the binding constraint.

## Benefits, cost and acceptance criteria

### Benefits (what we would get)

- Workload identity that survives IP changes, container restarts, and node replacement.
- Encryption of service-to-service traffic by default, without application changes.
- Platform-enforced authorization between teams, independent of the application code.
- Retry, timeout, and circuit-breaking defaults that remove a class of application bugs.
- A dependency graph and per-request latency without instrumenting each service.

### Costs (what we would take on)

- A control plane to operate, secure, back up, and upgrade.
- A large offline artifact set to mirror and keep current.
- A second CPU and memory tax on every pod.
- A new failure mode: a bad DestinationRule or an overloaded control plane can blackhole traffic cluster-wide.
- Meaningfully longer upgrade cycles, with a mandatory canary phase.
- A new troubleshooting skill set for the operations team.
- A large increase in the configuration surface that GitOps must manage.

### Acceptance criteria if a mesh is adopted

1. mTLS is in STRICT mode across all namespaces, with exceptions explicitly listed.
2. A network partition between the control plane and a workload does not break existing service-to-service traffic.
3. A mesh configuration error in one namespace does not affect another namespace.
4. The mesh upgrade procedure has been executed on a staging copy of a production cluster, including the canary phase.
5. Every mesh artifact is mirrored offline and pull-verified.
6. The added per-pod resource overhead is measured and accepted: `kubectl top pods` before and after.
7. Hubble or the equivalent is integrated with the existing observability stack.
8. A documented rollback: removing the mesh returns the platform to native networking without application changes.

## Interim measures

Until the threshold is met:

- Cilium network policies (L3/L4 and, where needed, L7) enforce what a mesh would enforce at the network level.
- Cilium mutual authentication provides workload-to-workload TLS where encryption is required, without a full mesh.
- Retry, timeout, and circuit-breaking defaults live in the application libraries and in the ingress configuration, owned by the application team.
- Service identity for platform components is handled by Vault-issued short-lived credentials, not by mesh identity.

## Offline footprint estimate

Before adopting, count the exact images to mirror. For Istio with the ambient data plane, the set includes: `istiod`, `istio-proxy` (or `ztunnel`), the ingress and egress gateway images, the `istio-cni` plugin, and the base images the gateway uses. For the sidecar model, every workload also pulls the `proxyv2` image, which must be present on every node or the pod stays in `ContainerCreating`.

The sidecar model's offline implication is the deciding factor for many air-gapped estates: the proxy image must be pullable by every node, and any node that cannot reach the registry will hold pods in `ContainerCreating` indefinitely.
