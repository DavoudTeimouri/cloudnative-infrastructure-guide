# ADR-0028 — External load balancer architecture

- **Status**: Accepted (provisional pending Phase 1 review)
- **Date**: 2026-10-22
- **Deciders**: Platform Architect / SecOps / SRE
- **Supersedes / superseded by**: none

## Context

The platform needs a stable, highly available address for the Kubernetes API, the Rancher agent, the Argo CD controller, the CI runners, and the client-facing ingress. The requirement is an active/active pair of Linux nodes running Nginx or HAProxy with Keepalived, deployed with Docker Compose. The tension is that Keepalived implements VRRP, and VRRP elects one master per virtual router id, so a single VIP under VRRP is active/standby by protocol, not by configuration.

## Requirements

See `requirements/requirements-and-assumptions.md` (R-01..R-14, D-01..D-14).

## Options considered

- 1. One VIP with Keepalived VRRP, active/standby.
- 2. One VIP with the dataplane running active/active on both nodes behind it.
- 3. Two VIPs, one per node, with upstream ECMP or BGP balancing between them, plus DNS/GSLB for client-facing names.
- 4. A hardware or cloud load balancer.

## Decision

Tiered design. The dataplane (HAProxy for L4 and active health checks, Nginx for L7 policy and TLS) runs on both edge nodes, containerised with Docker Compose, on the host network, binding the wildcard address with net.ipv4.ip_nonlocal_bind=1 so the socket is held whether or not the node currently owns a VIP. Keepalived manages the addresses with unicast peers. Active/active is delivered at tier 2: each node owns its own VIP and the router balances between them with ECMP or BGP; tier 3 adds DNS with health checks for client-facing names the router cannot balance. Tier 1, a single VRRP-owned VIP, is retained as the fallback when the router cannot balance, and is documented as active/standby rather than active/active.

## Rationale and trade-offs

- The dataplane is always up and serving on both nodes, so the VIP movement is a routing change, not a service start.
- Both nodes carry traffic, so losing one halves capacity instead of removing it.
- The edge is stateless and rebuilt by Ansible from committed configuration, so it is reconciled by GitOps at the node level.
- Two tiers of upstream dependency: the router must support ECMP or BGP for tier 2, and DNS must support health-checked records for tier 3.
- VRRP failover is roughly three seconds, and in-flight connections on the failing node reset; the drain window mitigates but does not eliminate it.
- Nginx and HAProxy in the same path doubles the component count and the failure surface for no benefit.

## Security and operational implications

The edge is the only host exposed to the untrusted segment, so it runs a minimal image set with no shell access, and the host firewall allows only 80 and 443 inbound. VRRP uses unicast peers because the DMZ segment is assumed to filter multicast; multicast must be confirmed with the network team before use. The dataplane binds the wildcard address and never the VIP, so an address move does not require a container restart, and the VRRP auth_pass and the TLS key are written by Ansible from Vault rather than committed to Git. A keepalived track_script health check stops a node with a broken dataplane from taking an address. SO_REUSEPORT on the Nginx listeners gives per-host worker sharding only; it is not cross-node balancing.

## Dependencies

The dataplane binds 80, 443, and the local health port 8443, plus the management-only stats port 8404 on the management address. Keepalived needs IP protocol 112 and the unicast peer port 112 between the edge nodes. The container runtime needs NET_ADMIN, NET_BROADCAST, NET_RAW, and SYS_MODULE for keepalived. Images and configuration are mirrored offline; the edge images are nginx 1.31.8, haproxy 3.2.26, and keepalived 2.4.3, with the Compose file and the configuration in Git.

## Failure scenarios

The edge is stateless, so losing both nodes loses only the edge. Losing one node in tier 2 leaves the surviving node serving its own VIP and the router converging on it. Losing the router's balancing capability in tier 2 degrades to whichever node the router still considers healthy, so the router's health-check configuration is part of the edge's failure model.

## Migration considerations

Moving from tier 1 to tier 2 requires the network team to add ECMP or BGP for the two VIPs; the edge configuration itself is unchanged apart from a second VIP in keepalived. Moving from tier 2 to a hardware load balancer means pointing the router at it and retiring the edge nodes. The dataplane configuration is portable between Nginx and HAProxy for the L4 role, so the choice is not a one-way door.
