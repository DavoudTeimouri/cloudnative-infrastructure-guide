# ADR-0002 — Kubernetes control-plane topology

- **Status**: Accepted (provisional pending Phase 1 review)
- **Date**: 2026-10-22
- **Deciders**: Platform Architect / SecOps / SRE
- **Supersedes / superseded by**: none

## Context

Control-plane size drives API availability, etcd quorum, and cost. Master prompt asks for 5 as preferred reference, 3 as minimum production.

## Requirements

See `requirements/requirements-and-assumptions.md` (R-01..R-14, D-01..D-14).

## Options considered

- 1. 3 control-plane nodes with stacked etcd.
- 2. 5 control-plane nodes with stacked etcd.
- 3. 3 control-plane nodes with dedicated etcd on 3 separate nodes.

## Decision

3 control-plane nodes with stacked etcd for the first environment; 5 documented as the reference production topology for larger sites. Revisit when sustained API load or a third failure domain justifies it.

## Rationale and trade-offs

- 3 nodes tolerate 1 control-plane failure.
- 5 nodes tolerate 2, but 5 stacked etcd members on 5 nodes still lose quorum at 3 failures.
- 5 nodes cost more and lengthen every maintenance window.
- Fewer nodes to patch, drain, and replace, and lower etcd write-latency exposure. 5 nodes are justified only by API load or by a real third failure domain.

## Security and operational implications

Each control-plane node runs kube-apiserver, kube-controller-manager, kube-scheduler, etcd, and the CNI agent. etcd members are colocated on control-plane nodes: a node loss takes one member and one API replica together.

## Dependencies

5 stacked-etcd members in 3 failure domains is possible but raises quorum sensitivity to correlated failures; dedicated etcd is cleaner but adds 3+ nodes.

## Failure scenarios

etcd is the state store for all cluster state. Loss of quorum stops all API writes immediately; running pods keep their state.

## Migration considerations

Kubespray supports both topologies; dedicated etcd requires a separate inventory group and more careful host preparation. A later migration from stacked to dedicated etcd means etcd data migration, not a simple role change.
