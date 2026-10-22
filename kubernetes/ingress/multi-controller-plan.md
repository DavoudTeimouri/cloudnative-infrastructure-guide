# Multiple ingress controllers — portfolio and deprecation plan

**Check date: 2026-10-17.** Gateway API conformance data is from the Gateway API implementation reports (`https://gateway-api.sigs.k8s.io/docs/implementations/list/`), which are the authoritative statement of what each implementation supports.

## The problem this solves

A single ingress controller is a single point of failure and a single point of lock-in. A portfolio of controllers lets the platform:

- Serve different traffic classes with different implementations (for example a Gateway API-native controller for new services, an Ingress controller for the long tail).
- Keep a second implementation running on a separate address so the primary can be upgraded or failed over without a full outage.
- Escape a controller's deprecation without a big-bang migration, because the next controller is already deployed and taking a share of the traffic.
- Use conformance reports as an objective measure of which implementation to prefer.

The cost is real: each controller is a set of images to mirror, a set of CRDs, a certificate, an address in the load-balancer pool, a configuration surface, and a skill requirement. The portfolio is bounded deliberately.

## Lifecycle model

Every controller in the portfolio moves through five stages. The stage is a property of the controller in the platform, not of the upstream project.

| Stage | Deployment | New apps | Upgrades in | Artifact mirroring | Exit condition |
|---|---|---|---|---|---|
| **Candidate** | Not installed | No | No | No | Evaluated and rejected, or promoted to Supported |
| **Supported** | Installed, taking traffic | Yes | Yes | Yes | Upstream EOL, or the platform's usage drops below the threshold |
| **Deprecated** | Installed, frozen at its pinned version | **No** | **No** | Yes, the pinned version only | 3 months after the stage change, or immediately if a critical CVE appears |
| **Removed** | Uninstalled | n/a | n/a | No | The traffic has been migrated and the runbook is retired |
| **Retired upstream** | Same as the stage it was in, but with a hard deadline | No | No | Only the pinned version, and only for continuity | Upstream stopped releasing: the platform sets its own deadline and treats the controller as Deprecated on that date |

Two hard rules:

1. **Upstream retirement forces Deprecated.** A controller whose project is retired (as `kubernetes/ingress-nginx` was in March 2026) becomes Deprecated on the retirement date, regardless of what stage it was in. There is no upgrade path, so the platform must treat it as frozen.
2. **A critical CVE in a Deprecated controller forces immediate removal planning.** The controller stays deployed to keep traffic flowing, but the removal plan becomes urgent and the exception is recorded with an owner and a date.

## The portfolio

| Controller | Stage | Role | Gateway API | Conformance (v1.5 reports) | Upstream status | Deprecation trigger |
|---|---|---|---|---|---|---|
| **F5 NGINX Ingress Controller** (`nginx/kubernetes-ingress`) | Supported | Primary L7. Serves Ingress and Gateway API | Yes | NGINX Gateway Fabric v2.6.0: 29/35 extended features | Active, F5 supported. NIC 5.7.0 supports k8s 1.30-1.37 | Upstream EOL, or Gateway API coverage of the estate reaches 100% and NGINX Gateway Fabric takes the load |
| **F5 NGINX Gateway Fabric** | Supported | Gateway API native. New services | Yes, primary | v2.6.0: 29/35 (v2.5.0: 26/35) | Active. Fabric 2.8.0 conforms to Gateway API 1.6.3, k8s 1.32+ | Never, while NGINX remains the vendor's strategic direction. Deprecated only if F5 changes direction |
| **Envoy Gateway** | Supported | Gateway API native. Second opinion and failover target | Yes | v1.8.0: 33-34/35 | Active, CNCF. v1.9 EOL 2027-02-14; v1.8 EOL 2026-11-08 | Upstream EOL, or the platform adopts a service mesh that provides the same function (ADR-0009) |
| **Traefik** | Candidate | Not installed. Evaluated for teams that want label-driven configuration | Yes | v3.7: 14/35 | Active, v3.7.16 | Remains a candidate unless a team requires it |
| **Cilium as a Gateway API implementation** | Candidate | Not installed as a controller. Cilium already provides the datapath | Yes | Cilium v1.20.0-pre.2: 25/35 | Active, part of the CNI already deployed | Never. Attractive because it removes a separate data path, but the conformance coverage is lower than the dedicated controllers |
| **Istio ingress gateway** | Candidate | Tied to the service-mesh decision | Yes | Istio 1.30.5: 31/35 | Active | Follows the mesh decision (ADR-0009): deprecated the moment a mesh is adopted, because the mesh provides ingress |
| **kgateway** | Candidate | Not installed | Yes | v2.3.7: 32/35 | Active | Remains a candidate |
| **HAProxy Ingress, Contour, Emissary, Kong, APISIX, Varnish** | Candidate | Not installed | Varies | Low | Active | Remain candidates. None clears the bar for a second deployment today |

## Deprecation schedule

Dates are anchored to the triggers, not to a fixed calendar. Where an upstream date exists, it is used.

| Controller | Latest known upstream EOL | Platform stage on that date | Platform removal target |
|---|---|---|---|
| kubernetes/ingress-nginx (community) | Retired 2026-03 | Deprecated immediately (already retired upstream) | 2026-12, after migration to the F5 controller or NGINX Gateway Fabric |
| Envoy Gateway v1.8 | 2026-11-08 | Deprecated on that date unless upgraded to v1.9 | 2027-02 (after the v1.9 EOL) |
| Envoy Gateway v1.9 | 2027-02-14 | Deprecated unless a newer version is adopted | 2027-05 |
| F5 NGINX Ingress Controller | Not scheduled | Supported | Only when Gateway API covers the whole estate |
| F5 NGINX Gateway Fabric | Not scheduled | Supported | Only if F5 changes direction |
| Ceph Squid (storage, tracked because Rook depends on it) | ~2026-10-31 | Deprecated | 2027-01 |

## Concrete deprecation procedure

When a controller enters the Deprecated stage:

1. **Freeze.** The version is pinned. No upgrades in, no new applications. The chart and images stay in the internal registry at the pinned version.
2. **Announce.** A dated notice in the platform changelog naming the controller, the replacement, the removal date, and the owner.
3. **Migrate.** Move traffic in slices, not all at once:
   - New applications go to the replacement immediately.
   - Existing applications move when they are next deployed, not as a separate project.
   - A deadline-driven bulk migration is scheduled for the remaining applications.
4. **Measure.** Track the traffic share still on the deprecated controller. Removal is blocked until it is zero and the address has been released.
5. **Remove.** Uninstall the controller, remove its CRDs, release its VIP from the MetalLB pool, remove its DNS record, and delete its artifacts from the internal registry. Update the network matrix and the artifact matrix in the same change.
6. **Record.** Update this file, the ADR, the version matrix, and the EOL watchlist.

## Traffic sharing and failover

Two controllers run on separate addresses, never behind the same VIP:

```
  DMZ LB
    ├── VIP-A  ->  NGINX Ingress Controller   (primary)
    └── VIP-B  ->  Envoy Gateway             (secondary / failover)
```

Each has its own certificate and its own entry in the MetalLB pool and the DNS records. Failover is a DNS or load-balancer target change, executed by the network team, not by a controller feature.

The secondary takes traffic only when:
- The primary is being upgraded.
- The primary has a defect.
- A share of new applications is deliberately routed to it to prove the path.

A DNS-based failover is slow (TTL-bound). For a platform where the ingress is on the critical path, prefer a load-balancer health-check-driven target change over DNS.

## Admission and policy interaction

Each controller has its own admission webhook, and each webhook is a cluster-wide dependency. The policy:

- Each controller runs in its own namespace with its own webhook configuration.
- The webhook's `failurePolicy` is `Fail` for the namespaces that controller serves, and `Ignore` elsewhere.
- The webhook's `namespaceSelector` restricts it to the namespaces it owns, so a failure in one controller does not block writes for another controller's namespaces.
- The admission webhooks of two controllers must not both claim the same resource in the same namespace without a documented precedence rule. Where both would apply, the newer controller takes the namespace and the older one is excluded by the namespace selector.

## Certificate strategy

One wildcard certificate per controller, issued by cert-manager from the internal CA, presented by the controller that owns the address. The certificate is not shared between controllers: a compromised controller must not be able to serve a valid certificate for the other's address.

## Offline footprint

Each controller adds:

| Item | Per controller |
|---|---|
| Container images | 2-4 (controller, webhook, agent, dataplane) |
| Helm chart | 1 |
| CRDs | 0-3 (Gateway API CRDs are shared) |
| CRD upgrades | Shared, but the controller version constrains which Gateway API release it supports |
| MetalLB IPs | 1-2 (one VIP, one failover VIP) |
| DNS records | 2 (one per VIP) |
| Configuration surface | One ConfigMap, one policy, one set of annotations |

A three-controller portfolio is roughly 12 images and 3 charts. That is the practical ceiling for an air-gapped estate, and the reason the portfolio is capped at three deployed controllers.

## Rules

1. At most three controllers are deployed at any time. The fourth is a candidate until one of the three is removed.
2. Every controller has a named replacement and a removal date before it is deployed.
3. No controller stays in the Deprecated stage for longer than three months without a recorded exception.
4. Upstream retirement immediately forces Deprecated.
5. Removal is blocked while any traffic share remains.
6. A controller is never removed without its replacement having served production traffic for a full business cycle.
