# ADR-0015 — Identity integration layer

- **Status**: Accepted (provisional pending Phase 1 review)
- **Date**: 2026-10-22
- **Deciders**: Platform Architect / SecOps / SRE
- **Supersedes / superseded by**: none

## Context

Operators and applications need directory-backed identity, but Linux nodes must stay independent of a directory service.

## Requirements

See `requirements/requirements-and-assumptions.md` (R-01..R-14, D-01..D-14).

## Options considered

- 1. SSSD join every node to AD or LDAP (the original plan).
- 2. Authentication for humans happens in the platform's identity-aware services (Rancher, Keycloak, Harbor, GitLab, Vault, Argo CD), while nodes keep local accounts only.
- 3. Both: OS-level join plus application-level federation.

## Decision

Identity is integrated at the **application layer only**. Linux nodes keep local administrative accounts plus an offline break-glass key; no SSSD, realmd, Kerberos membership or AD join on the host. Rancher, Keycloak, Harbor, GitLab, Argo CD and Vault authenticate through OIDC or LDAP federation against the customer directory, and Keycloak brokers the protocols so each service speaks one dialect.

## Rationale and trade-offs

- A directory outage cannot block local node recovery, because the node never depended on it.
- One integration point per service, expressed in its own configuration and owned by its own GitOps repository.
- No UID/GID mapping on hosts, so Ceph OSD directory ownership cannot be disturbed by a directory change.
- Group-to-role mapping is explicit per service instead of being implied by host membership.
- Joining every node to the directory couples host recovery to a service the operator may not control during an outage, and it buys nothing for workloads: Kubernetes authorization comes from the API server's OIDC/LDAP integration, not from host membership. Application-level federation gives the same audit trail with a smaller blast radius.

## Security and operational implications

Account lifecycle is now per service: removing a user requires that each integration is revoked, and there is no single host-level switch. Users still need a local account if they must log in to a node, and the break-glass account is shared operational emergency access rather than per-person accountability.

## Dependencies

Outbound from the management plane to the directory: LDAPS 636 (or 389 with StartTLS), HTTPS 443 for OIDC discovery. The directory never needs inbound access to the cluster.

## Failure scenarios

A directory outage blocks new interactive logins to the platform UI but does not stop running workloads, and does not affect node access or SSH recovery. Local accounts and the break-glass key remain the last resort.

## Migration considerations

Migrating from OS-level SSSD to application-level federation removes work from the host baseline and adds it to each service integration. The reverse path (adding SSSD later) remains available per cluster without touching the platform services.
