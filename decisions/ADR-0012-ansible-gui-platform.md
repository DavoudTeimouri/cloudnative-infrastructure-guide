# ADR-0012 — Ansible GUI platform

- **Status**: Accepted (provisional pending Phase 1 review)
- **Date**: 2026-10-22
- **Deciders**: Platform Architect / SecOps / SRE
- **Supersedes / superseded by**: none

## Context

Ansible is primary; a GUI is evaluated for approval workflows and audit.

## Requirements

See `requirements/requirements-and-assumptions.md` (R-01..R-14, D-01..D-14).

## Options considered

- 1. AWX.
- 2. Semaphore UI.
- 3. Rundeck.

## Decision

AWX. It is the closest to the Ansible Automation Platform's open-source core, has built-in RBAC, job approval, scheduling, and audit logging, and consumes the same roles and inventories. Semaphore UI is the lighter alternative. Rundeck is not recommended because it introduces a second job model that is not Ansible-native.

## Rationale and trade-offs

- AWX has the strongest audit and approval story.
- Semaphore is simpler and lighter.
- Rundeck is a general job runner, not an Ansible UI.
- AWX provides the audit trail the change-management model requires, which is the deciding factor.

## Security and operational implications

AWX is stateful (PostgreSQL) and therefore needs its own backup and restore path, and it becomes a control-plane component for change management.

## Dependencies

AWX web port, PostgreSQL port, and callback/websocket traffic between AWX and target hosts. Verify per release.

## Failure scenarios

AWX loss blocks GUI-driven changes but does not block direct ansible-playbook runs from the automation server, nor Argo CD deployments.

## Migration considerations

Migrating to Semaphore is a UI swap; the roles and inventories carry over. Migrating to AWX later means re-importing inventories and job templates.
