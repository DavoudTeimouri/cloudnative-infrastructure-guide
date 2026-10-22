# ADR-0015 — Linux directory integration

- **Status**: Accepted (provisional pending Phase 1 review)
- **Date**: 2026-10-22
- **Deciders**: Platform Architect / SecOps / SRE
- **Supersedes / superseded by**: none

## Context

Servers must work both standalone and AD-integrated, with a migration path.

## Requirements

See `requirements/requirements-and-assumptions.md` (R-01..R-14, D-01..D-14).

## Options considered

- 1. Local accounts only.
- 2. SSSD with AD or LDAP as the identity source, with local break-glass accounts retained.
- 3. Full AD join via realmd.

## Decision

SSSD as the mechanism (it handles both AD and LDAP providers) with realmd available for the AD join flow, plus mandatory local break-glass accounts and an emergency SSH key held offline on every node.

## Rationale and trade-offs

- Single mechanism for two directory types.
- SSSD caches identity and allows offline login.
- realmd is a convenience wrapper for the AD join.
- SSSD is the standard mechanism and the only one that gives a workable offline-cache story. Break-glass accounts are non-negotiable in an air-gapped environment where the directory may be unreachable.

## Security and operational implications

SSSD caches credentials, so a revoked or locked AD account can still log in for the cache lifetime. Cache timeout is a security decision, not a default. UID/GID mapping from AD can collide with local accounts.

## Dependencies

Kerberos 88, LDAP 389/636, DNS 53, NTP 123. SSSD communicates with the KDC and DC.

## Failure scenarios

Directory outage stops new logins but does not stop running workloads. Break-glass accounts remain the recovery path.

## Migration considerations

Migration from local accounts to SSSD is straightforward and reversible; the reverse migration requires re-creating local accounts. UID/GID mismatch can break file ownership on existing data, notably on Ceph OSD directories.
