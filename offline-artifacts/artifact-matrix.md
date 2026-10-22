# Offline Artifact Matrix

One row per component-artifact pair. All values pinned. Source URL and check date are mandatory; a row without them is a defect.

Status: `MIRRORED` = present in the internal system and pull-verified. `STAGED` = downloaded in connected staging, not yet imported. `PENDING` = identified, not yet fetched. `EXEMPT` = no artifact needed (document the reason).

## Conventions

- **Internal destination**: exact repository path in Harbor or Nexus.
- **Integrity**: checksum file and/or signature type.
- **Refresh**: how the artifact is updated and how often.
- **Validation**: the command that proves offline availability.

## Kubernetes platform

| Component | Version | Artifact type | Official source | Internal destination | Dependencies | Download procedure | Integrity | Configuration | Refresh | Validation |
|---|---|---|---|---|---|---|---|---|---|---|
| Kubernetes | pin per version matrix | OCI (control plane + core) | `https://registry.k8s.io` | `harbor.internal/platform/kubernetes` | none beyond the image itself | `skopeo copy` per image | digest pinned | containerd `hosts.toml` mirror | per K8s release | `crictl pull harbor.internal/...` |
| Kubespray | tag per `kubespray/VERSION` | Git | `https://github.com/kubernetes-sigs/kubespray` | `gitlab.internal/platform/kubespray` (mirror) | Ansible, Python, `requirements.txt` wheels | `git clone --mirror` | commit SHA recorded | `ansible.cfg` galaxy server | per release | `ansible --version` + `ansible-galaxy collection list` |
| Kubespray images (all roles) | derived | OCI | upstream registries per role | `harbor.internal/platform/kubespray-images` | containerd, runc, CNI, etcd, pause | capture from staging deploy | digest pinned | containerd mirror | per release | scripted pull loop |
| etcd | pin | OCI + binary | `https://github.com/etcd-io/etcd` | `harbor.internal/platform/etcd` | none | `skopeo copy` | digest | — | per release | `etcd --version` |
| containerd | pin | RPM/DEB + binary | `https://github.com/containerd/containerd` | `nexus.internal/rpm`, `nexus.internal/deb` | runc, CNI plugins | `dnf download --resolve` / `apt download` | RPM/DEB signature | `containerd/config.toml` | per release | `containerd --version` |
| CNI plugins | pin | RPM/DEB + binary | `https://github.com/containernetworking/plugins` | `nexus.internal/rpm`, `nexus.internal/deb` | none | `dnf download --resolve` | RPM/DEB signature | Kubespray `cni_plugins_version` | per release | `/opt/cni/bin/*` present |
| Helm | pin (CLI 3.22.0 in Kubespray; 4.x for the operator tooling) | binary + tar | `https://get.helm.sh` | `nexus.internal/raw` | none | `curl` | sha256 from release page | `HELM_*` env | per release | `helm version` | Helm 3 security fixes end 2027-02-10; plan the Helm 4 migration |
| kubectl | pin | binary | `https://dl.k8s.io` | `nexus.internal/raw` | none | `curl` | sha256 | — | per release | `kubectl version --client` |

## Storage

| Component | Version | Artifact type | Official source | Internal destination | Dependencies | Download procedure | Integrity | Configuration | Refresh | Validation |
|---|---|---|---|---|---|---|---|---|---|---|
| Ceph (cephadm path) | pin | RPM/DEB | `https://download.ceph.com` | `nexus.internal/rpm-ceph`, `nexus.internal/deb-ceph` | libs, ceph-volume, python3-ceph | `dnf download --resolve` | RPM signature | cephadm bootstrap | per Ceph release | `ceph --version` |
| Rook-Ceph operator | pin | OCI | `https://quay.io/rook/ceph` | `harbor.internal/platform/rook-ceph` | operator, CSI, csi-provisioner, cephcsi | `skopeo copy` per image | digest | Helm values | per release | `kubectl -n rook-ceph get pods` |
| ceph-csi | pin | OCI | `https://quay.io/cephcsi` | `harbor.internal/platform/cephcsi` | external-provisioner, snapshotter, resizer, livenessprobe, node-driver-registrar | `skopeo copy` per image | digest | StorageClass | per release | PVC binds |
| Ceph RGW (if used) | pin | RPM/DEB + OCI | as above | as above | radosgw, python3-rgw | `dnf download --resolve` | RPM signature | gateway pool | per release | `curl http://rgw:7480` |

## Management, GitOps, identity, secrets

| Component | Version | Artifact type | Official source | Internal destination | Dependencies | Download procedure | Integrity | Configuration | Refresh | Validation |
|---|---|---|---|---|---|---|---|---|---|---|
| Rancher | pin | Helm chart + OCI | `https://releases.rancher.com/server-charts/stable` | `harbor.internal/charts/rancher` | rancher images | `helm pull` + `skopeo copy` | digest + chart provenance | Helm values | per release | `kubectl -n cattle-system get deploy` |
| Argo CD | pin | OCI manifests | `https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml` | `gitlab.internal/platform/argocd` (vendored) | argocd images | `skopeo copy` per image | digest | Helm values | per release | `argocd version` |
| GitLab CE | pin | OCI / Omnibus | `https://about.gitlab.com/install/` | `harbor.internal/platform/gitlab` | postgres, redis, gitaly, rails images | `skopeo copy` per image | digest | `gitlab.rb` | per release | GitLab health endpoint |
| Keycloak | pin | OCI / RPM | `https://www.keycloak.org/downloads` | `harbor.internal/platform/keycloak` | postgres (external) | `skopeo copy` | digest | realm export | per release | token endpoint returns 200 |
| Harbor | pin | OCI | `https://goharbor.io` | `harbor.internal/platform/harbor` | postgres, redis, registry, jobservice, trivy | `skopeo copy` per image | digest | `harbor.yml` | per release | `curl https://harbor/api/v2.0/health` |
| Nexus Repository | pin | OCI / tar | `https://help.sonatype.com` | `harbor.internal/platform/nexus` | postgres | `skopeo copy` or tar | signature | `nexus.properties` | per release | `curl -I https://nexus` |
| HashiCorp Vault | pin | binary + OCI | `https://releases.hashicorp.com` | `nexus.internal/raw` | vault binary, optional plugins | `curl` + unzip | SHA256SUMS file | systemd unit, config | per release | `vault status` |
| Vault Agent / injector | pin | OCI | `https://hub.docker.com/_/vault` | `harbor.internal/platform/vault-agent` | none | `skopeo copy` | digest | injector flags | per release | injector pod Running |
| OpenBao (fallback) | pin | binary + OCI | `https://github.com/openbao/openbao` | `nexus.internal/raw` | none | `curl` | SHA256SUMS | systemd unit | per release | `bao status` |
| cert-manager | pin | Helm chart + OCI | `https://charts.jetstack.io` | `harbor.internal/charts/cert-manager` | cainjector, webhook, controller images | `helm pull` + `skopeo copy` | digest | Helm values | per release | `cert-manager` pods Ready |
| External Secrets Operator | pin | Helm chart + OCI | `https://charts.external-secrets.io` | `harbor.internal/charts/external-secrets` | ESO images, provider images | `helm pull` + `skopeo copy` | digest | Helm values, SecretStore | per release | `ExternalSecret` reconciles |
| Sealed Secrets | pin | Helm chart + OCI | `https://bitnami-labs.github.io/sealed-secrets` | `harbor.internal/charts/sealed-secrets` | controller image | `helm pull` + `skopeo copy` | digest | Helm values | per release | `SealedSecret` reconciles |

## Networking, monitoring, logging, security

| Component | Version | Artifact type | Official source | Internal destination | Dependencies | Download procedure | Integrity | Configuration | Refresh | Validation |
|---|---|---|---|---|---|---|---|---|---|---|
| Cilium | pin | Helm chart + OCI | `https://helm.cilium.io` | `harbor.internal/charts/cilium` | cilium, operator, hubble images | `helm pull` + `skopeo copy` | digest | Helm values | per release | `cilium status` |
| MetalLB | pin | Helm chart + OCI | `https://metalb-io.github.io/metalb` | `harbor.internal/charts/metallb` | speaker, controller images | `helm pull` + `skopeo copy` | digest | Helm values, IPAddressPool | per release | `LoadBalancer` gets an IP |
| NGINX Ingress (F5) | pin (chart 2.8.0, app 5.7.0) | Helm chart + OCI | `https://github.com/nginx/kubernetes-ingress` (chart from the F5 release) | `harbor.internal/charts/nginx-ingress` | controller, admission webhook images | `helm pull` + `skopeo copy` | digest | Helm values | per release | `kubectl -n ingress-nginx get pods` |
| NGINX Gateway Fabric (optional) | pin | Helm chart + OCI | `https://github.com/nginx/kubernetes-gateway-fabric` | `harbor.internal/charts/nginx-gateway-fabric` | controller, agent, and data-plane images | `helm pull` + `skopeo copy` | digest | Helm values | per release | `kubectl -n nginx-gateway get pods` |
| ingress-nginx (community) | **RETIRED** | Helm chart + OCI | `https://github.com/kubernetes/ingress-nginx` | not mirrored | controller, admission webhook images | n/a | n/a | n/a | never | n/a | Retired March 2026. Do not mirror for new deployments. If an existing estate still runs it, mirror the pinned version for continuity only and plan the migration |
| Gateway API CRDs | pin | YAML | `https://github.com/kubernetes-sigs/gateway-api` | `gitlab.internal/platform/gateway-api` | none | `curl` | commit SHA | CRD apply | per release | `kubectl get gatewayclasses` |
| kube-prometheus-stack | pin | Helm chart + OCI | `https://prometheus-community.github.io/helm-charts` | `harbor.internal/charts/kube-prometheus-stack` | prometheus, alertmanager, exporters, thanos images | `helm pull` + `skopeo copy` | digest | Helm values | per release | Prometheus targets UP |
| Grafana | pin | OCI + Helm chart | `https://grafana.com/grafana` | `harbor.internal/platform/grafana` | postgres (optional) | `skopeo copy` | digest | Helm values, datasources | per release | `/api/health` ok |
| Thanos | pin | OCI | `https://quay.io/thanos` | `harbor.internal/platform/thanos` | object storage | `skopeo copy` | digest | sidecar flags | per release | `thanos query` returns data |
| Loki + Fluent Bit | pin | OCI + Helm chart | `https://grafana.com/loki`, `https://fluentbit.io` | `harbor.internal/platform/loki` | promtail/fluent-bit images, chart | `helm pull` + `skopeo copy` | digest | Helm values | per release | log query returns entries |
| OpenSearch (optional) | pin | OCI + tar | `https://opensearch.org` | `harbor.internal/platform/opensearch` | JVM heap config | `skopeo copy` / tar | signature | `opensearch.yml` | per release | `_cluster/health` green |
| OPA Gatekeeper | pin | Helm chart + OCI | `https://open-policy-agent.github.io/gatekeeper` | `harbor.internal/charts/gatekeeper` | gatekeeper images | `helm pull` + `skopeo copy` | digest | Helm values, constraints | per release | violation denied |
| Kyverno | pin | Helm chart + OCI | `https://kyverno.github.io/kyverno` | `harbor.internal/charts/kyverno` | kyverno images | `helm pull` + `skopeo copy` | digest | Helm values, policies | per release | policy enforced |
| Falco | pin | OCI + Helm chart | `https://falco.org` | `harbor.internal/charts/falco` | falco, driver loader images | `helm pull` + `skopeo copy` | digest | Helm values, rules file | per release | test alert fires |
| Trivy | pin | RPM/DEB + OCI + DB | `https://github.com/aquasecurity/trivy` | `nexus.internal/rpm`, `harbor.internal/security/trivy-db` | vuln DB, DB metadata | `trivy image --download-db-only` | DB checksum (from OCI manifest) | `TRIVY_DB_REPOSITORY` | monthly | `trivy image --skip-db-update` works offline |
| Grype | pin | binary + DB | `https://github.com/anchore/grype` | `nexus.internal/raw` | DB (dated snapshot) | `grype db update` in staging | DB checksum | `GRYPE_DB_*` | monthly | `grype dir:.` works offline |
| Syft | pin | binary | `https://github.com/anchore/syft` | `nexus.internal/raw` | none | `curl` | sha256 | — | per release | `syft dir:. -o cyclonedx-json` |
| Cosign | pin | binary + OCI | `https://github.com/sigstore/cosign` | `nexus.internal/raw` | Rekor/trust root (bundle offline) | `curl` | sha256 | `COSIGN_REPOSITORY` | per release | `cosign verify` offline with bundled root |

## GPU and AI

| Component | Version | Artifact type | Official source | Internal destination | Dependencies | Download procedure | Integrity | Configuration | Refresh | Validation |
|---|---|---|---|---|---|---|---|---|---|---|
| NVIDIA driver | pin (branch) | RPM | `https://us.download.nvidia.com` | `nexus.internal/rpm-nvidia` | kernel headers matching the node kernel | `dnf download --resolve` | NVIDIA signature | `nvidia-modprobe`, kmod | per driver | `nvidia-smi` |
| NVIDIA CUDA toolkit (container) | pin | OCI | `nvcr.io/nvidia/cuda` | `harbor.internal/platform/cuda` | cudnn, cublas images for runtime | `skopeo copy` per image | digest | containerd runtime config | per release | `nvidia-smi` in pod |
| NVIDIA Container Toolkit | pin | RPM/DEB + OCI | `https://nvidia.github.io/libnvidia-container` | `nexus.internal/rpm`, `harbor.internal/platform/nvidia-container-toolkit` | nvidia-container-runtime, k8s-device-plugin | `dnf download --resolve` | RPM signature | `nvidia-ctk runtime configure` | per release | `nvidia-smi` in pod |
| GPU Operator | pin | Helm chart + OCI | `https://nvidia.github.io/gpu-operator` | `harbor.internal/charts/gpu-operator` | driver, toolkit, device plugin, dcgm-exporter, k8s-device-plugin images | `helm pull` + `skopeo copy` per image | digest | Helm values | per release | `kubectl -n gpu-operator get pods` |
| DCGM Exporter | pin | OCI | `https://nvcr.io/nvidia/k8s/dcgm-exporter` | `harbor.internal/platform/dcgm-exporter` | none | `skopeo copy` | digest | Service + ServiceMonitor | per release | `:9400/metrics` returns data |
| vLLM | pin | OCI | `https://quay.io/vllm` or `https://hub.docker.com/r/vllm` | `harbor.internal/platform/vllm` | CUDA runtime image, weights | `skopeo copy` | digest | `VLLM_*` env, model path | per release | `/v1/models` responds |
| llama.cpp | pin | OCI | `https://ghcr.io/ggml-org/llama.cpp` | `harbor.internal/platform/llama-cpp` | none | `skopeo copy` | digest | model GGUF path | per release | server responds |
| Triton | pin | OCI | `nvcr.io/nvidia/tritonserver` | `harbor.internal/platform/triton` | backend images | `skopeo copy` | digest | model repository layout | per release | `/v2/health/ready` |
| Model weights | revision SHA | S3 object | `https://huggingface.co` | RGW bucket `models/` (or MinIO) | none | `huggingface-cli download --revision <sha>` | SHA256 per file in manifest | RGW endpoint, credentials from Vault | per model release | `curl -I` + checksum match |

## Operating system packages

| Component | Version | Artifact type | Official source | Internal destination | Dependencies | Download procedure | Integrity | Configuration | Refresh | Validation |
|---|---|---|---|---|---|---|---|---|---|---|
| Oracle Linux packages | 8/9 | RPM | `https://yum.oracle.com` (ULN) | `nexus.internal/rpm-oraclelinux` | none (mirror with deps) | `dnf download --resolve` | RPM signature + repo GPG | `/etc/yum.repos.d/internal.repo` | monthly | `dnf install` offline |
| RHEL-compatible packages | pin | RPM | Red Hat CDN (entitled) | `nexus.internal/rpm-rhel` | entitlement required | Satellite or `subscription-manager` download | RPM signature | `internal.repo` | monthly | `dnf install` offline |
| Ubuntu packages | 22.04/24.04 | DEB | `http://archive.ubuntu.com` | `nexus.internal/deb-ubuntu` | none (mirror with deps) | `apt-get download` + `apt-rdepends` | repo `Release.gpg` | `/etc/apt/sources.list.d/internal.*` | monthly | `apt-get install` offline |
| Python wheels | pinned | PyPI | `https://pypi.org` | `nexus.internal/pypi` | transitive wheels | `pip download -r requirements.txt` | wheel hashes | `pip.conf` | per release | `pip install --no-index` |
| Ansible collections | pinned | Galaxy | `https://galaxy.ansible.com` | `nexus.internal/ansible-galaxy` + vendored tarballs in GitLab | transitive collections | `ansible-galaxy collection download -r requirements.yml` | galaxy metadata | `ansible.cfg` | per release | `ansible-galaxy collection list` |

## External load balancer (edge)

| Component | Version | Artifact type | Official source | Internal destination | Dependencies | Download procedure | Integrity | Configuration | Refresh | Validation |
|---|---|---|---|---|---|---|---|---|---|---|
| Nginx (edge) | pin (1.31.8) | OCI | `https://hub.docker.com/_/nginx` | `harbor.internal/edge/nginx` | none (static binary image) | `skopeo copy` | digest | `manifests/external-lb/nginx.conf` | per release | `nginx -t` in the container |
| HAProxy (edge) | pin (3.2.26) | OCI | `https://hub.docker.com/_/haproxy` | `harbor.internal/edge/haproxy` | none | `skopeo copy` | digest | `manifests/external-lb/haproxy.cfg` | per release | `haproxy -c -f ...` in the container |
| Keepalived (edge) | pin (2.4.3) | OCI | `https://hub.docker.com/r/acassen/keepalived` | `harbor.internal/edge/keepalived` | iproute2, iptables (in the image) | `skopeo copy` | digest | `manifests/external-lb/keepalived.conf` + `keepalived.d/` | per release | `docker logs edge-keepalived` shows a MASTER/BACKUP transition |
| Docker Compose (plugin) | pin (v5.6.1) | OCI | `https://github.com/docker/compose/releases` | `harbor.internal/tools/compose` | Docker Engine | `skopeo copy` | digest | CLI plugin directory | per release | `docker compose version` |
| Edge configuration | n/a | Git | `gitlab.internal/platform/edge` | GitLab | none | `git clone` | commit SHA | Compose file, Nginx, HAProxy, keepalived configs | per change | `docker compose config` |
| Edge TLS certificate | n/a | Secret | Vault PKI | Vault | CA chain | Ansible from Vault | cert chain | mounted read-only at `/etc/nginx/certs` | 30d, auto-renewed | `openssl s_client` against the VIP |

## Scanning and signature databases

| Item | Version | Artifact type | Source | Internal destination | Refresh | Validation |
|---|---|---|---|---|---|---|
| Trivy vulnerability DB | dated | OCI | `ghcr.io/aquasecurity/trivy-db` | `harbor.internal/security/trivy-db` | monthly | `trivy --skip-db-update` finds nothing / errors clearly |
| Trivy Java DB | dated | OCI | `ghcr.io/aquasecurity/trivy-db` (java-db tag) | `harbor.internal/security/trivy-db` | monthly | `trivy java` offline |
| Grype DB | dated | OCI/tar | `ghcr.io/anchore/grype-db` | `harbor.internal/security/grype-db` | monthly | `grype` offline scan |
| Sigstore trust root | pinned | bundle | `https://github.com/sigstore/root-signing` | `nexus.internal/raw/sigstore` | on trust root change | `cosign verify` with offline root |

## Rules for maintaining this matrix

1. A row is added when a component is added to the platform, and updated when a version is pinned.
2. Every row requires a source URL and a check date in the version matrix (`compatibility/version-matrix.md`).
3. `PENDING` rows block the phase they belong to. A deployment phase cannot start with a `PENDING` artifact for a component it installs.
4. `MIRRORED` is only claimed after a pull test succeeded in the offline environment. A successful import is not a successful pull.
