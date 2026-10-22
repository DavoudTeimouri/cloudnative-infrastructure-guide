# ADR-0008 — Ceph deployment model

- **Status**: Accepted (provisional pending Phase 1 review)
- **Date**: 2026-10-22
- **Deciders**: Platform Architect / SecOps / SRE
- **Supersedes / superseded by**: none

## Context

Ceph can be deployed by cephadm on dedicated hosts, by Rook-Ceph inside Kubernetes, or by containerized Ceph under Podman/Docker.

## Requirements

See `requirements/requirements-and-assumptions.md` (R-01..R-14, D-01..D-14).

## Options considered

- 1. cephadm on dedicated storage hosts.
- 2. Rook-Ceph inside Kubernetes.
- 3. Containerized Ceph under Podman/Docker.

## Decision

Two supported models, used for different purposes: Rook-Ceph inside the Application Cluster for cluster-local storage, and cephadm on dedicated storage hosts for shared capacity consumed by multiple clusters through the external CSI driver. Containerized Ceph under Docker/Podman is explicitly NOT a supported model here — it is neither cephadm nor Rook and carries no upgrade or support path.

## Rationale and trade-offs

- cephadm is the vendor-supported path with clean lifecycle.
- Rook gives K8s-native CRDs and CSI integration.
- Containerized Ceph is unsupported operationally.
- Using only cephadm for everything means the Application Cluster depends on an external storage cluster for basic PVCs, which is a deliberate choice with a deliberate cost in complexity. Supporting both models covers both needs but doubles the operational surface, so it is accepted only with distinct documentation, monitoring, and upgrade runbooks.

## Security and operational implications

cephadm owns the whole lifecycle including upgrade orchestration; Rook adds an operator layer between K8s and cephadm-style daemons, which shifts the upgrade sequence (Ceph first, then Rook, then CSI).

## Dependencies

Ceph MON/OSD/MDS/RGW ports, the CSI driver needs to reach MON and OSD. Rook's operator and CSI images must be mirrored offline.

## Failure scenarios

A Ceph failure that takes out the storage network affects both models. Running Ceph in Kubernetes adds a coupling: a cluster-wide network or CNI failure can take storage with it.

## Migration considerations

Rook to cephadm is a migration of the whole cluster, not a config change. cephadm to Rook is likewise. Plan the Ceph version before committing to either path.
