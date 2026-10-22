# ADR-0018 — Monitoring platform and long-term metrics

- **Status**: Accepted (provisional pending Phase 1 review)
- **Date**: 2026-10-22
- **Deciders**: Platform Architect / SecOps / SRE
- **Supersedes / superseded by**: none

## Context

Prometheus is mandatory; long-term retention and cross-cluster views need a decision.

## Requirements

See `requirements/requirements-and-assumptions.md` (R-01..R-14, D-01..D-14).

## Options considered

- 1. Prometheus only.
- 2. Prometheus + Thanos.
- 3. Prometheus + VictoriaMetrics.

## Decision

Prometheus Operator with kube-prometheus-stack, and Thanos sidecar for long-term retention and cross-cluster queries once retention exceeds about 30 days or more than one cluster is monitored. VictoriaMetrics is the alternative if cost becomes a driver.

## Rationale and trade-offs

- Thanos is the ecosystem standard and integrates with kube-prometheus-stack.
- VictoriaMetrics uses less resource and stores more per byte.
- Prometheus alone is simplest but retains only as long as local disk allows.
- Thanos is the boring choice that matches the existing operator stack.

## Security and operational implications

Thanos adds object-storage coupling and a sidecar per Prometheus. VictoriaMetrics is a different operational model with its own consistency semantics.

## Dependencies

Prometheus 9090, node_exporter 9100, kube-state-metrics 8080, Alertmanager 9093, Thanos sidecar/UI ports. Verify per exporter release.

## Failure scenarios

Monitoring outage does not affect workloads. Losing the object storage breaks long-term queries and Thanos compaction but not live metrics.

## Migration considerations

Switching from Thanos to VictoriaMetrics means re-pointing the query layer and re-importing historical data. Do it while the data volume is still small.
