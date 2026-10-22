# Deliverable 5 — Offline Artifact Architecture

## 5.1 Repository and registry responsibilities

One owner per artifact type. No duplication.

| Artifact type | System of record (internal) | Upstream source | Mirror/proxy | Notes |
|---|---|---|---|---|
| OCI container images | Harbor | Upstream registries | Harbor proxy-cache from upstream (connected staging only) | Harbor is the only pull target for clusters |
| Helm charts (OCI) | Harbor OCI project | Upstream chart repos | Harbor proxy | Argo CD points at Harbor only |
| Helm charts (classic) | Nexus helm-hosted | Upstream | Nexus proxy | Keep for non-OCI consumers |
| RPM (Oracle Linux, RHEL-compatible) | Nexus rpm-hosted | Oracle / RedHat (entitlement) | Nexus proxy | Requires RedHat subscription for RHEL content; Oracle Linux ULN for UE-K |
| DEB (Ubuntu) | Nexus deb-hosted (apt) | archive.ubuntu.com, security.ubuntu.com | Nexus proxy | Include -updates and -security pockets |
| PyPI | Nexus pypi-hosted | pypi.org | Nexus proxy | Needed for Ansible deps |
| npm (if used) | Nexus npm-hosted | registry.npmjs.org | Nexus proxy | Optional |
| Go modules | Nexus go-hosted | proxy.golang.org | Nexus proxy | Optional |
| Git repositories | GitLab (self-contained groups) | Upstream GitHub/GitLab | Staging clone then push mirror | Use `git bundle`/mirror clone for transfer |
| Ansible collections/roles | Nexus raw-hosted | Galaxy | Nexus proxy | Also vendor tarballs into GitLab for air-gap |
| Security scanner DBs | Nexus raw-hosted | Trivy/Grype/VulnDB upstream | Manual refresh from connected staging | Trivy DB is date-stamped, refresh monthly |
| OS images (cloud) | Nexus raw-hosted | Vendor | Manual | Custom OL/Ubuntu images for cloud-init |
| AI models (weights) | Harbor + S3-compatible object (Ceph RGW or MinIO) | Hugging Face | Manual mirroring | Model artifacts are large, not registry objects |
| AI inference images | Harbor | Upstream | Harbor proxy | Same as any image |
| NVIDIA drivers/toolkit | Nexus raw-hosted | NVIDIA | Manual | Large files, version-pinned per GPU matrix |
| Vault binaries/plugins | Nexus raw-hosted | releases.hashicorp.com | Nexus proxy | Plugin version pinned per Vault version |
| Container base images | Nexus raw-hosted (OCI layout) | Upstream | Manual | Needed to build offline images |

Anti-pattern to avoid: pointing clusters at Nexus for images and Harbor for charts and GitLab for images — three pull paths, three auth schemes, three failure modes.

## 5.2 Staging and import workflow

Context: **Connected staging environment** (steps 1-6) then **offline production environment** (steps 7-10).

1. Resolve exact versions and full dependency set in connected staging.
2. Download artifacts (curl/skopeo/helm pull/ansible-galaxy/git clone).
3. Verify signatures, checksums, provenance.
4. Generate manifest + SBOM.
5. Scan for vulnerabilities and policy violations.
6. Transfer artifacts via approved controlled mechanism.
7. Import into internal repositories and registries.
8. Configure clients to use internal sources.
9. Validate authentication, TLS, image pulls, package install, dependency resolution.
10. Verify deployment and recovery work with no production internet access.

### Commands (staging, connected)

```bash
# OCI image
skopeo copy --dest-daemon=false docker://ghcr.io/OWNER/REPO:TAG \
  docker://harbor.internal/oci/owner-repo:TAG

# Helm chart (OCI)
helm pull oci://ghcr.io/OWNER/charts/CHART --version X.Y.Z -d ./staging/charts

# Ansible collections
ansible-galaxy collection download -r requirements.yml -p ./staging/collections

# Python wheels
pip download -r requirements.txt -d ./staging/wheels

# DEB
apt-get download pkg=version   # plus dependencies via apt-rdepends or apt-offline

# RPM
dnf download --resolve --downloaddir=./staging/rpm pkg

# Git mirror
git clone --mirror https://github.com/OWNER/REPO.git ./staging/git/REPO.git
```

### Integrity and scan (staging)

```bash
# Checksums
sha256sum -c staging/CHECKSUMS

# SBOM
syft dir:./staging -o cyclonedx-json > staging/SBOM.json

# Vulnerability scan
trivy image --input ./staging/oci/owner-repo.tar --format json > staging/trivy.json
trivy fs --scanners vuln --format json ./staging > staging/trivy-fs.json

# Signature verification (where upstream signs)
cosign verify --key cosign.pub harbor.internal/oci/owner-repo:TAG
```

### Transfer (approved controlled mechanism)

| Method | Use | Notes |
|---|---|---|
| `skopeo copy` to Harbor over internal network | Images | Preferred |
| `helm push` to Harbor OCI | Charts | Preferred |
| `curl --upload-file` to Nexus | Packages/raw | Nexus supports it |
| Encrypted USB / controlled media | Only if air-gap has no internal transfer path | Requires chain of custody, encryption, manifest checksum verification on arrival |
| `airgap` containerized skopeo bundle | Common pattern | No external deps on target |

### Import (offline production)

```bash
# Image into Harbor
skopeo copy --dest-daemon=false \
  docker://harbor.internal/oci/owner-repo:TAG \
  docker://harbor.internal/platform/owner-repo:TAG

# Chart into Harbor OCI
helm push owner-chart-X.Y.Z.tgz oci://harbor.internal/charts

# Python wheels
pip install --no-index --find-links=/opt/staging/wheels -r requirements.txt

# Ansible collections
ansible-galaxy collection install -r requirements.yml -p /opt/collections

# DEB
sudo apt-get install -y ./staging/deb/*.deb
```

## 5.3 Client configuration per artifact class

| Client | File | Change needed | Notes |
|---|---|---|---|
| containerd | `/etc/containerd/certs.d/<registry>/hosts.toml` | Yes | Per-registry TLS + mirror config |
| containerd (Kubespray) | `group_vars/k8s_cluster/k8s-cluster.yml` -> `containerd_registries` | Yes | See `kubespray/groups/k8s-cluster.yml` |
| Docker/Podman | `/etc/docker/daemon.json`, `/etc/containers/registries.conf` | Yes | Only if these runtimes exist on the host |
| K8s image pulls | Image field in manifests -> Harbor path | Yes | Argo CD `image` rewrite rules can do this centrally |
| Helm CLI | `helm repo add` | Yes | Point at Harbor OCI or Nexus |
| Argo CD | `Application.spec.source.repoURL` + `destination` | Yes | repoURL to GitLab internal |
| apt | `/etc/apt/sources.list.d/internal.list` | Yes | `https://nexus.internal/repository/deb-ubuntu/ ...` |
| dnf/yum | `/etc/yum.repos.d/internal.repo` | Yes | `baseurl=https://nexus.internal/repository/rpm-oraclelinux/` |
| pip | `/etc/pip.conf` or venv `pip.conf` | Yes | `index-url=https://nexus.internal/repository/pypi/simple` |
| Ansible | `ansible.cfg` + `~/.ansible.cfg` | Yes | `galaxy_server` + `collections_path` |
| git | `~/.gitconfig` `url.<base>.insteadOf` | Optional | Use GitLab internal directly; insteadOf only for mirrors |
| Docker/Buildah | `~/.config/containers/registries.conf` | Yes | Short-name aliases for Harbor |
| CA trust | `/etc/pki/ca-trust/source/anchors/` (OL), `/usr/local/share/ca-certificates/` (Ubuntu) | Yes | `update-ca-trust` / `update-ca-certificates` |
| OpenSSL | `SSL_CERT_FILE` / system store | Yes | Same trust store |
| curl | system CA store | Yes | Same trust store |

### Reverse proxy: what is genuinely transparent

| Upstream | Proxy-transparent? | Notes |
|---|---|---|
| GitHub / GitLab web + git protocol | Yes | L7 reverse proxy preserves paths; git over HTTPS works with `insteadOf` |
| PyPI (pypi.org) | Yes | Simple index layout, `/simple/` path preserved |
| npm registry | Yes | Path preserved |
| Docker Hub / ghcr.io | Partially | Registry API is path-based and proxyable, but client auth flows, token endpoints, and content negotiation need explicit config — treat as "client config required" |
| Quay.io | Partially | Same registry caveats |
| Debian apt archive | Yes | `Release` + `Packages` paths preserved; `Release.gpg` must be signed by the mirror |
| RPM repos (yum/dnf) | Partially | `repodata` and signatures are path-based; repomd signature validation must pass — use Nexus to re-sign |
| Ubuntu PPA | Partially | Launchpad-specific metadata paths, not reliably proxyable — mirror explicitly instead |
| Helm classic repos (`index.yaml` + tarballs) | Yes | Flat file layout |
| OCI registries | Partially | Blob/manifest paths preserved, but auth/token endpoints and redirect behavior are registry-specific — test per registry |
| GitHub Releases (binary downloads) | Yes | Direct file paths |
| RedHat subscription content | No | Requires entitlement-aware tooling (subscription-manager, Satellite); mirror with a licensed copy |
| Hugging Face (model weights) | Partially | LFS/CDN redirect behavior; explicit mirror recommended |

Rule: never claim a reverse proxy transparently replaces a registry. Prove it per registry with an end-to-end pull test in the offline environment, and document the client-side change in the matrix.

## 5.4 Offline artifact matrix

Maintained in `offline-artifacts/artifact-matrix.md` (one row per component-artifact pair).
