# Deliverable 7 — GitLab and Ansible Design

## 7.1 Repository structure

One GitLab group per logical domain, separate projects for separate ownership. Rule: one project = one owner = one change-review path.

| GitLab project | Contents | Owner | Visibility |
|---|---|---|---|
| `docs-architecture` | architecture/, decisions/ | Platform Architect | Internal |
| `docs-requirements` | requirements/, compatibility/ | Platform Architect | Internal |
| `docs-operations` | troubleshooting/, lifecycle/, network-matrix/ | SRE | Internal |
| `infra-ansible` | ansible/ (roles, collections, inventories) | DevOps | Internal |
| `infra-os-config` | OS baselines, sysctl, security hardening, repos | DevOps + SecOps | Internal |
| `infra-kubespray` | kubespray/ (inventories, group vars, overrides) | Platform | Internal |
| `infra-gitlab-ci` | automation/gitlab-ci/ (pipeline templates) | DevOps | Internal |
| `infra-storage` | storage/ceph, storage/rook-ceph (CRs, config) | Storage | Internal |
| `infra-k8s-addons` | kubernetes/ (ingress, csi, security policies) | Platform | Internal |
| `mgmt-rancher` | management-cluster/rancher | Platform | Internal |
| `mgmt-argocd` | management-cluster/argocd (app-of-apps) | Platform | Internal |
| `mgmt-keycloak` | management-cluster/keycloak (realm export, clients) | SecOps | Internal |
| `sec-policies` | security/ (Gatekeeper, Kyverno, Falco, baseline) | SecOps | Internal |
| `sec-vault` | secrets-management/ (policies, roles, PKI layout) | SecOps | Restricted |
| `sec-scanning` | Trivy/Grype/Syft/Cosign policy + reports | SecOps | Internal |
| `obs-monitoring` | monitoring/ (Prometheus, rules, dashboards, Grafana JSON) | SRE | Internal |
| `obs-logging` | logging/ | SRE | Internal |
| `infra-vault` | Vault config, policies | SecOps | Restricted |
| `infra-gitlab` | GitLab runner config, backup scripts | DevOps | Restricted |
| `gpu-infra` | gpu-ai/ (drivers, operator, scheduling) | AI/Platform | Internal |
| `gpu-models` | model manifests, versions, checksums (no weights) | AI | Internal |
| `apps-<team>` | application GitOps repos (one per team) | Teams | Internal |
| `site-<env>` | environment-specific overlays (hosts, CIDRs, endpoints) | Platform | Restricted |

Environment overlay pattern: base content in the domain project, environment-specific values in `site-<env>`. Never fork base content per environment.

## 7.2 Pipeline stages

Stages run in order; each is a gate.

| # | Stage | Job | Tooling | Gate |
|---|---|---|---|---|
| 1 | source | branch policy, signed commits, template check | GitLab | protected branch, MR required |
| 2 | lint | YAML lint, markdown lint | yamllint, markdownlint | must pass |
| 3 | ansible | syntax check + lint | `ansible-lint`, `ansible-playbook --syntax-check` | must pass |
| 4 | helm | `helm lint` + `helm template` | helm | must pass |
| 5 | manifest | kubeconform / kubeval + policy dry-run | kubeconform, Gatekeeper dry-run | must pass |
| 6 | policy | OPA/conftest policy checks, Kyverno test | conftest, kyverno CLI | must pass |
| 7 | security | secret scan, dependency scan, image scan, SBOM | gitleaks, trivy, syft, grype | no HIGH/CRITICAL, no secrets |
| 8 | artifact | verify checksums, verify signatures, produce SBOM | cosign, sha256sum | must pass |
| 9 | staging | apply to staging cluster | ansible + Argo CD | health checks pass |
| 10 | integration | post-deploy tests from tests/ | bats/shell + k6 | pass |
| 11 | approval | MR approval gate, production job manual | GitLab approvals | 2 approvals + owner |
| 12 | production | apply to production | ansible + Argo CD sync | — |
| 13 | post-check | health, drift, SLO dashboards | prometheus queries, argocd app list | pass |
| 14 | drift | nightly scheduled diff of live vs Git | ansible `--check --diff`, Argo CD diff | report only, no auto-fix |

Validation is fully separate from production execution: no production credentials are present in the pipeline until the approval stage, and the production job runs from a protected tag, never from a branch.

## 7.3 Runner architecture

| Runner type | Use | Isolation | Notes |
|---|---|---|---|
| Shell executor on automation server | Ansible lint, syntax check | Host-level | Cheap, low risk tasks only |
| Docker executor | image build, unit tests | Container | Default for CI |
| Kubernetes executor | integration tests, Helm tests | Pod | Needs cluster agent token; keep separate namespace |
| VM runner (dedicated) | heavy builds | VM | Optional |

Rules:
- Runners never have cluster-admin. Namespace-scoped service accounts with a dedicated `ci` namespace.
- No runner on a Kubernetes control-plane node.
- Runner images pinned by digest.
- Concurrency limits to protect the artifact registry and cluster API.
- Protected variables for production secrets; masked and hidden in job logs.

## 7.4 Configuration ownership

| Object | Owner tool | Not owned by |
|---|---|---|
| OS packages, sysctl, users, firewall, repos | Ansible | any in-cluster controller |
| Node labels/taints, kubelet config, CNI, CSI, K8s version | Kubespray | manual kubectl |
| Add-ons (ingress, metrics, cert-manager, ESO, Gatekeeper) | Argo CD | Helm CLI by hand |
| Application manifests | Argo CD (per team repo) | platform repo |
| Cluster lifecycle (create/delete/upgrade) | Kubespray / Rancher Fleet | Argo CD |
| Secrets values | Vault | Git, Helm values, env files |
| Certificates | Vault PKI / cert-manager | manual openssl |
| Policy | Git (sec-policies) applied by Argo CD | runtime kubectl edits |

Conflict rule: if two tools would reconcile the same field, one is the owner and the other is forbidden from writing it. Recorded per component in the component guide (section D/E).

## 7.5 Secrets in CI

- GitLab CI variables marked `masked` + `protected` for production values.
- Preferred: OIDC/JWT authentication from GitLab CI job to Vault, exchanging the job's ID token for a Vault token with a narrow policy — avoids static CI tokens. Compatibility and edition constraints are recorded in `secrets-management/vault/gitlab-integration.md`.
- Vault agent sidecar for the runner if the GitLab edition does not support the chosen OIDC flow.
- `ansible-vault` only for bootstrap-time offline secrets, with the key file stored outside Git (Vault + offline copy).
- Never: secrets in Git, in images, in pipeline artifacts, in ordinary job logs, in `set -x` output.

## 7.6 Approval gates

| Change class | Approvals | Who |
|---|---|---|
| Docs/comment only | 1 | Any maintainer |
| Add-on or policy change (staging+prod) | 2 | Platform + SecOps |
| OS baseline, Ansible role change | 2 | DevOps + SecOps |
| K8s version upgrade | 2 + change window | Platform lead + owner |
| Storage class / Ceph change | 2 + change window | Storage + owner |
| Network/firewall change | 2 | Network + SecOps |
| Secrets/PKI policy change | 2 | SecOps only |

Protected branches: `main` (protected, no direct push), `release/*` (tagged, deploy source), `hotfix/*` (time-boxed).
