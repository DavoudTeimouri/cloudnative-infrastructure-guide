# ADR-0031 — Identity integration with LDAP AD federation

- **Status**: Accepted (provisional pending Phase 1 review)
- **Date**: 2026-10-22
- **Deciders**: Platform Architect / SecOps / SRE
- **Supersedes / superseded by**: none

## Context

Enterprise sites have an existing directory (Active Directory or LDAP). The question is where that directory is consumed: on the Linux hosts, or only by the platform's application-layer identity provider. ADR-0015 already forbids joining Linux hosts to the directory, so this record fixes the application-layer pattern.

## Requirements

See `requirements/requirements-and-assumptions.md` (R-01..R-14, D-01..D-14).

## Options considered

- 1. No directory integration: local accounts everywhere.
- 2. Keycloak as the identity broker, federating LDAP/AD, with Rancher, Harbor, GitLab, Argo CD, and Vault trusting Keycloak.
- 3. Each platform component configured directly against AD/LDAP, with no broker.

## Decision

Keycloak as the single broker. It federates the site's LDAP or AD, and every platform component trusts Keycloak over OIDC or SAML. Linux hosts keep local accounts plus an offline break-glass account, per ADR-0015. Direct per-component directory configuration is rejected because it multiplies credentials, groups, and outage dependencies across components.

## Rationale and trade-offs

- One place to map directory groups to platform roles, and one place to revoke access.
- Components stay usable if the directory is unreachable, because Keycloak caches sessions and can fall back to a local admin account.
- Keycloak becomes a critical service: if it is down, new logins fail across the platform, so it needs its own HA pair and backup.
- Group mapping is per-component work regardless of the broker, so the broker reduces credential sprawl, not mapping effort.

## Security and operational implications

Keycloak stores no directory passwords; it validates them against the directory over LDAPS and stores only federation metadata and sessions. The LDAPS certificate and the bind account credential live in Vault and are injected at deploy time. Admin access to Keycloak itself is a separate realm with its own strong authentication, because compromising the broker compromises every trusting component. Break-glass local accounts on the hosts remain the recovery path when both the directory and Keycloak are unavailable.

## Dependencies

An LDAPS-reachable directory endpoint and a read-only bind account. Keycloak runs in the management cluster with a backed-up database (PostgreSQL) and its own ingress hostname. Each integrated component needs a client registration in Keycloak and its own group-to-role mapping. The offline mirror must carry the Keycloak and PostgreSQL images.

## Failure scenarios

Directory outage: existing Keycloak sessions continue, new federated logins fail, local break-glass still works. Keycloak outage: new logins across the platform fail; existing tokens remain valid until expiry, so token lifetime bounds the blast radius. Loss of the Keycloak database means re-creating clients and mappings, not loss of directory data.

## Migration considerations

Starting with no integration and adding Keycloak later is additive: deploy Keycloak, register clients, then switch each component's auth provider in a maintenance window. Moving from per-component directory configuration to the broker means re-creating clients and group mappings, which is why the broker is chosen first.
