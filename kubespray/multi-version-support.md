# Kubespray multi-version support

**Check date: 2026-10-17.** All values extracted from each release branch's own README and `docs/ansible/ansible.md` by `scripts/kubespray_release_matrix.py` and `scripts/kubespray_ansible_matrix.py`.

## Why five versions

A Kubespray release pins the exact Kubernetes, etcd, containerd, CNI, and Helm versions it was tested with. A single pinned release means a single point of failure: when that release ages out, or when a site needs a Kubernetes version that release cannot deploy, the whole estate is blocked on one upgrade.

The platform therefore supports **five Kubespray release branches at once**: `release-2.28` through `release-2.32`. Each is a complete, deployable, offline-capable configuration.

## The support matrix

| Kubespray release | Kubernetes (default) | Min Kubernetes | etcd | containerd | Helm | Cilium | Calico | Ansible | Python |
|---|---|---|---|---|---|---|---|---|---|
| release-2.32 | 1.36.5 | v1.34.0 | 3.6.15 | 2.3.7 | 3.22.0 | 1.20.3 | 3.31.7 | >= 2.19.0, < 2.20.0 | 3.11 - 3.13 |
| release-2.31 | 1.35.9 | v1.30 | 3.6.15 | 2.2.10 | 3.18.4 | 1.19.3 | 3.31.7 | >= 2.18.0, < 2.19.0 | 3.11 - 3.13 |
| release-2.30 | 1.34.12 | v1.30 | 3.5.34 | 2.2.10 | 3.18.4 | 1.18.6 | 3.30.7 | >= 2.17.3 | 3.10 - 3.12 |
| release-2.29 | 1.33.10 | v1.30 | 3.5.29 | 2.1.6 | 3.18.4 | 1.18.5 | 3.30.7 | >= 2.17.3 | 3.10 - 3.12 |
| release-2.28 | 1.32.13 | v1.30 | 3.5.29 | 2.0.7 | 3.16.4 | 1.17.9 | 3.29.7 | >= 2.16.4 | 3.10 - 3.12 |

Each row is a full configuration, not just a Kubernetes version. The etcd, containerd, Helm, and CNI versions in a row are the ones that release ships and tests. Do not mix a containerd from one row into an inventory from another.

## Deployment model: one checkout per release

```
kubespray/
├── VERSION                        # the default release for new clusters
├── releases/
│   ├── release-2.28/              # a full git clone at that tag
│   ├── release-2.29/
│   ├── release-2.30/
│   ├── release-2.31/
│   └── release-2.32/
├── inventory/
│   ├── prod/                      # uses release-2.32
│   ├── prod-legacy/               # uses release-2.29
│   └── staging/
└── virtualenvs/
    ├── release-2.28-venv/         # ansible 2.16.x, python 3.11
    ├── ...
    └── release-2.32-venv/         # ansible 2.19.x, python 3.12
```

Rule: **one virtualenv per Kubespray release.** The Ansible version differs between releases (2.16.4 to 2.19.0), and a shared virtualenv will break one of them. Each venv installs that release's own `requirements.txt`.

```bash
# Per-release environment
for r in 2.28 2.29 2.30 2.31 2.32; do
  python3 -m venv /opt/kubespray/venvs/release-$r
  /opt/kubespray/venvs/release-$r/bin/pip install -r /opt/kubespray/releases/release-$r/requirements.txt
done
```

Each venv also needs the platform's own collection and role versions, installed from the internal Nexus.

## Inventory model: one inventory per (cluster, release) pair

A cluster is bound to the Kubespray release that built it. The binding is recorded in the inventory directory name and in a `kubespray-release` marker in the cluster's group vars.

```
inventory/
├── prod/                    # release-2.32
│   ├── hosts.ini
│   └── group_vars/
├── prod-legacy/             # release-2.29, pinned until the site migrates
│   ├── hosts.ini
│   └── group_vars/
│       └── all/
│           └── kubespray-release.yml
└── staging/                 # release-2.32
```

```yaml
# group_vars/all/kubespray-release.yml
kubespray_release: release-2.29
kubernetes_target: v1.33.10
```

Why one inventory per pair rather than one inventory with a variable:

- The group-vars differ between releases (variable names change). A single inventory would accumulate conditional variables for five releases, and every run would carry dead configuration.
- A rerun must reproduce the cluster exactly as it was built. The inventory is that record.
- Upgrading a cluster to a newer Kubespray release is a separate operation with its own change record.

## Offline artifacts: one set per release

Each release needs its own image set and file tree, because the component versions differ.

```
files_repo/
├── release-2.28/
│   ├── github.com/
│   ├── dl.k8s.io/
│   ├── storage.googleapis.com/
│   ├── get.helm.sh/
│   └── helm.cilium.io/
├── release-2.29/
...
```

The `files_repo` URL carries the release in the path, exactly as the Kubespray offline guide recommends, so an upgrade does not change the base URL.

Image sets are per release and per containerd version. The `kube-apiserver`, `kube-controller-manager`, `kube-scheduler`, and `kube-proxy` images differ per Kubernetes version, and the CNI, etcd, and pause images differ per release. The Kubespray `contrib/offline/generate_list.sh` script produces the list per release; run it in each release's checkout.

Harbor layout that keeps the versions distinguishable:

```
harbor.internal/
├── kubespray/release-2.28/     # mirrors upstream repository paths
├── kubespray/release-2.29/
├── kubespray/release-2.30/
├── kubespray/release-2.31/
├── kubespray/release-2.32/
└── platform/                    # everything that is not Kubespray-managed
```

Because each release's images are mirrored under the **same upstream repository path** inside a per-release project, the inventory for that release points at its own project with no per-image overrides.

## Lifecycle of a supported release

| Stage | Meaning | Duration | Action |
|---|---|---|---|
| Supported | Fully deployable, upgrades in, security fixes tracked | Current + 4 predecessors | New clusters may use it. Upgrades in are allowed from the next-newer release only |
| Maintenance | Deployable for new clusters, but no new clusters should adopt it | Until the successor's successor ships | Freeze the inventory. Continue mirroring artifacts. Plan the migration |
| Deprecated | Deployable for rebuilds only. Not for new clusters and not for upgrades | 3 months after entering Maintenance | Artifact mirror retained. New installs blocked by policy |
| Retired | Removed from the platform | At the end of Deprecation | Artifacts and the checkout archived offline |

Rules:

- A release leaves "Supported" only when a fifth successor exists. That is what keeps five versions supported.
- A release stays in "Supported" for at least 12 months after its successor ships, unless a critical CVE in the pinned Kubernetes version forces an earlier exit. A CVE forces an emergency exit, and that exit is recorded with the CVE.
- A Kubernetes version that reaches end of life removes that combination from the matrix immediately. The Kubespray release stays, but the Kubernetes version is no longer deployable.

## Kubernetes version coverage across the five releases

```
release-2.28  ->  Kubernetes 1.32.x
release-2.29  ->  Kubernetes 1.33.x
release-2.30  ->  Kubernetes 1.34.x
release-2.31  ->  Kubernetes 1.35.x
release-2.32  ->  Kubernetes 1.36.x  (floor v1.34.0)
```

Together they cover five consecutive Kubernetes minor versions. A cluster that must stay on an older Kubernetes minor (a vendor support constraint, a workload that has not been certified on a newer version) is still deployable, and the platform can rebuild it.

## Upgrade ladder

Kubernetes supports one minor of skew in each direction, so a cluster moves one minor at a time. The ladder across the supported releases:

```
release-2.28 (1.32)  ->  release-2.29 (1.33)  ->  release-2.30 (1.34)
     ->  release-2.31 (1.35)  ->  release-2.32 (1.36)
```

Procedure for one step:

1. Create a new inventory directory for the target release, copying the hosts and the site-specific group vars.
2. Set `kubespray_release` and `kubernetes_target` in the new inventory.
3. Mirror the target release's artifacts and pull-verify them.
4. Run the target release's `cluster.yml` against the new inventory, with the target release's venv.
5. Validate: `kubectl get nodes`, `kubectl get pods -A`, the CSI and CNI versions, and the application smoke tests.
6. Keep the old inventory and the old release checkout until the validation window closes.

The Ansible version changes between some steps (2.17.3 -> 2.18.0 -> 2.19.0). The venv is per release, so each step uses its own.

## Validation of the support matrix

```bash
# The extracted matrix, refreshed from upstream
python3 scripts/kubespray_release_matrix.py release-2.28 release-2.29 release-2.30 release-2.31 release-2.32
python3 scripts/kubespray_ansible_matrix.py release-2.28 release-2.29 release-2.30 release-2.31 release-2.32

# The offline artifacts for a release are present
for r in 2.28 2.29 2.30 2.31 2.32; do
  test -d "files_repo/release-$r" || echo "MISSING files_repo for release-$r"
done
```

## Best practices

Mandatory:
- One checkout, one virtualenv, and one inventory per Kubespray release.
- The Kubernetes, etcd, containerd, CNI, and Helm versions in an inventory are the ones that release ships. Do not mix.
- The release in use is recorded in the inventory and in the cluster's own labels.
- Artifacts for every supported release are mirrored and pull-verified, not just the current one.
- A cluster moves one Kubernetes minor at a time.

Strongly recommended:
- The deprecated-stage release list is reviewed at every platform release meeting, and the resulting decision is recorded as an ADR amendment.
- A rebuild drill against the oldest supported release, at least annually, to prove the estate can be rebuilt on a pinned older combination.
- The per-release `files_repo` trees are stored on the offline media as well as the internal mirror.
