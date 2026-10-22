# ADR-0007 — Ingress controller and Gateway API

- **Status**: Accepted (provisional pending Phase 1 review)
- **Date**: 2026-10-22
- **Deciders**: Platform Architect / SecOps / SRE
- **Supersedes / superseded by**: none

## Context

L7 traffic entry, TLS termination, and routing. The community ingress-nginx project (kubernetes/ingress-nginx) was retired in March 2026 with no further releases or security fixes, so the previously default choice is no longer adoptable. The successor options are F5's NGINX Ingress Controller (nginx/kubernetes-ingress), F5's NGINX Gateway Fabric (Gateway API native), and Traefik.

## Requirements

See `requirements/requirements-and-assumptions.md` (R-01..R-14, D-01..D-14).

## Options considered

- 1. F5 NGINX Ingress Controller (nginx/kubernetes-ingress).
- 2. F5 NGINX Gateway Fabric.
- 3. Traefik.
- 4. Retain the retired kubernetes/ingress-nginx.

## Decision

F5 NGINX Ingress Controller as the L7 controller, with Gateway API objects adopted for new applications and Ingress retained for compatibility. Re-evaluate toward NGINX Gateway Fabric when Gateway API becomes the only API in use across the estate.

## Rationale and trade-offs

- F5-maintained with a commercial support path; mature TLS handling; NGINX dataplane; supports both Ingress and Gateway API.
- NGINX Gateway Fabric is Gateway API native and is the vendor's forward path, but it requires converting every Ingress resource before it can serve them.
- Traefik is simpler and label-driven but has a smaller enterprise support ecosystem.
- Retaining the retired controller leaves the platform with no security fixes and a read-only repository; the steering committee has stated that doing so leaves users vulnerable.
- The NGINX dataplane and the F5 support path are the deciding factors, not inertia: the NGINX Ingress Controller is a different project from the retired ingress-nginx and is actively maintained by F5.

## Security and operational implications

The controller must be hardened: no unnecessary NGINX modules, explicit worker and connection limits, and admission webhooks that do not permit arbitrary configuration injection from untrusted namespaces. The retired project was explicitly criticised for the snippets annotation allowing arbitrary NGINX directives, so the replacement must not reintroduce that surface.

## Dependencies

NGINX Ingress Controller controller, webhook, and metrics ports; Gateway API CRDs are client-side only. For NIC 5.7.0 the officially tested Kubernetes range is 1.30-1.37, with Helm chart 2.8.0 and operator 3.8.0. NGINX Gateway Fabric 2.8.0 is conformant with Gateway API 1.6.3 and requires Kubernetes 1.32+. Verify against the pinned release.

## Failure scenarios

Ingress controller failure affects all external traffic to the cluster, but internal ClusterIP traffic is unaffected. A Gateway API implementation failure has the same blast radius.

## Migration considerations

Moving from Ingress to Gateway API is incremental: both can coexist and a Gateway controller can run alongside the Ingress one on a separate address. The Kubernetes SIG Network ingress2gateway tool converts existing Ingress resources to Gateway API, but it is a conversion utility, not an end-to-end migration, so the converted output must be reviewed and tested. Changing the controller is a helm swap with a brief traffic interruption.
