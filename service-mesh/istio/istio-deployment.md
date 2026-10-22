# Istio deployment

Istio is **not** part of the v1 baseline. ADR-0009 sets the threshold for adopting a mesh, and
`service-mesh/evaluation.md` records the evaluation. This document is the deployment procedure for
the case where that threshold is met — either because per-workload mTLS and L7 authorization are
required by a compliance obligation, or because traffic splitting and retries are needed between
services that cannot implement them themselves.

Pinned version: **1.31.3** (`compatibility/version-matrix.md`).

## Decide the dataplane mode first

| Mode | How it works | Cost | When to choose it |
|---|---|---|---|
| Sidecar (default) | An Envoy container per pod, injected by the webhook | ~10–30 MB and a small CPU share per pod; every pod restart on upgrade | Per-workload policy, `VirtualService` features, teams already familiar with it |
| Ambient | A per-node `ztunnel` for L4 mTLS, plus optional per-namespace waypoint proxies for L7 | No sidecar; one DaemonSet per node; L7 only where a waypoint exists | New deployments, large pod counts, mTLS as the main requirement |

Ambient is the better default for a new adoption. It changes the failure domain: a `ztunnel`
problem affects every pod on that node, not one workload.

Whichever mode is chosen, the control plane (`istiod`) is the same, and it is a new failure domain:
if `istiod` is unavailable, existing mTLS connections keep working but new pods cannot get
certificates.

## Prerequisites

1. Kubernetes is inside Istio 1.31's supported version window. Check the support matrix for the
   exact minor range before the upgrade, not after.
2. Gateway API CRDs are installed at the version the pinned Istio release expects. The platform
   already installs them for the ingress portfolio; do not install a second, older copy.
3. The CNI is compatible. With Cilium, ambient mode requires the CNI chaining configuration, and
   the Cilium `kube-proxy` replacement must be reconciled with Istio's traffic redirection.
4. Every image is mirrored into Harbor. There is no pull from the internet at deploy time.
5. A certificate authority decision is made: Istio's self-signed CA, or an external CA backed by
   Vault. The self-signed CA is per-cluster and dies with the cluster; the Vault-backed CA survives
   a rebuild and is the choice for a production cluster that must be recoverable.

## Mirror the images

Run this in the connected staging environment, then import the bundle into the air-gapped one.

```bash
istioctl manifest generate -f istio-operator.yaml -o /tmp/istio-rendered
# Every image the install and the dataplane need:
grep -rhoE 'image: *[^ ]+' /tmp/istio-rendered | awk '{print $2}' | sort -u \
  > /tmp/istio-images.txt
# Mirror each entry to the internal registry, keeping the tag and digest.
```

The list includes `istiod`, `proxyv2` (sidecar), `install-cni`, `ztunnel` (ambient), the gateway
images, and the `pilot-agent`. Re-run the extraction after every version change: the set changes
between releases, and a missing image fails at pod start, not at install time.

## Install

### Option A — istioctl (single cluster, imperative)

```bash
istioctl install -f istio-operator.yaml --verify
kubectl -n istio-system get pods
```

### Option B — Helm, managed by Argo CD (the platform default when a mesh is adopted)

```bash
helm upgrade --install istio-base   oci://{{registry}}/istio/base   -n istio-system --version 1.31.3
helm upgrade --install istiod       oci://{{registry}}/istio/istiod -n istio-system --version 1.31.3 -f istiod-values.yaml
# ambient only:
helm upgrade --install istio-cni    oci://{{registry}}/istio/cni    -n istio-system --version 1.31.3 -f cni-values.yaml
helm upgrade --install ztunnel      oci://{{registry}}/istio/ztunnel -n istio-system --version 1.31.3 -f ztunnel-values.yaml
```

Helm is preferred here because it makes the mesh a GitOps object like everything else. The
`IstioOperator` path is kept for the initial bring-up and for `istioctl` diagnostics.

## Enable mTLS in stages

Never start at STRICT on the whole mesh. The order that works:

1. Install with permissive mTLS (the default). Verify traffic flows.
2. Apply `PeerAuthentication` with `STRICT` to one non-critical namespace.
3. Watch the mesh metrics for rejected connections for a full business cycle.
4. Move namespace by namespace. Leave `kube-system` and any namespace running a third-party
   controller that cannot present a certificate for last, or exclude it explicitly.

```bash
kubectl apply -f peer-authentication.yaml
istioctl x describe pod <pod> -n <namespace>   # confirms the effective policy
```

The generated `peer-authentication.yaml` also carries a default-deny `AuthorizationPolicy` and an
allow rule scoped to one namespace. Apply the deny rule only after the allow rules are in place.

## Traffic entry

Two controllers must not claim the same `GatewayClass`. The platform's Gateway API portfolio
(`kubernetes/ingress/multi-controller-plan.md`) already has NGINX Gateway Fabric and Envoy Gateway
as candidates. When Istio is adopted:

- North–south edge: keep the edge load balancer, then a single ingress path. Either the existing
  NGINX Gateway Fabric terminates and forwards to the mesh, or Istio's own gateway terminates and
  the NGINX layer is removed from that path. Pick one, record it in the ADR, and do not run both
  in front of the same hostname.
- East–west: `VirtualService` / `DestinationRule` for sidecar mode; `HTTPRoute` attached to a
  waypoint for ambient mode. Do not mix the two models in one namespace.

## Observability

Istio's telemetry feeds the existing Prometheus stack. No second metrics pipeline.

```bash
istioctl analyze -A                     # configuration errors before they break traffic
kubectl -n istio-system get pods
# Dashboards: Istio's own Grafana dashboards, imported into the platform Grafana.
```

Kiali is optional and adds a second UI with its own RBAC. Do not install it without a named owner.

## Upgrade

Istio supports **canary upgrades with revisions**, and that is the only supported path that keeps
a rollback available.

```bash
# 1. Install the new control plane alongside the old one.
istioctl install --revision=1-32-0 -f istio-operator.yaml
# 2. Move one namespace at a time.
kubectl label namespace <ns> istio.io/rev=1-32-0 --overwrite
kubectl rollout restart deployment -n <ns>
# 3. Verify, then move the next namespace.
# 4. Remove the old revision when nothing references it.
istioctl uninstall --revision=1-31-3
```

Rules:

- **One minor at a time.** Istio does not support skipping minors.
- **Control plane before dataplane**, always.
- **Rollback exists only while the old revision is installed.** Moving the namespace label back is
  the rollback. Once the old revision is removed, the only path is forward.
- **Downgrade is not supported.**
- The revision name is derived from the version (`1-32-0` for 1.32.0); keep the naming rule in the
  upgrade record so the label and the installed revision cannot drift.

## Capacity and failure

| Item | Value |
|---|---|
| `istiod` | 2 replicas minimum, PodDisruptionBudget, requests 500m CPU / 2 GiB for a medium cluster |
| Sidecar per pod | requests 100m CPU / 128 MiB; limits 1 CPU / 512 MiB |
| `ztunnel` per node | requests 200m CPU / 128 MiB |
| Control-plane outage | Existing connections continue; new pods cannot obtain certificates |
| `istiod` loss | mTLS and policy stay enforced by the dataplane; config changes stop applying |
| Certificate expiry | Managed by Istio's CA. With an external Vault CA, the Vault PKI is a hard dependency |

## Validation before handover

```bash
istioctl version
istioctl analyze -A
kubectl -n istio-system get pods
# mTLS actually on:
istioctl x describe pod <pod> -n <ns> | grep -i 'mTLS'
# Policy is enforced, not just present: connect from a pod that should be denied.
kubectl exec -n <ns> <pod> -- curl -sS -o /dev/null -w '%{http_code}\n' http://<service>.<ns>:8080/
```

A mesh that is installed but not enforcing STRICT mTLS, or whose `AuthorizationPolicy` was never
tested with a negative case, is not adopted — it is a second control plane with no benefit.

## Removal

Removing a mesh is a migration, not an uninstall:

1. Set every namespace back to permissive, verify, then remove the policies.
2. Remove the waypoints or sidecars (label change, rolling restart).
3. Uninstall the control plane and the CRDs last.
4. Re-verify that NetworkPolicy still gives the isolation the mesh was providing. In most cases it
   does not, which is why the decision to adopt was made in the first place.
