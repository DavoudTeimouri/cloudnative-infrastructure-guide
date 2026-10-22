# MEMORY.md — environment and the fact store

This file is a pointer and a contract. It does not hold facts.

## The rule

**Facts live only in the memory store and the skill store. Not in this repository.**

The Hermes memory store and the skill store are the single source of truth for environment facts: current pinned versions, site IP ranges, host naming, credentials locations, and lessons learned from incidents. They live outside the repository and are not versioned with it.

This repository holds the durable, shareable engineering artifact: procedures, decisions, matrices, and the source-backed reasoning behind them. It points at the fact store; it does not duplicate it.

## Why

- The repository is reviewed, forked, and read months later. A duplicated fact goes stale silently in one place and stays correct in the other.
- The fact store is private to one profile and holds the things that change weekly.
- A fact in the repository without its source and check date is an unverifiable claim. A fact in the memory store with no source is fine, because the source lives in the repository file that the memory entry points to.

## Where each kind of information goes

| Information | Lives in | Not in |
|---|---|---|
| Current pinned version of a component | memory store (fact) | this repository, except the matrix row that cites the source and check date |
| Where a credential or key is kept | memory store | this repository, ever |
| Site IP ranges, host names, DNS names | memory store | this repository |
| A procedure, runbook, or workflow | skill store, plus the guide in this repository | memory store |
| A lesson from an incident | skill store | this repository |
| The version matrix (component, source URL, check date, compatibility rules) | `compatibility/version-matrix.md` | memory store |
| A decision and its reasoning | `decisions/ADR-*.md` | memory store |
| The network matrix (flows and ports) | `network-matrix/` | memory store |
| The artifact matrix (what is mirrored where) | `offline-artifacts/artifact-matrix.md` | memory store |
| Requirements, assumptions, open decisions | `requirements/` | memory store |
| Acceptance test results and evidence | `tests/acceptance/` | memory store |

## Maintenance order

When a fact changes:

1. Update the fact store entry first.
2. Update the repository file that cites it: the version matrix row, the artifact matrix row, the guide, or the ADR.
3. Run `python3 tests/test_repo_tools.py`.
4. Commit both the fact-store change and the repository change. The memory store is not versioned, so the repository change is the audit trail for why the fact changed.

## Environment

Facts about the environment where this repository is built, maintained, and deployed. Current values are in the fact store; the structure and the constraints are here.

| Aspect | Constraint |
|---|---|
| Deployment target | On-premises, air-gapped. No outbound internet at runtime. All artifacts mirrored internally and pull-verified |
| OS baseline | Oracle Linux 9 and Ubuntu Server 24.04 LTS, per `operating-systems/` |
| Cluster lifecycle | Kubespray, five releases supported in parallel (ADR-0026) |
| Storage | Ceph, either cephadm on dedicated hosts or Rook-Ceph in-cluster (ADR-0008) |
| Management | Rancher Management Cluster plus independent Application Clusters (ADR-0010, ADR-0011) |
| Traffic | MetalLB L4, a bounded portfolio of at most three L7 controllers (ADR-0027) |
| GitOps | Argo CD, with GitLab CI as the validation and approval path (ADR-0014) |
| Secrets | HashiCorp Vault, on hosts outside every cluster (ADR-0016, ADR-0025) |
| Observability | Prometheus and Loki, with a documented redaction boundary |
| AI | NVIDIA H100/H200 workers, MIG for isolation, vLLM for serving (ADR-0021, ADR-0022, ADR-0023) |

## Tooling

The memory and skill management tools are external to this repository. They are configured per Hermes profile, not versioned here. The repository therefore must stay self-describing: a reader with no access to the fact store must still be able to rebuild the platform from the documentation, the matrices, and the ADRs.
