# ADR-0019 — Centralized logging backend

- **Status**: Accepted (provisional pending Phase 1 review)
- **Date**: 2026-10-22
- **Deciders**: Platform Architect / SecOps / SRE
- **Supersedes / superseded by**: none

## Context

Central logs are needed for audit, troubleshooting, and security detection.

## Requirements

See `requirements/requirements-and-assumptions.md` (R-01..R-14, D-01..D-14).

## Options considered

- 1. Loki + Fluent Bit.
- 2. OpenSearch + Fluent Bit/Logstash.
- 3. Elasticsearch + Logstash + Kibana.

## Decision

Loki with Fluent Bit as the default backend, with OpenSearch added only where full-text search across log content is a hard requirement (audit investigation, compliance). Elasticsearch is avoided in favour of OpenSearch on licensing grounds, subject to a licence review.

## Rationale and trade-offs

- Loki is far cheaper and label-based, and it fits Kubernetes metadata well.
- OpenSearch gives full-text, SQL, and alerting on content.
- Elasticsearch is the most capable but the most resource-hungry and licence-encumbered.
- Loki is the pragmatic default for Kubernetes-native logs. OpenSearch is added as a targeted capability rather than a platform-wide default.

## Security and operational implications

Loki's label model is index-like: high-cardinality labels (pod UID, request id) destroy performance. Label cardinality must be a design constraint, not a discovery.

## Dependencies

Fluent Bit forwarder to the backend, Loki 3100, OpenSearch 9200, Logstash 5044, and Fluent Bit OTLP 4317/4318. Verify per release.

## Failure scenarios

Log ingestion failure does not affect workloads unless a workload writes to stdout/blocked logging, which must be avoided with bounded buffers.

## Migration considerations

Migrating from Loki to OpenSearch means re-indexing historical logs. Keep the Fluent Bit output layer abstracted so the backend can change without touching nodes.
