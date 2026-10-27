# CONTRIBUTING

Thank you for contributing to the Cloud-Native Guide! This document outlines how to contribute effectively.

## Quick Start

1. **Fork the repository**
2. **Create a branch** from `main`: `git checkout -b my-feature`
3. **Make your changes** following the guidelines below
4. **Run the self-check**: `python3 tests/test_repo_tools.py`
5. **Submit a pull request**

## Tutorial

### Adding a New Document

Purpose: Add a new guide step or component documentation.

Prerequisites:
- The document must follow the guide's numbering sequence (Step 00-10)
- All version claims must have a source URL and check date
- The document must be cross-referenced from the catalog

Steps:
1. Create the markdown file in the appropriate directory (e.g., `architecture/00-overview.md`)
2. Add the step to the guide's step-by-step list in `README.md`
3. Update `compatibility/version-matrix.md` if new versions are introduced
4. Run `python3 scripts/validate_catalog.py` to verify
5. Run `python3 scripts/build_site.py` to regenerate the site
6. Run `python3 -m http.server 8080 --directory site` to preview

### Updating Component Versions

Purpose: Update pinned versions in the compatibility matrix.

Prerequisites:
- Access to the official source URL
- A verified check date (within 30 days)

Steps:
1. Run the appropriate refresh script: `python3 scripts/fetch_versions.py`, `python3 scripts/github_latest_releases.py <owner/repo>`, or `python3 scripts/kubespray_release_matrix.py release-2.28 release-2.29 release-2.30 release-2.31 release-2.32`
2. Review the output and update `compatibility/version-matrix.md`
3. Verify all changed rows have source URLs and check dates
4. Run `python3 scripts/validate_catalog.py` to confirm no catalog discrepancies

## How-to

### Running the Build Site Locally

```bash
python3 scripts/build_site.py        # regenerate site/data.json
python3 scripts/validate_catalog.py  # missing docs, bad placeholders, stale data
python3 scripts/check_links.py       # relative paths and in-page anchors
python3 -m http.server 8080 --directory site   # preview at http://localhost:8080
```

### Refreshing Version Data

```bash
python3 scripts/fetch_versions.py
python3 scripts/helm_chart_versions.py
python3 scripts/github_latest_releases.py <owner/repo>
python3 scripts/kubespray_release_matrix.py release-2.28 release-2.29 release-2.30 release-2.31 release-2.32
python3 scripts/kubespray_ansible_matrix.py release-2.28 release-2.29 release-2.30 release-2.31 release-2.32
```

### Generating ADRs

```bash
python3 scripts/gen_adrs.py
```

## Reference

### Repository Map

```
catalog/                 site data model: components, steps, values, export templates
site/                    the static guide site (no build toolchain, no CDN, no server)
USER.md                  communication and work style contract
MEMORY.md                 fact-store contract: facts live in memory + skills, not here
architecture/            logical topology, deployment topology, failure domains
decisions/               ADR-0001 .. ADR-0028
requirements/            requirements, tech matrix, roadmap, validation, acceptance, standards, performance, component-guide template
compatibility/           version & compatibility matrix (pinned, with check dates)
offline-artifacts/       artifact matrix, offline architecture, staging workflow
operating-systems/       oracle-linux/ ubuntu/ distro baselines + host-configuration.md
automation/              ansible/ awx/ gitlab-ci/
kubespray/               deployment guide, multi-version support, inventory and group-vars templates
kubernetes/              control-plane/ networking/ (cilium, coredns-forwarding, metallb) ingress/ csi/ security/ access/ (end-user kubeconfig), windows-workers.md, node-resource-reservation.md, multiple-clusters.md
storage/                 ceph/ (incl. per-role node separation) rook-ceph/ alternatives/
management-cluster/      rancher/ argocd/ keycloak/ platform-services/ alternatives.md: Rancher vs Headlamp vs KubeSphere
identity/                application-level directory integration (no host join)
addons/                  platform-addons.md: cert-manager, metrics-server, VPA, descheduler, external-dns, Trivy, OpenTelemetry
secrets-management/      vault/ (architecture + HashiCorp product decision) kubernetes-integration/ pki/ recovery/
gpu-ai/                  gpu-ai-architecture, gpu-workers/ drivers/ scheduling/ sharing/ inference/ monitoring/
monitoring/ logging/ security/ service-mesh/
network-matrix/          communication matrix, firewall rule generation, external load balancer design
lifecycle/               upgrades/ backup/ disaster-recovery/
troubleshooting/         symptom-driven runbooks
scripts/                 version-refresh helpers, Kubespray matrix extractors, ADR generator, GitHub sync/verify helpers
tests/                   repository self-check
manifests/               external-lb/ (Compose, Nginx, HAProxy, Keepalived)
```

### ADR Format

Each ADR follows the standard format:
- **Context**: The problem situation
- **Decision**: The chosen approach
- **Consequences**: Implications of the decision
- **Status**: Provisional, Accepted, Deprecated, or Superseded

### Version Matrix Marks

| Mark | Meaning |
|------|---------|
| VERIFIED | Checked against official source on the recorded date |
| PINNED | The exact version this platform deploys |
| UNVERIFIED | Not confirmed; must not be used in a deploy |

## Explanation

### Documentation as Code

This repository treats documentation with the same rigor as software:
- **Versioned:** Every claim has a version, source URL, and check date
- **Reviewed:** Changes go through the standard PR process
- **CI-tested:** `tests/test_repo_tools.py` runs 9 checks; `validate_catalog.py` and `build_site.py` enforce data consistency
- **Traceable:** All facts trace back to source documents

### Guide Site Workflow

The static guide site at `https://davoudteimouri.github.io/cloudnative-infrastructure-guide/` is built from three sources:
1. **`catalog/catalog.json`** — components, steps, values, export templates
2. **`compatibility/version-matrix.md`** — versions with source URLs and check dates
3. **Only VERIFIED rows** from the matrix are used in the site generation

Build checks fail when generated data no longer matches the sources, preventing drift. The site holds no independent knowledge — all components, steps, and exports come from the catalog and matrix.

### Contribution Guidelines

- **One writer per object:** Ansible owns OS and node state, Kubespray owns the cluster lifecycle, Argo CD owns declared Kubernetes state, Vault owns secret values
- **No version, image tag, URL, port, or compatibility claim enters this repo without a source URL and a check date**
- **Facts that cannot be verified are labelled UNVERIFIED with the verification procedure. Never silently assumed.**
- **Sensitive values never enter this repo. Sanitized examples and secret identifiers only.**
- **Every command states its execution context**
- **Destructive or production-impacting actions require explicit authorization before execution**
- **A test is PASSED only when it has been executed and the evidence is stored. Nothing in this repo is pre-marked as passed.**

### Staying in Scope

- Do NOT add new Kubernetes distributions (the guide is pinned to Kubespray)
- Do NOT introduce new secret stores beyond HashiCorp Vault (Community) and OpenBao fallback
- Do NOT change the five-Kubespray-release support policy (ADR-0026)
- Do NOT add new ingress controllers beyond the bounded portfolio (ADR-0027)

### Development Process

1. Discuss the proposed change in a new issue (or directly if it's a small fix)
2. Create a topic branch off `main`
3. Make changes with the smallest possible diff
4. Run all local checks: `test_repo_tools.py`, `validate_catalog.py`, `build_site.py`, `check_links.py`
5. Submit a PR with a clear title and description
6. Address review feedback
7. Once approved, the PR will be merged

### Release Process

- Version bumps are recorded in `compatibility/version-matrix.md` with a check date
- Each release must update the version matrix, artifact matrix, and component guide in the same change
- A version bump MR must pass all 9 checks in `test_repo_tools.py`