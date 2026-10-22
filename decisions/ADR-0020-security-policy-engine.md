# ADR-0020 — Security policy engine

- **Status**: Accepted (provisional pending Phase 1 review)
- **Date**: 2026-10-22
- **Deciders**: Platform Architect / SecOps / SRE
- **Supersedes / superseded by**: none

## Context

Admission control and runtime detection are required.

## Requirements

See `requirements/requirements-and-assumptions.md` (R-01..R-14, D-01..D-14).

## Options considered

- 1. OPA Gatekeeper only.
- 2. Kyverno only.
- 3. Both, with a defined split.

## Decision

Both, with a defined split: OPA Gatekeeper for constraint validation expressed in Rego (complex cross-resource rules, quotas, allowed-registries), Kyverno for image and resource policies that teams can write directly in YAML without learning Rego.

## Rationale and trade-offs

- Rego is powerful and testable.
- Kyverno policies are readable by application teams.
- One engine means one webhook and one failure mode.
- The split avoids forcing every team to learn Rego while keeping the power of Rego for platform-wide constraints. It is accepted with the cost of two webhooks explicitly documented.

## Security and operational implications

Two admission engines mean two webhooks on the API path and two failure policies. A misconfigured webhook can block all deployments. Both must be deployed in audit mode first, then switched to enforce, and both must be excluded from the platform's own namespaces.

## Dependencies

Webhook ports (typically 443 via the apiserver), Gatekeeper controller and manager ports, Kyverno admission/background/cleanup/report ports. Verify per release.

## Failure scenarios

A broken admission webhook can block all writes to the cluster. FailurePolicy must be configured deliberately: Fail for security namespaces, Ignore for the platform namespaces, with a documented exception process.

## Migration considerations

Removing one engine means deleting its constraints and webhook configuration, then re-validating that the remaining engine covers the policies that were dropped.
