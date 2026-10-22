# ADR-0027 — Ingress controller portfolio and deprecation policy

- **Status**: Accepted (provisional pending Phase 1 review)
- **Date**: 2026-10-22
- **Deciders**: Platform Architect / SecOps / SRE
- **Supersedes / superseded by**: none

## Context

One ingress controller is a single point of failure and a single point of lock-in. The community ingress-nginx project was retired in March 2026, which showed concretely what happens when a controller's project ends: deployments keep running on a frozen version with no security fixes and no upgrade path. A portfolio with an explicit lifecycle gives the platform a rehearsed escape route and a second implementation for failover and for Gateway API migration.

## Requirements

See `requirements/requirements-and-assumptions.md` (R-01..R-14, D-01..D-14).

## Options considered

- 1. One controller, replaced when its project is retired.
- 2. A portfolio with no lifecycle rules.
- 3. A bounded portfolio of at most three deployed controllers, each with a stage, a replacement, and a removal date.

## Decision

A bounded portfolio of at most three deployed controllers, each assigned one of five stages (Candidate, Supported, Deprecated, Removed, Retired upstream), with a dated deprecation schedule and a mandatory replacement named before a controller is deployed. F5 NGINX Ingress Controller and F5 NGINX Gateway Fabric are Supported; Envoy Gateway is Supported as the Gateway API native failover target; everything else is a Candidate. Upstream retirement forces Deprecated immediately, and a critical CVE forces an urgent removal plan.

## Rationale and trade-offs

- A second implementation on a separate address gives a rehearsed failover path and a safe place to land Gateway API traffic.
- A named replacement and a removal date mean a deprecation is a plan, not a surprise.
- A cap of three keeps the offline artifact footprint and the operational surface bounded.
- Three controllers means three sets of images, CRDs, certificates, addresses, admission webhooks and skills.
- A controller held in the Deprecated stage still consumes address space, artifacts, and attention.

## Security and operational implications

Each controller runs in its own namespace with its own admission webhook and a namespace-scoped failure policy, so one controller's webhook outage does not block writes for another. The annotation-driven configuration surface must stay disabled: the retired project was explicitly criticised for allowing arbitrary NGINX directives through an annotation, and the replacement must not reintroduce that. A wildcard certificate is issued per controller, so a compromised controller cannot serve a valid certificate for another controller's address.

## Dependencies

Per controller: 2-4 images, 1 chart, up to 3 CRDs, 1-2 MetalLB addresses, 2 DNS records, 1 ConfigMap and 1 policy. The Gateway API CRDs are shared. Failure is signalled by a DNS or load-balancer target change, not by a controller feature, and a load-balancer health-check-driven change is preferred over DNS because of the TTL.

## Failure scenarios

Migrating a controller is a staged traffic move, not a big bang: new applications go to the replacement immediately, existing applications move on their next deployment, and the remaining ones are migrated on a deadline. Removal is blocked while any traffic share remains, and a controller is never removed before its replacement has served a full business cycle. The Kubernetes SIG Network ingress2gateway tool assists with the conversion, but it is a utility and its output must be reviewed and tested.

## Migration considerations

A controller is never deployed without a named replacement and a removal date, and no controller stays Deprecated for more than three months without a recorded exception. The deprecation schedule is anchored to upstream dates where they exist, such as the Envoy Gateway release end-of-life dates.
