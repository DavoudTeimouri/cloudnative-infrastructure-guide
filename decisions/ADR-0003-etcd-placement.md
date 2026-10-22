# ADR-0003 — etcd placement

- **Status**: Accepted (provisional pending Phase 1 review)
- **Date**: 2026-10-22
- **Deciders**: Platform Architect / SecOps / SRE
- **Supersedes / superseded by**: none

## Context

etcd holds all cluster state. Its failure characteristics dominate cluster recovery.

## Requirements

See `requirements/requirements-and-assumptions.md` (R-01..R-14, D-01..D-14).

## Options considered

- 1. Stacked on control-plane nodes.
- 2. Dedicated hosts.
- 3. Dedicated managed service (out of scope offline).

## Decision

Stacked on control-plane nodes in the first environment. Dedicated etcd hosts become mandatory when the site has separate failure domains for control-plane and storage-heavy workloads, or when etcd disk latency threatens API latency.

## Rationale and trade-offs

- Fewer nodes, lower cost.
- etcd gets dedicated fast local disks.
- Best isolation, highest cost.
- Stacking is the standard, supported, simplest path. Dedicated etcd pays off when disks or failure domains justify it.

## Security and operational implications

etcd traffic is sensitive to disk latency and network jitter. Colocating etcd with the API server means a slow disk degrades both.

## Dependencies

3 or 5 members spread across the failure domains available. 3 members tolerate 1 failure, 5 tolerate 2.

## Failure scenarios

Total etcd quorum loss halts all cluster writes. Restore is from a snapshot; recovery time is dominated by snapshot size and restore bandwidth.

## Migration considerations

Migrating from stacked to dedicated etcd is a data migration performed by the Kubespray workflow with the dedicated-etcd inventory; it is not a role flip.
