# ADR-0004 — Load balancing for control plane and ingress

- **Status**: Accepted (provisional pending Phase 1 review)
- **Date**: 2026-10-22
- **Deciders**: Platform Architect / SecOps / SRE
- **Supersedes / superseded by**: none

## Context

kube-apiserver, Rancher, Argo CD, Keycloak, and ingress all need stable virtual IPs that fail over. The requirement is an active/active pair of Linux edge nodes running Nginx or HAProxy with Keepalived, deployed with Docker Compose. Superseded in detail by ADR-0028, which defines the tiered design; this record states the boundary between the edge and the in-cluster load balancing.

## Requirements

See `requirements/requirements-and-assumptions.md` (R-01..R-14, D-01..D-14).

## Options considered

- 1. Hardware F5/HA pair.
- 2. Keepalived (VRRP) on a pair of nodes.
- 3. HAProxy in a small dedicated pair.

## Decision

Keepalived VRRP on two dedicated edge nodes for the control-plane API VIP, with an HAProxy or NGINX layer in front for TLS termination and upstream health checks. Hardware F5 only if the site already owns one. The full external load balancer design, including the active/active tiers, is in ADR-0028 and network-matrix/external-load-balancer.md.

## Rationale and trade-offs

- VRRP failover is in the second range, not instant.
- HAProxy is explicit and scriptable.
- Hardware gives the best support path.
- A single VRRP-owned VIP is active/standby, so the active/active requirement is met above the VIP layer, not by VRRP itself.
- Keepalived is a small, well-understood dependency and can be managed by Ansible. Hardware is preferred where it exists.

## Security and operational implications

VRRP depends on multicast or unicast peer configuration on the network segment; a switched network with multicast filtering needs unicast peers. HAProxy and keepalived both need health checks against the real backends. The edge is the only host exposed to the untrusted segment, so it runs a minimal image set and allows only 80 and 443 inbound.

## Dependencies

VRRP protocol 112 (IP protocol), keepalived health-check ports, HAProxy frontend/backend ports, and the management-only stats port. Verify against the installed versions.

## Failure scenarios

A VIP with no working failover is worse than no VIP: it hides a single point of failure behind a stable address. A split-brain VIP (both nodes think they are master) causes intermittent failures.

## Migration considerations

Migrating from keepalived to HAProxy or to hardware is a config change, not a data migration. Moving from tier 1 to the active/active tier 2 needs router ECMP or BGP for the second VIP, as described in ADR-0028.
