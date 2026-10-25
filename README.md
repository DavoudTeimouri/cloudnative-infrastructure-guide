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
| Identity | Keycloak as broker, OIDC/LDAP federation for Rancher, Harbor, GitLab, Argo CD, Vault, Kubernetes API. **No host-level AD join** |
| Secrets | **HashiCorp Vault** (Community, BSL 1.1), cert-manager, External Secrets. OpenBao is the documented fallback |
| Observability | Prometheus/Grafana/Alertmanager/Thanos, Loki/Fluent Bit |
| Security | Pod Security Standards, OPA Gatekeeper, Kyverno, Falco, Trivy, Cosign, Syft |
| AI | NVIDIA H100/H200 workers, MIG, vLLM, DCGM |

## Current state

| Item | Value |
|---|---|
| Files | 95 markdown, scripts and templates |
| ADRs | 28 (`decisions/ADR-0001` .. `ADR-0028`) |
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
| Service mesh | **None at v1.** Adopt only when the threshold in `service-mesh/evaluation.md` is met. Istio 1.31.3 (sidecar or ambient) has a full deployment, mTLS-staging and revision-based upgrade procedure: `service-mesh/istio/istio-deployment.md` | ADR-0009 |
| GPU sharing | MIG for production multi-tenancy, time-slicing for development only (no VRAM isolation) | ADR-0022 |
| LLM serving | vLLM primary, llama.cpp for small or quantized models | ADR-0023 |
| External load balancer | Tiered active/active edge: HAProxy (L4, active health checks) and Nginx (L7, TLS) on host network via Docker Compose, Keepalived with unicast peers. Tier 2 = two VIPs balanced by router ECMP/BGP; tier 3 = DNS/GSLB. A single VRRP VIP is active/standby, not active/active | ADR-0028, ADR-0004 |
| Artifact distribution | Harbor for images and OCI charts, Nexus for packages, GitLab for source, Ceph RGW for model weights. One owner per artifact type | ADR-0024 |

## Interactive guide site

**<https://davoudteimouri.github.io/cloudnative-infrastructure-guide/>**

A static site built from this repository. It turns the documents into a plan for one specific
cluster: pick the deployment method, the Kubespray release and the components, fill in the site
values, then read the ordered plan and download the configuration files.

The site holds no independent knowledge. Components, steps and exports come from
`catalog/catalog.json`; versions come from `compatibility/version-matrix.md`, and only rows
marked `VERIFIED` are used. A build check fails when the generated data no longer matches the
sources, so the site cannot drift from the documents. Details: `site/README.md`.

## Step-by-step guide — existing documents linked in order

Work the existing documents in order. Each step links to the next so the guide reads end-to-end;
every document is the authority for its section (this README only links them).

| Step | Title | Document | Next |
|---|---|---|---|
| 00 | Overview & architecture | [`architecture/00-overview.md`](architecture/00-overview.md) | → 01 |
| 01 | Deployment topology & sizing | [`architecture/02-deployment-topology.md`](architecture/02-deployment-topology.md) | → 02 |
| 02 | Failure domains | [`architecture/03-failure-domains.md`](architecture/03-failure-domains.md) | → 03 |
| 03 | OS baseline (per host) | [`operating-systems/host-configuration.md`](operating-systems/host-configuration.md) | → 04 |
| 04 | Container engine (Docker/Podman, air-gap) | [`storage/ceph/cephadm-deployment.md`](storage/ceph/cephadm-deployment.md) §air-gap | → 05 |
| 05 | Storage — Ceph (cephadm) | [`storage/ceph/cephadm-deployment.md`](storage/ceph/cephadm-deployment.md) | → 06 |
| 06 | Kubernetes (Kubespray) | [`kubespray/kubespray-deployment.md`](kubespray/kubespray-deployment.md) | → 07 |
| 07 | Management cluster | [`management-cluster/rancher/rancher.md`](management-cluster/rancher/rancher.md) | → 08 |
| 08 | Traffic edge (LB / ingress) | [`network-matrix/external-load-balancer.md`](network-matrix/external-load-balancer.md) | → 09 |
| 09 | Platform services | [`management-cluster/platform-services/`](management-cluster/platform-services/) | → 10 |
| 10 | Backup & upgrade | [`lifecycle/backup/backup-and-dr.md`](lifecycle/backup/backup-and-dr.md) · [`lifecycle/upgrades/upgrade-procedures.md`](lifecycle/upgrades/upgrade-procedures.md) | (end) |

**Cross-references kept inside the documents:**
- Ports / flows: [`network-matrix/port-requirements.md`](network-matrix/port-requirements.md)
- Versions: [`compatibility/version-matrix.md`](compatibility/version-matrix.md)
- No host AD join: [`decisions/ADR-0015-identity-integration-layer.md`](decisions/ADR-0015-identity-integration-layer.md)
- Secrets: Vault, never in Git — `[REDACTED]`

## Use it, step by step

The configurator is a wizard: one page per group, then a review page. The **Back** and **Next**
buttons sit at the bottom of every page, below the content, with the page counter between them.

1. **Deployment** — bare metal or virtual machines, cluster name, environment, domain. Read the
   requirements: the VM option lists what changes in the failure domain.
2. **Application cluster** — control-plane count, worker count, GPU nodes, and vCPU/RAM/disk per
   role. Node names and addresses are generated from the prefix and the first address; the page
   shows the result.
3. **Management cluster** — its own worker count and sizes, because Rancher, Keycloak, Argo CD,
   Harbor and Vault do not share the workload cluster's capacity. Includes the directory
   integrations (multi-select) and the directory endpoint.
4. **Operating system** — Oracle Linux 9/8 or Ubuntu 24.04/22.04, plus the host baseline: admin
   user, SSH port and password policy, sudo, timezone and locale, NTP and DNS servers, search
   domain, kernel arguments, swap, transparent huge pages, max pods, file descriptors, SELinux,
   firewall backend, audit retention, unattended security updates, and the CA bundle. Local
   accounts only; nodes are never joined to a directory. Reference:
   `operating-systems/host-configuration.md`.
5. **Storage** — Rook-Ceph inside the cluster, or cephadm on dedicated hosts with **Podman or
   Docker**. cephadm gets one node group per role: MON, MGR, OSD, MDS and RGW each have their own
   count and first address, so no role shares a host by accident. Rook gets the OSD worker count,
   device filter and StorageClass names. Reference: `storage/ceph/cephadm-deployment.md`.
6. **Traffic** — edge node count, edge VIP, MetalLB pool, DMZ CIDR, the VRRP pass phrase, and the
   ingress controller.
7. **Network and offline artifacts** — the seven CIDRs, the API VIP, registry and file-mirror
   endpoints, additional registries and package repositories, and the registry credential.
8. **Platform services** — GitOps, secrets, observability, logging, admission policy, runtime
   detection, backup, service mesh, GPU.
9. **Add-ons** — optional cluster components, each with its own version, values file and line in
   the deploy script: cert-manager (Vault PKI or a bootstrap issuer), Metrics Server, Vertical Pod
   Autoscaler (recommendation or auto), Descheduler (dry-run or eviction), external-dns (RFC2136
   or CoreDNS etcd), Trivy Operator, OpenTelemetry Collector. Reference:
   `addons/platform-addons.md`.
10. **Review** — sizing totals per role, every resolved version, the filtered implementation
    steps, and the generated files: inventories for both clusters, Kubespray group vars, cephadm
    bootstrap and per-role service spec, MetalLB pool, Keepalived, edge Compose stack, bootstrap
    scripts, Istio manifests, Vault policy, GPU manifests, the directory-integration checklist,
    the add-on values files, the deployment bundle, and the runbook.
11. **Upgrade** — a separate walkthrough. Pick the component and the target, and the site renders
    the ordered steps with gate markers, the command for each step rendered against your values,
    the downtime, and the rollback statement.

**Automated deployment bundle**

The review page emits an executable bundle, not a reading list:

| File | Role |
|---|---|
| `deploy.sh` | One entry point: `--dry-run`, `--phase NN`, `--verify`, `--yes`. Stops at the first failure, logs every phase |
| `nodes.tsv` | Every node with its role and address, generated from the counts |
| `00-preflight.sh` | Read-only checks: registry, SSH, clock, disk, DNS. Nothing changes until this passes |
| `10-os-baseline.sh` / `10-os-node.sh` | Copies and applies the host baseline on every node |
| `20-ceph.sh` | cephadm bootstrap on the first MON, adds every role host with its label, applies the spec, waits for `HEALTH_OK` |
| `30-kubespray.sh` | Runs the pinned Kubespray release from its own virtualenv, waits for every node Ready |
| `40-addons.sh` | Installs exactly the add-ons whose values files exist; a missing chart is reported, never downloaded |
| `50-verify.sh` | Acceptance checks: nodes, pods, metrics API, Ceph health, cert-manager, Argo CD |

A user with the addresses and the registry endpoint can run `./deploy.sh --dry-run`, then
`./deploy.sh`, and fix the phase that fails. Every phase is idempotent; re-running it is the
recovery path. The runbook download wraps the same order in prose with the document behind each
decision.


**Change it, step by step**

| Change | Edit | Then |
|---|---|---|
| A pinned version | `compatibility/version-matrix.md` | `python3 scripts/build_site.py` |
| A component, option, page or value | `catalog/catalog.json` | `python3 scripts/build_site.py` |
| An export template | `catalog/exports.json` | `python3 scripts/build_site.py` |
| An upgrade flow or a gate | `catalog/upgrades.json` | `python3 scripts/build_site.py` |
| A document that a step links to | the document | nothing, unless the path moved |

```bash
python3 scripts/build_site.py        # regenerate site/data.json
python3 scripts/validate_catalog.py  # missing docs, bad placeholders, stale data
python3 tests/test_site_render.py    # boots app.js and asserts the render (needs dukpy)
python3 -m http.server 8080 --directory site   # preview at http://localhost:8080
```

## Repository map

```
catalog/                 site data model: components, steps, values, export templates
site/                    the static guide site (no build toolchain, no CDN, no server)
USER.md                   communication and work style contract
MEMORY.md                 fact-store contract: facts live in memory + skills, not here
architecture/            logical topology, deployment topology, failure domains
decisions/               ADR-0001 .. ADR-0028
requirements/            requirements, tech matrix, roadmap, validation, acceptance,
                         standards, performance, component-guide template
compatibility/           version & compatibility matrix (pinned, with check dates)
offline-artifacts/       artifact matrix, offline architecture, staging workflow
operating-systems/       oracle-linux/ ubuntu/ distro baselines +
                         host-configuration.md (every host input, per distro)
automation/              ansible/ awx/ gitlab-ci/
kubespray/               deployment guide, multi-version support, inventory and
                         group-vars templates
kubernetes/              control-plane/ networking/ (cilium, coredns-forwarding,
                         metallb) ingress/ csi/ security/ access/ (end-user
                         kubeconfig), windows-workers.md,
                         node-resource-reservation.md, multiple-clusters.md
storage/                 ceph/ (incl. per-role node separation) rook-ceph/ alternatives/
management-cluster/      rancher/ argocd/ keycloak/ platform-services/
                         alternatives.md: Rancher vs Headlamp vs KubeSphere
identity/                application-level directory integration (no host join)
addons/                  platform-addons.md: cert-manager, metrics-server, VPA,
                         descheduler, external-dns, Trivy, OpenTelemetry
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

# Regenerate and validate the guide site
python3 scripts/build_site.py
python3 scripts/validate_catalog.py

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
