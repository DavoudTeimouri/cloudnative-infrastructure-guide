# ADR-0014 — GitOps strategy and division of labour with Ansible

- **Status**: Accepted (provisional pending Phase 1 review)
- **Date**: 2026-10-22
- **Deciders**: Platform Architect / SecOps / SRE
- **Supersedes / superseded by**: none

## Context

Multiple tools must not fight over the same configuration.

## Requirements

See `requirements/requirements-and-assumptions.md` (R-01..R-14, D-01..D-14).

## Options considered

- 1. Argo CD manages everything including cluster add-ons.
- 2. Argo CD manages add-ons and applications; Ansible manages OS and cluster lifecycle.
- 3. Argo CD for add-ons only; applications deployed by CI.

## Decision

Argo CD manages Kubernetes-declared state: platform add-ons and application manifests. Ansible owns the operating system, node configuration, Kubespray cluster lifecycle, and external services. GitLab owns source control, validation, approvals, and pipeline execution. Each object has exactly one reconciler.

## Rationale and trade-offs

- Single writer per object avoids drift fights.
- Clear mental model for operators.
- More tools to learn.
- One writer per object is the only way multi-tool estates stay stable. The boundary between node-level and cluster-level state is the natural line.

## Security and operational implications

Overlapping ownership causes Argo CD to revert manual changes and Ansible to overwrite Helm-managed state. The ownership table in the CI design doc is normative.

## Dependencies

Argo CD -> GitLab 443, Argo CD -> K8s API 6443, Argo CD -> Vault 8200 (if using plugin-based secret management).

## Failure scenarios

Argo CD loss stops automated sync but does not stop running workloads. Ansible-driven changes continue.

## Migration considerations

Moving an object to a different owner is a one-time change in the Argo CD exclusion list or the Ansible role, plus a Git move.
