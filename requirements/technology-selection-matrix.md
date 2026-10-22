# Deliverable 3 — Technology Selection Matrix

Legend: **HA** = high-availability option exists. **Offline** = works air-gapped with mirrored artifacts. **Ops** = operational complexity (Low/Med/High). Recommendation is the default for this platform, not a universal rule.

## Orchestration and networking

| Technology | Purpose | Benefits | Limitations | HA | Offline | Security | Ops | Compatibility | Recommendation |
|---|---|---|---|---|---|---|---|---|---|
| Kubespray | K8s lifecycle via Ansible | Declarative inventory, idempotent reruns, offline images | Version drift, no built-in UI, limited rollback | Yes (via K8s) | Yes | SSH + sudo on nodes | Med | Ansible/Python version coupling | **Adopt** (mandated) |
| kubeadm | K8s lifecycle | Upstream native | Manual per-node, weaker config mgmt | Yes | Yes | Same | Med | None | Alternative only |
| Cluster API | Cluster fleet lifecycle | GitOps-native, strong model | Requires bootstrap provider, new CRDs | Yes | Yes | Controller perms | High | K8s >= 1.24 | Evaluate at fleet > 5 clusters |
| Calico | CNI | Mature, rich policy, IPIP/VXLAN | eBPF absent, policy debugging harder | Yes | Yes | NetworkPolicy | Med | Kubespray supported | Alternative to Cilium |
| Cilium | CNI | eBPF, Hubble, L7 policy, kube-proxy-free | Newer, kernel feature needs | Yes | Yes | CiliumNetworkPolicy | Med | Kubespray supported | **Adopt** |
| Flannel | CNI | Simplest | No network policy | n/a | Yes | Weak | Low | Any | Only for minimal lab |
| MetalLB | L4 LoadBalancer | Bare-metal VIPs, no cloud LB | L2/BGP only, no L7 | Yes (multi-VIP) | Yes | ARP/NDP spoofing risk | Low | Any | **Adopt** (bare metal) |
| NGINX Ingress (F5) | L7 ingress | F5-maintained, commercial support, Gateway API, stable | Config model complex at scale | Yes | Yes | NGINX CVEs | Med | NIC 5.7.0, chart 2.8.0, k8s 1.30-1.37 | **Adopt** |
| NGINX Gateway Fabric (F5) | Gateway API native L7 | Vendor's forward path, Gateway API conformant | Requires converting Ingress first | Yes | Yes | NGINX CVEs | Med | Fabric 2.8.0, Gateway API 1.6.3, k8s 1.32+ | Adopt when Gateway API is the only API in use |
| External edge: HAProxy + Nginx | L4 + L7 edge, active/active | Both on host network via Docker Compose; active health checks; stateless and rebuildable | Two components to maintain; a single VRRP VIP is active/standby, so active/active needs ECMP/BGP or DNS above it | Yes | Yes | Smallest attack surface (only 80/443 exposed) | Med | nginx 1.31.8, haproxy 3.2.26, keepalived 2.4.3, compose v5.6.1 | **Adopt** — ADR-0028 |
| ingress-nginx (community) | L7 ingress | Was the de facto default | **RETIRED March 2026** — no releases, no security fixes, read-only repo | n/a | Yes | No fixes for new CVEs | n/a | Not adoptable | **Do not adopt** |
| Traefik | L7 ingress | Excellent Docker labels, simple CRDs | Smaller enterprise adoption | Yes | Yes | Good | Low | Gateway API supported | Alternative |
| Istio | Service mesh | mTLS, traffic mgmt, huge ecosystem | Resource overhead, upgrade pain, large artifact set | Yes | Yes (heavy) | STRONG identity | High | k8s >= 1.24 | Defer until scale threshold met |
| Linkerd | Service mesh | Light, fast, simple | Smaller feature set | Yes | Yes (light) | mTLS | Med | Broad | Alternative if mesh adopted |

**Mesh acceptance threshold (ADR-0009):** adopt only when (a) >= 30 services needing mTLS, (b) cross-team traffic policy required, (c) >= 2 application clusters.

## Storage

| Technology | Purpose | Benefits | Limitations | HA | Offline | Security | Ops | Recommendation |
|---|---|---|---|---|---|---|---|---|
| Ceph via Rook-Ceph | SDS in K8s | K8s-native, CSI, self-healing | Operator complexity, upgrade ordering | Yes | Yes | Ceph auth + KMS | High | **Adopt** |
| Ceph via cephadm | External SDS on dedicated hosts | Vendor-supported path, clean separation | Extra host pool, no CSI (use external CSI) | Yes | Yes | Ceph auth + KMS | Med | **Adopt** for shared capacity across clusters |
| Longhorn | K8s-native replicated block | Simple, no external deps | Not object/file; smaller scale proven | Yes | Yes | Per-volume | Med | Alternative for small K8s-only sites |
| OpenEBS | K8s-native storage | Broad options (JSC, CSI) | More moving parts, project status | Yes | Yes | Per-volume | Med | Alternative |
| NFS (managed) | Shared FS | Simple | Weak scale, no block | Depends | Yes | Kerberos | Low | Valid for shared-file only |
| Enterprise SAN | External block | Mature, fast, support | Cost, vendor lock | Yes | Yes | HW crypto | Low | Valid where budget allows |

## Management, GitOps, identity, secrets

| Technology | Purpose | Benefits | Limitations | HA | Offline | Security | Ops | Recommendation |
|---|---|---|---|---|---|---|---|---|
| Rancher | Multi-cluster mgmt | Cluster lifecycle, Fleet, RBAC | Own cluster to run, license tiers | Yes | Yes | OIDC + RBAC | Med | **Adopt** |
| Argo CD | GitOps CD | Diff view, self-heal, AppSet | Repo credentials, sync loops | Yes | Yes | Repo + OIDC | Med | **Adopt** (add-ons + apps) |
| GitLab | SCM + CI/CD | Integrated, large ecosystem, self-hosted | Heavy footprint, stateful | Yes (HA + object store) | Yes | Built-in, SSO | Med | **Adopt** |
| Keycloak | IdP broker | OIDC/SAML, many apps, admin UI | Stateful, needs DB | Yes | Yes | Strong | Med | **Adopt** |
| HashiCorp Vault | Secrets + PKI | Dynamic secrets, leases, PKI, SSH, audit, Kubernetes auth; commercial support path | BUSL 1.1 since 1.15 (IBM as licensor); Community edition has no namespaces, replication, or Sentinel | Yes (Raft) | Yes | Strong | Med | **Adopt** — platform standard. `secrets-management/vault/hashicorp-vault-decision.md` |
| OpenBao | Secrets + PKI | MPL 2.0, no licence cost, Vault-compatible core | Smaller ecosystem, no Vault Enterprise features, no commercial support contract | Yes (Raft) | Yes | Strong | Med | Fallback if legal rejects BUSL |
| SOPS + age | Git-encrypted secrets | Zero infra, works offline | No dynamic secrets, no leases | n/a | Yes | Key distribution burden | Low | Good for static bootstrap only |
| External Secrets Operator | K8s secret sync | Vendor-neutral, no Vault lock-in | Still syncs into etcd | n/a | Yes | Depends on provider | Low | **Adopt** with Vault provider |
| cert-manager | TLS lifecycle | Auto issue/renew, works with Vault PKI | Needs CA backend | n/a | Yes | Private key in K8s secret | Low | **Adopt** |
| AWX | Ansible GUI | Job control, RBAC, audit, scheduling | Stateful, needs PostgreSQL | Yes | Yes | SSO | Med | **Adopt** |
| Semaphore UI | Ansible GUI | Lighter, modern | Smaller feature set | Yes | Yes | SSO | Low | Alternative |
| Rundeck | Job runner | Not Ansible-native | Adds a second job model | Yes | Yes | SSO | Med | Not recommended |

## Observability, logging, security

| Technology | Purpose | Benefits | Limitations | HA | Offline | Security | Ops | Recommendation |
|---|---|---|---|---|---|---|---|---|
| Prometheus | Metrics | Ecosystem standard, simple | Pull model, no multi-master | Yes (sharding) | Yes | Auth proxy | Med | **Adopt** |
| Prometheus Operator | Manage Prometheus | CRD, scrape configs, rules | Extra controller | n/a | Yes | Cluster-admin | Low | **Adopt** |
| kube-prometheus-stack | Bundle | Fast baseline, good defaults | Bundle pin = upgrade pain | Yes | Yes | n/a | Low | **Adopt**, pin chart |
| Thanos | Long-term metrics | Object store, global query | Resource overhead, complex | Yes | Yes | n/a | High | **Adopt** when retention > 30d |
| VictoriaMetrics | Long-term metrics | Lower cost, fast | Smaller ecosystem | Yes | Yes | n/a | Med | Alternative to Thanos |
| Grafana | Dashboards | Broad support, alerting | Dashboard drift | Yes | Yes | SSO + RBAC | Low | **Adopt** |
| Alertmanager | Alerting | Grouping, inhibition, silences | Dedupe tuning needed | Yes | Yes | n/a | Med | **Adopt** |
| Loki + Fluent Bit | Log aggregation | Low cost, label-based, k8s-native | Weak full-text search | Yes | Yes | Multi-tenant labels | Med | **Adopt** (default) |
| OpenSearch | Log search | Full-text, SQL, dashboards | Heavy, JVM tuning | Yes | Yes | RBAC, TLS | High | Add where full-text required |
| OPA Gatekeeper | Admission policy | Rego, rich constraints | No audit-mode by default, latency | HA | Yes | Cluster-wide webhook | Med | **Adopt** (primary) |
| Kyverno | Policy | Native YAML, easier for teams | Fewer policy primitives than Rego | HA | Yes | Cluster-wide webhook | Low | **Adopt** (secondary, image policy) |
| Falco | Runtime detection | Low overhead, kernel events | Taps driver, noisy by default | Yes | Yes | eBPF/host | Med | **Adopt** (tuned ruleset) |
| Trivy | Image/file scanning | Easy, DB offline capable | DB staleness, not a runtime scanner | n/a | Yes | Needs DB | Low | **Adopt** |
| Grype | Image scanning | Anchored to fixed DB | Same staleness issue | n/a | Yes | Needs DB | Low | Alternative to Trivy |
| Syft | SBOM | CycloneDX/SPDX | Generation cost | n/a | Yes | n/a | Low | **Adopt** (SBOM generation) |
| Cosign | Signing/verification | Sigstore ecosystem, keyless | Registry trust bootstrap | n/a | Yes | Key management burden | Med | **Adopt** |

## GPU and AI

| Technology | Purpose | Benefits | Limitations | HA | Offline | Ops | Recommendation |
|---|---|---|---|---|---|---|---|
| NVIDIA GPU Operator | K8s GPU stack | Upgrades driver/toolkit/operator together | Privileged DaemonSet, kernel coupling | No (per node) | Yes (image mirror) | Med | **Adopt** |
| NVIDIA Container Toolkit | containerd GPU runtime | Standard path | Must match driver | No | Yes | Low | **Adopt** (with operator) |
| MIG | Hardware partitioning | Hard VRAM isolation, SLI | Supported models only, reconfigure downtime | No | Yes | Med | **Adopt** for production isolation |
| Time-slicing | GPU sharing | No reconfigure, simple | No VRAM isolation, contention | No | Yes | Low | Dev/burst only |
| MPS | Multi-process sharing | Better throughput than time-slicing | Same-process caveats, memory not isolated | No | Yes | Med | Limited use |
| vLLM | LLM serving | High throughput, continuous batching, tensor parallel | VRAM hungry, needs tuned model | Yes (replicas) | Yes (weights) | Med | **Adopt** primary |
| llama.cpp | LLM serving | CPU/edge capable, GGUF, quant | Lower throughput at scale, quant accuracy | Yes | Yes | Low | Adopt for edge/small models |
| Triton | Inference server | Multi-framework, dynamic batching | Heavier ops, NVIDIA-centric | Yes | Yes | High | Adopt if multi-framework needed |
| NVIDIA NIM | Prebuilt microservice | Fast deploy, optimized | License terms, image availability offline | Yes | Yes (license permitting) | Low | Evaluate license + offline artifact size |
| KServe | Inference platform | Standards, autoscaling, canary | Knative dependency, complexity | Yes | Yes | High | Adopt if platform-level serving needed |
| DCGM + exporter | GPU telemetry | Vendor-standard metrics, fault detection | NVIDIA-only | No | Yes | Low | **Adopt** |

## CI/CD, gitops, policy, and other choices

| Technology | Purpose | Recommendation |
|---|---|---|
| GitLab CI | Pipeline engine | **Adopt** |
| Kustomize | Manifest templating | **Adopt** (built into Argo CD, kubectl) |
| Helm | Chart templating | **Adopt** with pinned chart versions + digest |
| Argo Workflows | Batch pipelines | Adopt when DAG pipelines needed |
| Flagger | Progressive delivery | Optional, adopt after Argo CD maturity |
| Renovate/Dependabot | Version bump | Adopt for chart/image updates in connected staging only |
