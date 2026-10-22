# Enterprise Cloud-Native Deployment & Operations Guide

Personal cloud-native knowledge base: on-premises, air-gapped, production-oriented. Documentation as code. Every version pinned, every URL sourced, every claim traceable.

## Scope

| Domain | Stack |
|---|---|
| OS | Oracle Linux 9, Ubuntu Server 24.04 LTS |
| Orchestration | Kubernetes via Kubespray (Ansible) — **five Kubespray releases supported in parallel** |
| Storage | Ceph (cephadm on dedicated hosts, Rook-Ceph in-cluster) |
| Management | Rancher Management Cluster + independent Application Clusters |
| Traffic | MetalLB (L4, in-cluster) + external active/active edge (HAProxy/Nginx + Keepalived on Docker Compose) + F5 NGINX Ingress Controller / NGINX Gateway Fabric / Envoy Gateway (L7) + Gateway API + Cilium |
| GitOps | Argo CD, GitLab CI |
| Identity | Keycloak, SSSD/realmd, AD/LDAP |
| Secrets | **HashiCorp Vault** (Community, BSL 1.1), cert-manager, External Secrets. OpenBao is the documented fallback |
| Observability | Prometheus/Grafana/Alertmanager/Thanos, Loki/Fluent Bit |
| Security | Pod Security Standards, OPA Gatekeeper, Kyverno, Falco, Trivy, Cosign, Syft |
| AI | NVIDIA H100/H200 workers, MIG, vLLM, DCGM |

## Current state

| Item | Value |
|---|---|
| Files | 97 markdown, scripts and templates |
| ADRs | 27 (`decisions/ADR-0001` .. `ADR-0027`) |
| Deliverables | all 12 from the master prompt §32, mapped below |
| Repository self-check | `tests/test_repo_tools.py` — 8 checks, all passing |
| Version baseline check date | 2026-10-17 |
| Acceptance tests | 48, all `NOT RUN` — nothing is pre-marked as passed |

## Key platform decisions

The decisions that shape everything else. Full reasoning in the ADR, referenced by number.

| Decision | Outcome | ADR |
|---|---|---|
| Kubespray release support | **Five releases in parallel** (release-2.28 .. release-2.32), each with its own checkout, venv, inventory and mirrored artifacts. Covers five consecutive Kubernetes minors | ADR-0026 |
| Ingress controllers | **Bounded portfolio of at most three deployed**, each with a five-stage lifecycle (Candidate / Supported / Deprecated / Removed / Retired upstream) and a dated deprecation schedule. Upstream retirement forces Deprecated immediately | ADR-0027 |
| L7 ingress | F5 NGINX Ingress Controller (NIC 5.7.0, chart `nginx-ingress` 2.8.0) + NGINX Gateway Fabric + Envoy Gateway. The community `kubernetes/ingress-nginx` project is **retired** and not adoptable | ADR-0007 |
| Secrets | **HashiCorp Vault**, Community edition, on dedicated hosts outside every cluster. OpenBao only if legal rejects the BSL | ADR-0016, ADR-0025 |
| Kubernetes topology | 3 control-plane nodes with stacked etcd; 5 documented as the reference topology for larger sites | ADR-0002, ADR-0003 |
| CNI | Cilium, kube-proxy-free, with Hubble | ADR-0006 |
| Container runtime | containerd (2.3.7 under Kubespray release-2.32) | ADR-0005 |
| Service mesh | **None at v1.** Adopt only when the threshold in `service-mesh/evaluation.md` is met | ADR-0009 |
| GPU sharing | MIG for production multi-tenancy, time-slicing for development only (no VRAM isolation) | ADR-0022 |
| LLM serving | vLLM primary, llama.cpp for small or quantized models | ADR-0023 |
| External load balancer | Tiered active/active edge: HAProxy (L4, active health checks) and Nginx (L7, TLS) on host network via Docker Compose, Keepalived with unicast peers. Tier 2 = two VIPs balanced by router ECMP/BGP; tier 3 = DNS/GSLB. A single VRRP VIP is active/standby, not active/active | ADR-0028, ADR-0004 |
| Artifact distribution | Harbor for images and OCI charts, Nexus for packages, GitLab for source, Ceph RGW for model weights. One owner per artifact type | ADR-0024 |

## Repository map

```
USER.md                   communication and work style contract
MEMORY.md                 fact-store contract: facts live in memory + skills, not here
architecture/            logical topology, deployment topology, failure domains
decisions/               ADR-0001 .. ADR-0028
requirements/            requirements, tech matrix, roadmap, validation, acceptance,
                         standards, performance, component-guide template
compatibility/           version & compatibility matrix (pinned, with check dates)
offline-artifacts/       artifact matrix, offline architecture, staging workflow
operating-systems/       oracle-linux/ ubuntu/ distro-specific baselines
automation/              ansible/ awx/ gitlab-ci/
kubespray/               deployment guide, multi-version support, inventory and
                         group-vars templates
kubernetes/              control-plane/ networking/ ingress/ csi/ security/
                         ingress/  nginx-ingress.md, multi-controller-plan.md
storage/                 ceph/ rook-ceph/ alternatives/
management-cluster/      rancher/ argocd/ keycloak/ platform-services/
identity/                SSSD, realmd, Kerberos, AD integration
secrets-management/      vault/ (architecture + HashiCorp product decision)
                         kubernetes-integration/ pki/ recovery/
gpu-ai/                  gpu-ai-architecture, gpu-workers/ drivers/ scheduling/
                         sharing/ inference/ monitoring/
monitoring/ logging/ security/ service-mesh/
network-matrix/          communication matrix, firewall rule generation,
                         external load balancer design
lifecycle/               upgrades/ backup/ disaster-recovery/
troubleshooting/          symptom-driven runbooks
scripts/                 version-refresh helpers, Kubespray matrix extractors,
                         ADR generator, GitHub sync/verify helpers
tests/                   repository self-check
manifests/               external-lb/ (Compose, Nginx, HAProxy, Keepalived)
```

## Status legend

| Mark | Meaning |
|---|---|
| VERIFIED | checked against the official source on the recorded date |
| UNVERIFIED | value not yet confirmed; the verification procedure is recorded |
| PROVISIONAL | chosen default pending review; safe to change before build |

## Working rules

1. No version, image tag, URL, port, or compatibility claim enters this repo without a source URL and a check date.
2. Facts that cannot be verified are labelled UNVERIFIED with the verification procedure. Never silently assumed.
3. Sensitive values never enter this repo. Sanitized examples and secret identifiers only.
4. Every command states its execution context.
5. Destructive or production-impacting actions require explicit authorization before execution.
6. A test is PASSED only when it has been executed and the evidence is stored. Nothing in this repo is pre-marked as passed.
7. One writer per object: Ansible owns OS and node state, Kubespray owns the cluster lifecycle, Argo CD owns declared Kubernetes state, Vault owns secret values.

## Deliverables map (master prompt §32)

| # | Deliverable | Location |
|---|---|---|
| 1 | Requirements and assumptions | `requirements/requirements-and-assumptions.md` |
| 2 | Reference architecture | `architecture/` |
| 3 | Technology selection matrix | `requirements/technology-selection-matrix.md` |
| 4 | Version and compatibility baseline | `compatibility/version-matrix.md` |
| 5 | Offline artifact architecture | `offline-artifacts/` |
| 6 | Network communication matrix | `network-matrix/` |
| 7 | GitLab and Ansible design | `automation/` |
| 8 | Secrets management architecture | `secrets-management/` |
| 9 | GPU and AI architecture | `gpu-ai/` |
| 10 | Implementation roadmap | `requirements/implementation-roadmap.md` |
| 11 | Component guide backlog | `requirements/component-guide-backlog.md` |
| 12 | Validation strategy | `requirements/validation-strategy.md` |

Supporting standards: `requirements/platform-standards.md`, `requirements/performance-and-capacity.md`.

## Lifecycle and expiry watch

Tracked in `compatibility/version-matrix.md` (End-of-life and retirement watchlist).

| Item | Date | Action |
|---|---|---|
| `kubernetes/ingress-nginx` (community) | Retired 2026-03 | Do not adopt. Migrate to the F5 controller or NGINX Gateway Fabric |
| Helm 3 | Security fixes end 2027-02-10 | Plan the Helm 4 migration. Kubespray release-2.32 ships Helm 3.22.0 |
| Envoy Gateway v1.8 | EOL 2026-11-08 | Move to v1.9 (EOL 2027-02-14) |
| Ceph Squid 19.x | EOL ~2026-10-31 | Use Tentacle 20.x, or the version the pinned Rook release supports |
| Kubespray release-2.28 | Oldest supported | Leaves the supported set when a sixth successor ships |

## Maintenance

```bash
# Refresh the version data in a connected environment
python3 scripts/fetch_versions.py
python3 scripts/helm_chart_versions.py
python3 scripts/github_latest_releases.py <owner/repo>

# Refresh the Kubespray release matrix from each release branch
python3 scripts/kubespray_release_matrix.py release-2.28 release-2.29 release-2.30 release-2.31 release-2.32
python3 scripts/kubespray_ansible_matrix.py release-2.28 release-2.29 release-2.30 release-2.31 release-2.32

# Regenerate the ADRs after editing the generator
python3 scripts/gen_adrs.py

# Self-check the repository (offline)
python3 tests/test_repo_tools.py

# Publish the local tree to GitHub (Git Data API, no force-push needed)
python3 scripts/sync_github.py DavoudTeimouri cloudnative-infrastructure-guide \
  . main "Update guide content" --orphan

# Verify what is online against the local tree
python3 scripts/verify_github.py DavoudTeimouri cloudnative-infrastructure-guide main
python3 scripts/compare_tree.py DavoudTeimouri cloudnative-infrastructure-guide main .
```

## Implementation phases

Dependency-aware 15-phase plan with acceptance criteria per phase: `requirements/implementation-roadmap.md`.
