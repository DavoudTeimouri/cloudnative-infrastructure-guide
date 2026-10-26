# ADR-0031 — Identity-integration LDAP/AD mixed-domain

- **Status**: Proposed
- **Date**: 2026-10-26
- **Deciders**: Platform Architect / SRE / SecOps
- **Supersedes / superseded by**: none

## Context

The platform must integrate with both LDAP and Active Directory in a mixed-domain environment. Users and services span directories with different authentication schemas, group formats, and trust boundaries. The integration strategy must address SSO, attribute mapping, and directory failover.

## Decision

Implement a federation layer that authenticates against both LDAP and AD, presenting a unified identity surface. Use an anti-corruption layer to translate between directory schemas, and enforce per‑app directory selection based on tenant boundaries. SSO is achieved via a central IdP that proxies to both back‑ends.

## Consequences

- **SSO**: Users obtain single sign‑on across LDAP‑ and AD‑backed applications, but per‑app directory mapping must be configured; mis‑mapped attributes can cause authentication failures.
- **Operational overhead**: The federation layer adds a configuration and monitoring surface; directory sync failures require manual intervention.
- **Latency**: Authentication requires round‑trip to the federation layer, adding a small but measurable delay versus direct directory binds.
- **Future scope**: Adding a third directory follows the same anti-corruption pattern; the architecture scales but each new directory increases the translation surface area.