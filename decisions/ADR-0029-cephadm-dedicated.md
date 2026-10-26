# ADR-0029 — Cephadm dedicated deployment

- **Status**: Proposed
- **Date**: 2026-10-26
- **Deciders**: Platform Architect / SRE / SecOps
- **Supersedes / superseded by**: none

## Context

The platform requires a Ceph storage backend. Two deployment patterns are under evaluation: a dedicated cephadm cluster or an integrated deployment alongside workload clusters. The choice impacts upgrade pathways, operational surface area, and network topology.

## Decision

Deploy cephadm as a dedicated cluster outside the workload auto-scaling groups. This isolates storage lifecycle from application deployment cycles and provides a single upgrade plane for the storage subsystem.

## Consequences

- **Upgrades**: Single upgrade plane simplifies Ceph version bumps; no coordination with application rollouts.
- **Complexity**: Adds a second cluster to provision and monitor, but with dedicated tooling (cephadm) the operational burden is contained.
- **Network**: Requires separate network policies and firewall rules for the cephadm endpoints, isolated from workload traffic.
- **Flexibility**: Future migration to a different Ceph deployment model (e.g., Rook) would require cluster rebuild; the dediated path is a deliberate trade-off for upgrade simplicity.