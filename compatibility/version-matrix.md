# Version and Compatibility Matrix

**Check date: 2026-10-17.** Every row was read from the official source on that date unless marked otherwise. Re-verify before each upgrade; this file is a snapshot, not a live feed.

## How to read this file

| Mark | Meaning |
|---|---|
| VERIFIED | Read from the official source on the check date; the source is linked |
| PINNED | The exact version this platform deploys (chosen from the VERIFIED set) |
| UNVERIFIED | Not confirmed. The verification procedure is stated; the value must not be used in a deploy until confirmed |

Refresh procedure: `scripts/fetch_versions.py`, `scripts/helm_chart_versions.py`, `scripts/github_latest_releases.py`. Run them in a connected environment, diff against this file, and open an MR with the change plus the check date.

## Kubernetes and cluster lifecycle

| Component | Verified version | Pinned | Official source | Status | Notes |
|---|---|---|---|---|---|
| Kubespray | v2.32.0 | v2.32.0 | `https://github.com/kubernetes-sigs/kubespray/releases/tag/v2.32.0` | VERIFIED | Release branch `release-2.32` |
| Kubespray: default Kubernetes | 1.36.5 | see note | Kubespray release-2.32 README, "Supported Components" block | VERIFIED | The README lists the version the release was tested with, not the only supported one |
| Kubespray: minimum Kubernetes | v1.34.0 | n/a | Same README, "Requirements" | VERIFIED | Hard floor enforced by the release |
| Kubernetes (upstream latest stable) | v1.37.1 | UNVERIFIED for deploy | `https://github.com/kubernetes/kubernetes/releases` | VERIFIED | Pin only after a Kubespray compatibility check |
| Ansible (Kubespray-supported) | >=2.19.0, <2.20.0 | 2.19.x | Kubespray release-2.32 `docs/ansible/ansible.md` compatibility table | VERIFIED | Requires Python 3.11-3.13 |
| Python (control node) | 3.11-3.13 | 3.12 | Same table | VERIFIED | |
| containerd (Kubespray-managed) | 2.3.7 | 2.3.7 | Kubespray release-2.32 README, "Supported Components" | VERIFIED | containerd upstream latest is v2.4.2 — not interchangeable, Kubespray pins the version it tested |
| etcd (Kubespray-managed) | 3.6.15 | 3.6.15 | Same README | VERIFIED | |
| cri-o (Kubespray-managed) | 1.36.7 | not adopted | Same README | VERIFIED | Experimental in Kubespray; only on Fedora/Ubuntu/CentOS-family |
| Helm (Kubespray-managed) | 3.22.0 | 3.22.0 | Same README | VERIFIED | Helm 3 is in support mode. Final Helm 3 feature release 2026-09-09; **security fixes end 2027-02-10**. See the Helm EOL note below |
| Helm (upstream current) | v4.3.1 | n/a (not adopted yet) | `https://helm.sh/blog/helm-v3-end-of-life` | VERIFIED | Helm 4 is the current stable line. Plan the migration before 2027-02-10 |
| cni-plugins | 1.9.1 | 1.9.1 | Same README | VERIFIED | |
| CoreDNS (Kubespray-managed) | 1.14.2 | 1.14.2 | Same README | VERIFIED | |
| kube-vip | 1.0.3 | not adopted | Same README | VERIFIED | Alternative to keepalived for the control-plane VIP |
| local-path-provisioner | 0.0.37 | not adopted | Same README | VERIFIED | Default SC; replaced by Ceph |
| node-feature-discovery | 0.19.0 | optional | Same README | VERIFIED | |
| Kubespray container image | quay.io/kubespray/kubespray:v2.31.0 (example in README) | UNVERIFIED | Kubespray release-2.32 README "Quick Start" | VERIFIED that the example tag is v2.31.0; the matching image tag for v2.32.0 must be confirmed from the quay.io tag list | Use the image only if the tag is confirmed |

### Kernel requirements (Kubespray release-2.32, `docs/operations/kernel-requirements.md`)

| OS | Kernel | Meets >=4.19 | Platform note |
|---|---|---|---|
| Oracle Linux 9 | 5.14 | Yes | Preferred Oracle Linux release for this platform |
| Oracle Linux 8 | 4.18 | No | Below the 4.19 recommendation. Usable, but the platform standard is OL9 |
| Ubuntu 24.04 | 6.6 | Yes | Preferred Ubuntu release |
| Ubuntu 22.04 | 5.15 | Yes | Supported |
| RHEL/Rocky/Alma 9 | 5.14 | Yes | |

For Kubernetes >= 1.32, the recommended 4.x LTS kernel is 4.19; any 5.x or 6.x is supported. cgroups v2 needs >= 4.15 (5.8+ recommended). If a node's kernel is below the requirement, `kubeadm_ignore_preflight_errors: [SystemVerification]` can be set, but that is a documented deviation, not a default.

## Networking

| Component | Verified version | Pinned | Official source | Status | Notes |
|---|---|---|---|---|---|
| Cilium | 1.20.3 | 1.20.3 | Kubespray release-2.32 README, "Supported Components" | VERIFIED | The version Kubespray ships and tests |
| Cilium Helm chart | 1.20.3 | 1.20.3 | `https://helm.cilium.io/index.yaml` | VERIFIED | Chart and app version match |
| Calico | 3.31.7 | not adopted | Kubespray release-2.32 README | VERIFIED | Alternative CNI |
| Flannel | 0.28.9 | not adopted | Same README | VERIFIED | No network policy |
| Multus | 4.2.2 | not adopted | Same README | VERIFIED | Secondary networks |
| MetalLB | v0.16.1 | 0.16.1 | `https://github.com/metallb/metallb/releases/tag/v0.16.1` | VERIFIED | Chart `metallb-0.16.1` from `https://metallb.github.io/metallb/charts/index.yaml` |
| MetalLB (Kubespray-managed) | 0.13.9 | not adopted | Kubespray release-2.32 README | VERIFIED | Kubespray ships an older MetalLB; the platform installs its own chart instead |
| NGINX Ingress Controller (F5) | 5.7.0 (chart nginx-ingress 2.8.0) | chart 2.8.0 | `https://github.com/nginx/kubernetes-ingress/releases` | VERIFIED | F5's commercial-grade controller. **This is the NGINX Ingress Controller, not the retired `kubernetes/ingress-nginx`** — see the retirement note below |
| NGINX Gateway Fabric (F5) | 2.8.0 | 2.8.0 | `https://docs.nginx.com/nginx-gateway-fabric/overview/technical-specifications/` | VERIFIED | Gateway API conformant. Requires Kubernetes 1.32+. Gateway API 1.6.3 |
| Envoy Gateway | v1.9.2 | v1.9.2 | `https://github.com/envoyproxy/gateway/releases` | VERIFIED | Gateway API implementation. v1.9 EOL 2027-02-14, v1.8 EOL 2026-11-08 |
| kubernetes/ingress-nginx | v1.15.1 (chart 4.15.1) | **RETIRED — do not adopt** | `https://kubernetes.io/blog/2025/11/11/ingress-nginx-retirement/` | VERIFIED | Retired March 2026. Read-only repositories, no further releases or security fixes. Artifacts remain available for existing deployments only |
| Traefik | v3.7.16 | not adopted | `https://github.com/traefik/traefik/releases/tag/v3.7.16` | VERIFIED | Alternative ingress |
| Gateway API | v1.6.3 | v1.6.3 | `https://github.com/kubernetes-sigs/gateway-api/releases/tag/v1.6.3` | VERIFIED | v1.7.0-rc.1 exists; do not pin a pre-release |
| kube-router | 2.1.1 | not adopted | Kubespray release-2.32 README | VERIFIED | |

## Storage

| Component | Verified version | Pinned | Official source | Status | Notes |
|---|---|---|---|---|---|
| Ceph (upstream latest release) | v21.2.0 | UNVERIFIED | `https://github.com/ceph/ceph/releases` | VERIFIED | Tags v21.3.0 / v21.2.0 / v21.1.2 exist; the "latest" release feed and the tag list disagree — confirm before pinning |
| Ceph Squid (active) | 19.2.7 | UNVERIFIED | `https://docs.ceph.com/en/latest/releases/` | VERIFIED | EOL estimated 2026-10-31 — near end of life, do not start a new deployment on Squid |
| Ceph Tentacle (active) | 20.2.4 | candidate | Same page | VERIFIED | EOL estimated 2027-06-01. The current long-lived target |
| Ceph Reef | 18.2.8 | not adopted | Same page | VERIFIED | End of life |
| Rook | v1.21.0 | v1.21.0 | `https://github.com/rook/rook/releases/tag/v1.21.0` | VERIFIED | The Ceph version shipped by this Rook release must be read from the release notes before setting `cephVersion.image`; that pairing is the single most common cause of a failed Rook upgrade |
| Rook Helm chart | UNVERIFIED | UNVERIFIED | Rook release page | UNVERIFIED | Procedure: read the chart version from the Rook release notes for v1.21.0, then confirm against `https://charts.rook.io/release/index.yaml` |
| ceph-csi | UNVERIFIED | UNVERIFIED | `https://quay.io/cephcsi` | UNVERIFIED | Procedure: read the cephcsi version from the pinned Rook release's `cluster.yaml` example, then confirm the image tag exists in the registry |
| Velero | v1.18.4 | v1.18.4 | `https://github.com/velero-io/velero/releases/tag/v1.18.4` | VERIFIED | Chart 12.2.1 (app 1.18.2) from `https://vmware-tanzu.github.io/helm-charts/index.yaml` |

## Management, GitOps, identity, secrets

| Component | Verified version | Pinned | Official source | Status | Notes |
|---|---|---|---|---|---|
| Argo CD | v3.5.6 | v3.5.6 | `https://github.com/argoproj/argo-cd/releases/tag/v3.5.6` | VERIFIED | v3.6.0-rc4 exists; do not pin a pre-release |
| Argo CD Helm chart | 10.10.5 (app v3.5.5) | 10.10.5 | `https://argoproj.github.io/argo-helm/index.yaml` | VERIFIED | |
| Argo CD ApplicationSet chart | 1.12.1 | 1.12.1 | Same index | VERIFIED | |
| Argo CD (Kubespray-managed) | 2.14.5 | not adopted | Kubespray release-2.32 README | VERIFIED | Kubespray ships an older Argo CD; the platform installs its own chart instead |
| Rancher | v2.15.2 | v2.15.2 | `https://github.com/rancher/rancher/releases/tag/v2.15.2` | VERIFIED | Chart 2.15.2 from `https://releases.rancher.com/server-charts/stable/index.yaml` |
| Keycloak | 26.8.1 | 26.8.1 | `https://github.com/keycloak/keycloak/releases/tag/26.8.1` | VERIFIED | |
| GitLab CE | 19.5.1 | 19.5.1 | `https://docs.gitlab.com/releases/19/gitlab-19-5-released/` and the critical patch release page for 19.5.1 | VERIFIED | Monthly release 19.5 on 2026-10-15; patch 19.5.1 on 2026-10-21 |
| Harbor | v2.15.4 | v2.15.4 | `https://github.com/goharbor/harbor/releases/tag/v2.15.4` | VERIFIED | |
| Sonatype Nexus Repository | release-3.97.1-02 | release-3.97.1-02 | `https://github.com/sonatype/nexus-public/releases` | VERIFIED | |
| HashiCorp Vault | v2.2.0 | v2.2.0 | `https://github.com/hashicorp/vault/releases/tag/v2.2.0` | VERIFIED | Platform standard. Community edition (BSL 1.1). Edition selection and the license position: `secrets-management/vault/hashicorp-vault-decision.md` |
| Vault Helm chart | 0.34.1 (app 2.0.4) | 0.34.1 | `https://helm.releases.hashicorp.com/index.yaml` | VERIFIED | The chart app version lags the Vault release — the chart is the pinned unit, not the binary |
| OpenBao | v2.7.1 | fallback | `https://github.com/openbao/openbao/releases/tag/v2.7.1` | VERIFIED | MPL-licensed alternative |
| cert-manager | v1.21.2 | v1.21.2 | `https://github.com/cert-manager/cert-manager/releases` | VERIFIED | Chart v1.21.2 from `https://charts.jetstack.io/index.yaml`. A v1.20.4 maintenance release was published more recently than v1.21.2; the 1.21 line is the current feature line |
| cert-manager (Kubespray-managed) | 1.15.3 | not adopted | Kubespray release-2.32 README | VERIFIED | Older than the standalone chart |
| External Secrets Operator | v2.13.0 | v2.13.0 | `https://github.com/external-secrets/external-secrets/releases/tag/v2.13.0` | VERIFIED | Chart 2.13.0 from `https://charts.external-secrets.io/index.yaml` |
| Sealed Secrets | v0.40.0 | optional | `https://github.com/bitnami-labs/sealed-secrets/releases` | VERIFIED | Bootstrap-static only |

### Vault licensing (verified 2026-10-17)

- HashiCorp announced the change from MPL 2.0 to BSL 1.1 on 2023-08-10 (`https://www.hashicorp.com/en/blog/hashicorp-adopts-business-source-license`).
- The Vault LICENSE file states: "Licensed Work: Vault, Version 1.15.0 or later. The Licensed Work is (c) 2024 IBM Corp." — so every Vault release from 1.15.0 onward is BSL 1.1, with the licensor now IBM.
- Change Date: four years from the first public distribution of each version, at which point that version becomes MPL 2.0.
- Additional Use Grant: production use is permitted provided the use is not a "competitive offering" as defined. Internal enterprise use is not a competitive offering.
- Consequence for this platform: internal use is permitted under the BSL grant. Redistribution to third parties as a hosted service is not. Legal must confirm the interpretation for the site's specific use.
- OpenBao is the MPL-licensed alternative if legal rejects the BSL. The deployment model in `secrets-management/vault/vault-architecture.md` is portable; only Consul integration and Vault-Enterprise-only features are not.

## Observability, logging, security

| Component | Verified version | Pinned | Official source | Status | Notes |
|---|---|---|---|---|---|
| kube-prometheus-stack | chart 92.11.0 (app v0.94.1) | chart 92.11.0 | `https://prometheus-community.github.io/helm-charts/index.yaml` | VERIFIED | Chart version is the pin |
| Prometheus Operator | v0.94.1 | via the stack | Same index | VERIFIED | |
| Prometheus | v3.15.1 | via the stack | `https://github.com/prometheus/prometheus/releases` | VERIFIED | Prometheus 3.x |
| Alertmanager | v0.34.1 | via the stack | `https://github.com/prometheus/alertmanager/releases` | VERIFIED | |
| node_exporter | v1.12.1 | via the stack | `https://github.com/prometheus/node_exporter/releases` | VERIFIED | |
| kube-state-metrics | v2.20.0 | via the stack | `https://github.com/kubernetes/kube-state-metrics/releases` | VERIFIED | |
| Grafana | 13.2.4 | 13.2.4 | `https://github.com/grafana/grafana/releases` | VERIFIED | Chart 10.5.15 (app 12.3.1) from `https://grafana.github.io/helm-charts/index.yaml` — the chart app version lags the Grafana release |
| Thanos | v0.42.4 | v0.42.4 | `https://github.com/thanos-io/thanos/releases` | VERIFIED | Chart 0.47.3 |
| Loki | v3.7.9 | v3.7.9 | `https://github.com/grafana/loki/releases` | VERIFIED | Chart 7.5.0 (app 3.6.16) |
| Fluent Bit | v5.1.5 | v5.1.5 | `https://github.com/fluent/fluent-bit/releases` | VERIFIED | Chart 0.58.3 (app 5.1.3) |
| OpenSearch | 2.19.7 | optional | `https://github.com/opensearch-project/OpenSearch/releases` | VERIFIED | Only where full-text search is required |
| OPA Gatekeeper | v3.23.1 | v3.23.1 | `https://github.com/open-policy-agent/gatekeeper/releases` | VERIFIED | Chart 3.23.1 |
| Kyverno | v1.19.2 | v1.19.2 | `https://github.com/kyverno/kyverno/releases` | VERIFIED | Chart 3.9.2 |
| Falco | 0.45.1 | 0.45.1 | `https://github.com/falcosecurity/falco/releases` | VERIFIED | Chart 9.2.1 |
| Trivy | v0.76.1 | v0.76.1 | `https://github.com/aquasecurity/trivy/releases` | VERIFIED | Vulnerability DB is a separate, dated artifact |
| Syft | v1.55.0 | v1.55.0 | `https://github.com/anchore/syft/releases` | VERIFIED | SBOM generation |
| Cosign | v3.1.4 | v3.1.4 | `https://github.com/sigstore/cosign/releases` | VERIFIED | Sigstore trust root is a separate, pinned artifact |
| Grype | v0.121.0 | not adopted | `https://github.com/anchore/grype/releases` | VERIFIED | Alternative to Trivy |

## Additional verified components (not in the core platform)

| Component | Verified version | Official source | Status | Notes |
|---|---|---|---|---|
| Calico | v3.33.0 | `https://github.com/projectcalico/calico/releases` | VERIFIED | Upstream current. Kubespray release-2.32 ships 3.31.7 |
| Helm (upstream current) | v4.3.1 | `https://github.com/helm/helm/releases` | VERIFIED | Helm 4 is the current stable line |
| VictoriaMetrics | v1.154.1 | `https://github.com/VictoriaMetrics/VictoriaMetrics/releases` | VERIFIED | Long-term metrics alternative to Thanos |
| KServe | v0.21.0 | `https://github.com/kserve/kserve/releases` | VERIFIED | Inference platform, if multi-framework serving is needed |
| OpenTelemetry Collector | v0.164.x | `https://github.com/open-telemetry/opentelemetry-collector-releases` | VERIFIED | Telemetry collector |
| Elasticsearch | 9.5.5 | `https://github.com/elastic/elasticsearch/releases` | VERIFIED | Not adopted; OpenSearch preferred on licensing grounds |
| Logstash | 9.5.5 | `https://github.com/logstash/logstash/releases` | VERIFIED | Not adopted |
| secrets-store-csi-driver | v1.5.7 | `https://github.com/kubernetes-sigs/secrets-store-csi-driver/releases` | VERIFIED | Secret delivery method 3 |
| sigstore (root signing) | v1.11.1 | `https://github.com/sigstore/sigstore/releases` | VERIFIED | Trust root distribution |
| DCGM Exporter | 4.8.4 | `https://github.com/NVIDIA/dcgm-exporter/releases` | VERIFIED | GPU metrics; version is tied to the GPU Operator release |
| Vault Kubernetes auth (helm) | v1.7.6 | `https://github.com/hashicorp/vault-k8s/releases` | VERIFIED | Vault injector and agent chart |

## Platform add-ons

| Component | Version | Pinned | Official source | Status | Notes |
|---|---|---|---|---|---|
| external-dns | 1.23.0 | chart 1.23.0 | `https://github.com/kubernetes-sigs/external-dns/releases` | VERIFIED | RFC2136 against the internal DNS, or the CoreDNS etcd provider. No public provider in an air-gapped site |
| Descheduler | v0.37.0 | v0.37.0 | `https://github.com/kubernetes-sigs/descheduler/releases` | VERIFIED | Run in DryRun for one week before enabling eviction |
| Vertical Pod Autoscaler | 0.15.0 | chart 0.15.0 | `https://github.com/kubernetes/autoscaler/releases` | VERIFIED | Recommendation mode by default. Auto mode restarts pods and is not for stateful workloads |
| Metrics Server | 3.14.0 | chart 3.14.0 | `https://github.com/kubernetes-sigs/metrics-server/releases` | VERIFIED | Required by HPA and by the VPA recommender |
| OpenTelemetry Operator | v0.161.0 | v0.161.0 | `https://github.com/open-telemetry/opentelemetry-operator/releases` | VERIFIED | Collector only. Traces go to Tempo, not to a second metrics pipeline |
| Trivy Operator | v0.36.0 | v0.36.0 | `https://github.com/aquasecurity/trivy-operator/releases` | VERIFIED | Vulnerability and config scans as CRDs. Needs the internal DB mirror or offline mode |

## End-of-life and retirement watchlist

| Component | Status | Date | Source | Action |
|---|---|---|---|---|
| kubernetes/ingress-nginx (community) | **Retired** | March 2026 | `https://kubernetes.io/blog/2025/11/11/ingress-nginx-retirement/` | Do not adopt. Migrate to F5 NGINX Ingress Controller or NGINX Gateway Fabric. No further releases or security fixes |
| Helm 3 | Support mode | Final feature release 2026-09-09; security fixes end 2027-02-10 | `https://helm.sh/blog/helm-v3-end-of-life` | Plan the Helm 4 migration before 2027-02-10. Kubespray release-2.32 ships Helm 3.22.0 |
| Ceph Squid (19.x) | End of life | Estimated 2026-10-31 | `https://docs.ceph.com/en/latest/releases/` | Do not start a new deployment on Squid. Use Tentacle (20.x) or the version the pinned Rook release supports |
| Ceph Tentacle (20.x) | Active | EOL estimated 2027-06-01 | Same | The current long-lived target |
| Rook 1.20.x | Maintenance | n/a | `https://github.com/rook/rook/releases` | v1.20.9 is the latest 1.20 patch. The 1.21 line is current |
| Calico 3.31.x | Superseded upstream | n/a | `https://github.com/projectcalico/calico/releases` | Kubespray ships it; upstream is at 3.33.0 |
| K8s API 6443 etcd ports | Stable | n/a | `https://kubernetes.io/docs/reference/` | Verify per release |
| Vault (BUSL 1.1) | Source-available | 4 years per version | `https://github.com/hashicorp/vault/blob/main/LICENSE` | Internal use permitted. Confirm with legal |

## GPU and AI

| Component | Verified version | Pinned | Official source | Status | Notes |
|---|---|---|---|---|---|
| NVIDIA GPU Operator | 26.7.2 | 26.7.2 | `https://github.com/NVIDIA/gpu-operator/releases` | VERIFIED | Release branch 26.7 |
| NVIDIA k8s-device-plugin | v0.20.1 | v0.20.1 | `https://github.com/NVIDIA/k8s-device-plugin/releases` | VERIFIED | |
| NVIDIA Container Toolkit | v1.20.1 | v1.20.1 | `https://github.com/NVIDIA/nvidia-container-toolkit/releases` | VERIFIED | Must be compatible with the installed driver |
| NVIDIA data center driver branch | R580 (LTSB), R595 (production) | UNVERIFIED | `https://docs.nvidia.com/datacenter/tesla/drivers/latest/supported-drivers-and-cuda-toolkit-versions.html` | VERIFIED for the branch table | R535 EOL June 2026, R580 EOL June 2028, R595 EOL March 2027, R610 EOL August 2026. Pin an exact patch release after the matrix check |
| NVIDIA driver, latest listed release | 595.71.05 (Linux) | UNVERIFIED | `https://docs.nvidia.com/datacenter/tesla/tesla-release-notes-595-71-05/index.html` | VERIFIED | Released 2026-04-28, CUDA 13.x |
| CUDA Toolkit | 13.x with R595; 12.x supported by R580 | UNVERIFIED | Same driver matrix page | VERIFIED | Max CUDA major without forward-compat: CUDA 12 for R535, CUDA 13 for R580/R595/R610 |
| H100/H200 minimum driver for MIG | CUDA 12, R450 (>= 450.80.02) or later | UNVERIFIED for deploy | NVIDIA MIG User Guide, supported GPUs table | VERIFIED | A production branch far above this minimum is required in practice |
| vLLM | v0.32.0 | UNVERIFIED for deploy | `https://github.com/vllm-project/vllm/releases` | VERIFIED | v0.32.1rc0 exists; do not pin a pre-release |
| Istio | 1.31.3 | UNVERIFIED for deploy | `https://github.com/istio/istio/releases` | VERIFIED | Only if the service mesh threshold in ADR-0009 is met |
| Triton Inference Server | 2.73.0 (NGC 26.09) | UNVERIFIED | `https://github.com/triton-inference-server/server/releases` | VERIFIED | |
| llama.cpp | b11819 (build tag) | UNVERIFIED | `https://github.com/ggml-org/llama.cpp/releases` | VERIFIED that the feed publishes build tags rather than semantic versions | Pin by build tag or by the container image digest; there is no semver to pin |
| llama.cpp formats | GGUF (Q4/Q5/Q8 and K-quants) | n/a | llama.cpp documentation | VERIFIED | Not a version claim |

### GPU/CUDA architecture support (verified 2026-10-17)

From the NVIDIA CUDA Toolkit, Driver, and Architecture Matrix:

| Architecture | Compute capability | First CUDA toolkit | Last driver support |
|---|---|---|---|
| Blackwell | 10.0 | CUDA 12.8 | Ongoing |
| Hopper (H100, H200) | 9.0 | CUDA 11.8 | Ongoing |
| Ada | 8.9 | CUDA 11.8 | Ongoing |
| Ampere (A100) | 8.0 / 8.6 | CUDA 11.0 | Ongoing |

## OS and runtime

| Component | Verified version | Pinned | Official source | Status | Notes |
|---|---|---|---|---|---|
| Oracle Linux | 9 | 9 | `https://yum.oracle.com/` | VERIFIED for availability | OL8 has a 4.18 kernel, below the 4.19 recommendation |
| Ubuntu Server | 24.04 LTS | 24.04 LTS | `https://releases.ubuntu.com/` | VERIFIED for availability | 22.04 LTS (5.15 kernel) also supported |
| Python (Ansible control node) | 3.11-3.13 | 3.12 | Kubespray ansible.md | VERIFIED | |

## Kubespray supported release set (five releases in parallel)

Full detail and the deployment model: `kubespray/multi-version-support.md`. Extracted from each release branch's own README and `docs/ansible/ansible.md` by `scripts/kubespray_release_matrix.py` and `scripts/kubespray_ansible_matrix.py`, check date 2026-10-17.

| Kubespray release | Kubernetes (default) | Min Kubernetes | etcd | containerd | Helm | Cilium | Calico | Ansible | Python | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| release-2.28 | 1.32.13 | v1.30 | 3.5.29 | 2.0.7 | 3.16.4 | 1.17.9 | 3.29.7 | >= 2.16.4 | 3.10 - 3.12 | Supported (oldest) |
| release-2.29 | 1.33.10 | v1.30 | 3.5.29 | 2.1.6 | 3.18.4 | 1.18.5 | 3.30.7 | >= 2.17.3 | 3.10 - 3.12 | Supported |
| release-2.30 | 1.34.12 | v1.30 | 3.5.34 | 2.2.10 | 3.18.4 | 1.18.6 | 3.30.7 | >= 2.17.3 | 3.10 - 3.12 | Supported |
| release-2.31 | 1.35.9 | v1.30 | 3.6.15 | 2.2.10 | 3.18.4 | 1.19.3 | 3.31.7 | >= 2.18.0, < 2.19.0 | 3.11 - 3.13 | Supported |
| release-2.32 | 1.36.5 | v1.34.0 | 3.6.15 | 2.3.7 | 3.22.0 | 1.20.3 | 3.31.7 | >= 2.19.0, < 2.20.0 | 3.11 - 3.13 | Supported (default) |

Each release ships with its own pinned component versions. A cluster is bound to the release that built it. The Ansible and Python windows differ per release, so each release gets its own virtualenv.

## External load balancer (edge)

| Component | Verified version | Pinned | Official source | Status | Notes |
|---|---|---|---|---|---|
| Nginx (OSS) | 1.31.8 | 1.31.8 | `https://github.com/nginx/nginx/releases` | VERIFIED | Ubuntu noble ships 1.24.0 |
| HAProxy | 3.2.26 (3.2 branch) | 3.2.26 | `https://www.haproxy.org/download/3.2/src/` | VERIFIED | Ubuntu noble ships 2.8.5. The 3.5 tags in the release feed are development builds, not stable |
| Keepalived | 2.4.3 | 2.4.3 | `https://github.com/acassen/keepalived/releases` | VERIFIED | Ubuntu noble ships 2.2.8 |
| Docker Compose (plugin) | v5.6.1 | v5.6.1 | `https://github.com/docker/compose/releases` | VERIFIED | Edge deployment and CI |
| Docker Engine | 26.x or later | UNVERIFIED | `https://docs.docker.com/engine/release-notes/` | UNVERIFIED | Procedure: read the engine release notes for the pinned version |
| Compose file schema | `name` top-level key, no `version` key | n/a | `https://github.com/compose-spec/compose-spec/blob/main/spec.md` | VERIFIED | The `version` field is obsolete in the Compose specification |

## Component-to-component compatibility constraints that must hold

| Constraint | Rule | Verification |
|---|---|---|
| Kubespray -> Kubernetes | The target K8s version must be in the Kubespray release's supported range (floor v1.34.0 for release-2.32) | Kubespray release README |
| Kubespray -> Ansible | ansible-core 2.19.x with Python 3.11-3.13 | `docs/ansible/ansible.md` |
| Kubespray -> containerd | Use the containerd version the Kubespray release ships (2.3.7 for release-2.32) | Kubespray release README |
| Kubespray -> CNI | Cilium 1.20.3 (or Calico 3.31.7) as shipped by the release | Same |
| Rook -> Ceph | The `cephVersion.image` must be a Ceph version the pinned Rook release supports | Rook release notes for the pinned version — mandatory check before every Rook upgrade |
| Vault chart -> Vault binary | The chart's appVersion defines the Vault binary version; the chart is the pin | `helm show chart vault` |
| Argo CD chart -> Argo CD image | The chart's appVersion defines the image; pin the chart | `helm show chart argo-cd` |
| GPU Operator -> driver | The operator's `driver.version` must have a matching container-toolkit version in the same operator release | GPU Operator release notes |
| MIG -> driver | H100/H200 need driver >= 450.80.02 on a CUDA 12 branch | NVIDIA MIG User Guide |
| vLLM -> driver/CUDA | vLLM must run on a CUDA version supported by the installed driver branch | vLLM install docs for the pinned release |
| GitLab -> runner | The runner major/minor must be supported by the GitLab version | GitLab runner docs for the pinned version |
| Keepalived -> VRRP | Unicast peers need the peer addresses reachable on the interface named in `interface`. Multicast 224.0.0.18 must be confirmed with the network team | `https://www.keepalived.org/documentation/keepalived-conf/` |
| Nginx -> host | `reuseport` needs Linux 3.9+; `net.ipv4.ip_nonlocal_bind=1` is needed to bind the wildcard address and hold it across a VIP move | Nginx core module docs, Kubespray kernel requirements |
| HAProxy -> host | The stats socket and the reload procedure (`USR2` then `USR1`) must be writable by the container user | HAProxy configuration manual |
| Docker Compose -> edge containers | `network_mode: host` plus `NET_ADMIN`, `NET_BROADCAST`, `NET_RAW`, `SYS_MODULE` for keepalived; `pid: host` for correct VRRP state handling | Compose specification, keepalived documentation |
| Keycloak -> PostgreSQL | The Keycloak version must support the PostgreSQL major version | Keycloak system requirements for the pinned version |
| Kubespray -> OS | The OS must be in the Kubespray release's supported OS list | Kubespray release README |

## Known-unverified items and their procedures

| Item | Procedure to verify |
|---|---|
| Exact Kubernetes patch to deploy | Read the Kubespray release's supported-version list, then confirm the patch appears in `kubernetes/kubernetes` releases |
| Rook chart version | Rook release notes for the pinned Rook version |
| cephcsi image tag | The pinned Rook release's `cluster/examples/kubernetes/ceph/cluster.yaml` example |
| Ceph version to deploy | Ceph active-release table, filtered to the version the pinned Rook release supports |
| NVIDIA driver patch version | The NVIDIA driver release notes index for the chosen branch, then the driver support matrix page |
| vLLM version and its minimum driver | The vLLM release's install requirements |
| Grype version | The Grype releases page |
| Kubespray container image tag for v2.32.0 | The quay.io tag list for `kubespray/kubespray` |
| NVIDIA Container Toolkit distro package name | The NVIDIA container toolkit install documentation for the chosen OS release |

## Version pinning policy

- Production uses exact versions. No `latest` tags, no floating Git references, no unpinned Helm charts.
- Container images are deployed by digest wherever the platform supports it.
- Every pin has a row in this file, a source URL, and a check date.
- A version bump is an MR that updates this file, the artifact matrix, and the component guide in the same change.
- Upgrading a component to a version that is not in this file requires the compatibility checks in the "Component-to-component compatibility constraints" table first.
