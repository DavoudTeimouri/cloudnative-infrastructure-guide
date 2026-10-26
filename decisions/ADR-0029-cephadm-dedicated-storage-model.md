# ADR-0029 — Cephadm dedicated storage model

- **Status**: Accepted (provisional pending Phase 1 review)
- **Date**: 2026-10-22
- **Deciders**: Platform Architect / SecOps / SRE
- **Supersedes / superseded by**: none

## Context

Ceph can run either as the storage layer of the application cluster (Rook-Ceph, operator-managed, pods on worker nodes) or on dedicated hosts outside Kubernetes (cephadm, systemd-managed daemons). The choice sets the blast radius between storage and workloads and determines whether storage can outlive a cluster rebuild.

## Requirements

See `requirements/requirements-and-assumptions.md` (R-01..R-14, D-01..D-14).

## Options considered

- 1. Rook-Ceph inside the application cluster.
- 2. cephadm on dedicated storage hosts outside Kubernetes.
- 3. External storage appliance (out of scope for the offline reference design).

## Decision

cephadm on dedicated storage hosts is the reference design: OSDs and MON/MGR daemons run on hosts that are not Kubernetes nodes, and the application cluster consumes the cluster through the Ceph CSI driver. Rook-Ceph is documented as the alternative for sites without dedicated hosts, where storage must share the worker nodes.

## Rationale and trade-offs

- Storage failure does not consume worker capacity and does not depend on the Kubernetes control plane being healthy.
- Ceph upgrades are scheduled independently of Kubernetes upgrades, so neither becomes a coupled change window.
- Dedicated hosts cost more than reusing worker capacity, and they add a second provisioning and patching surface.
- Two upgrade runbooks to maintain when a site chooses Rook instead.

## Security and operational implications

Dedicated storage hosts sit on the storage network only and are reached over SSH from the management network. Cephx keys and the dashboard TLS certificate are issued per cluster and stored in Vault, never in Git. Host firewall permits MON 3300/6789 and OSD 6800-7300 from cluster peers only. The hosts run no container workloads other than the Ceph daemons, so the exposed surface is the daemon set plus SSH.

## Dependencies

Three or more storage hosts with at least three MONs across failure domains, one OSD per physical disk, and a separate storage network. Images come from the internal registry mirror. The application cluster needs the Ceph CSI driver and a provisioned pool plus a client key with the minimum capability set for that pool.

## Failure scenarios

Losing one host leaves data available while Ceph recovers; losing enough OSDs to drop below min_size makes the affected pool read-only rather than corrupt. Loss of MON quorum stops pool and key operations but does not stop existing I/O. Loss of the storage network forces OSDs down, which is why the storage network is a separate failure domain from the workload network.

## Migration considerations

Moving from cephadm to Rook-Ceph means standing up a second cluster and migrating data with RBD mirroring or application-level copy; there is no in-place conversion. The reverse move is the same. Choosing cephadm first is the lower-risk order because the storage layer survives application-cluster rebuilds.
