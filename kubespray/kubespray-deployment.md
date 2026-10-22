# Kubespray deployment (offline)

## A. Purpose and scope

Kubespray is the cluster lifecycle tool. Ansible deploys the cluster, manages the node OS configuration for the cluster components, and drives version upgrades.

## B. Versions and compatibility

| Item | Value | Status |
|---|---|---|
| Kubespray release | pinned per `kubespray/VERSION` | see `compatibility/version-matrix.md` |
| Ansible core | pinned per `automation/ansible/requirements.txt` | see `compatibility/version-matrix.md` |
| Python on control node | pinned per `automation/ansible/requirements.txt` | see `compatibility/version-matrix.md` |
| Kubernetes | pinned per `kubespray/inventory/<cluster>/group_vars/k8s_cluster/k8s-cluster.yml` | see `compatibility/version-matrix.md` |

Kubespray variables change between releases. Never reuse a group-vars file across a Kubespray release without diffing it against the new release's `inventory/sample`. Procedure: `lifecycle/upgrades/kubespray.md`.

## C. Layout

```
kubespray/
├── VERSION                      # pinned Kubespray release tag
├── inventory/
│   ├── sample/                  # vendored copy of the release's sample inventory
│   └── <cluster>/
│       ├── hosts.ini
│       ├── group_vars/
│       │   ├── all/
│       │   │   ├── main.yml
│       │   │   ├── offline.yml        # image + registry overrides
│       │   │   └── containerd.yml     # registry mirror + TLS config
│       │   ├── k8s_cluster/
│       │   │   ├── k8s-cluster.yml     # version, CNI, networking
│       │   │   └── k8s-cluster-encrypted-images.yml
│       │   ├── etcd/
│       │   ├── kube_node/
│       │   └── k8s_secrets/
│       └── group_vars/all/external.yml
└── patches/                     # site-specific variable overrides, applied deliberately
```

## D. Inventory

`kubespray/inventory/<cluster>/hosts.ini`:

```ini
[all:vars]
ansible_user=ansible
ansible_become=yes
ansible_python_interpreter=/usr/bin/python3

[control-plane]
k8s-cp-1 ansible_host=10.20.0.11 ip=10.20.0.11
k8s-cp-2 ansible_host=10.20.0.12 ip=10.20.0.12
k8s-cp-3 ansible_host=10.20.0.13 ip=10.20.0.13

[etcd]
k8s-cp-1
k8s-cp-2
k8s-cp-3

[k8s-node]
k8s-w-1 ansible_host=10.20.0.21 ip=10.20.0.21
k8s-w-2 ansible_host=10.20.0.22 ip=10.20.0.22

[k8s-node:children]
gpu-node

[gpu-node]
k8s-gpu-1 ansible_host=10.50.0.11 ip=10.50.0.11 labels='{"accelerator":"nvidia"}'

[calico-node]
[k8s-cluster:children]
control-plane
etcd
k8s-node

[kube-node]
control-plane
k8s-node
```

Group membership rules:
- `etcd` members must also be in `control-plane` when etcd is stacked.
- `k8s-node` must contain every worker, including the GPU pool.
- Never list a host in two `k8s-node` groups.

## E. Group vars — core

`group_vars/k8s_cluster/k8s-cluster.yml` (names must be verified against the pinned release's sample):

```yaml
kube_version: v1.31.x            # VERIFY per release
kube_network_plugin: cilium
kube_proxy_mode: ""
enable_coredns: true
kube_pods_subnet: "10.30.0.0/16"
kube_service_addresses: "10.32.0.0/16"
```

`kube_proxy_mode: ""` disables kube-proxy. This is required for Cilium's kube-proxy-free mode. It is a per-release variable name — verify before use.

`group_vars/all/main.yml`:

```yaml
container_manager: containerd
containerd_version: "1.7.x"      # VERIFY per release
containerd_enable_cri: true
kube_pods_subnet: "10.30.0.0/16"
kube_service_addresses: "10.32.0.0/16"
cert_manager: false              # installed by Argo CD, not Kubespray
```

## F. Offline image configuration

Kubespray downloads images from the upstream registry. In an air-gapped environment, mirror every required image and point Kubespray at the internal registry.

Verified against the Kubespray `release-2.32` official offline guide (`docs/operations/offline-environment.md`), check date 2026-10-17.

The upstream guide requires four internal services:

1. An HTTP reverse proxy / cache / mirror serving static files (binaries, zips) — the `files_repo`.
2. An internal Yum/Deb repository for OS packages.
3. An internal container image registry populated with every image Kubespray uses.
4. Optional internal PyPI and Helm registries.

The upstream tip for `files_repo` is to preserve the original domain as the top-level directory (`github.com/`, `dl.k8s.io/`, `storage.googleapis.com/`, `get.helm.sh/`). Do that — it makes the mapping mechanical and reviewable.

### Inventory variables (official names)

```yaml
# group_vars/all/offline.yml
# Registry overrides
kube_image_repo: "{{ registry_host }}"
gcr_image_repo: "{{ registry_host }}"
docker_image_repo: "{{ registry_host }}"
quay_image_repo: "{{ registry_host }}"
github_image_repo: "{{ registry_host }}"
github_url: "{{ files_repo }}/github.com"
dl_k8s_io_url: "{{ files_repo }}/dl.k8s.io"
storage_googleapis_url: "{{ files_repo }}/storage.googleapis.com"
get_helm_url: "{{ files_repo }}/get.helm.sh"
local_path_provisioner_helper_image_repo: "{{ registry_host }}/busybox"

# containerd 2+ registry mirrors
containerd_registries_mirrors:
  - prefix: docker.io
    mirrors:
      - host: https://registry-1.docker.io
        capabilities: ["pull", "resolve"]
        skip_verify: false
  - prefix: "{{ registry_addr }}"
    mirrors:
      - host: "https://{{ registry_addr }}"
        capabilities: ["pull", "resolve"]
        skip_verify: false
        header:
          Authorization: "Basic {{ (registry_user + ':' + registry_pass) | b64encode }}"

# Cilium: mirror the chart index and the chart tarball into files_repo
cilium_install_extra_flags: "--repository {{ files_repo }}/helm.cilium.io/"
cilium_extra_values:
  image:
    useDigest: false
  hubble:
    relay:
      image:
        useDigest: false
    ui:
      backend:
        image:
          useDigest: false
      frontend:
        image:
          useDigest: false
  operator:
    image:
      override: "{{ registry_host }}/cilium/operator-generic:v<VERSION>"
      useDigest: false
      extension: ""
  certgen:
    image:
      useDigest: false
  envoy:
    image:
      useDigest: false
```

Required variable definitions, from the upstream guide:

| Variable | Meaning |
|---|---|
| `registry_host` | Container image registry. If the internal registry uses the same repository paths as upstream, no per-image overrides are needed |
| `registry_addr` | Registry as `[domain or ip]:[port]` only |
| `files_repo` | HTTP server or reverse proxy serving the static file tree. Include the version in the path so an upgrade does not change the URL |
| `yum_repo` / `debian_repo` / `ubuntu_repo` | Internal OS package repository for the matching OS |
| `registry_user` / `registry_pass` | Registry credentials, stored with `!vault` |

Keeping the same repository paths in the internal registry is the single biggest simplification: it means the `*_image_repo` overrides above are the only change and the image list does not have to be rewritten.

### containerd registry auth — version matters

Kubespray `release-2.32` documents two different mechanisms, because containerd changed its registry configuration:

```yaml
# containerd 2+ -> hosts.toml style mirrors
containerd_registries_mirrors:
  - prefix: "{{ registry_addr }}"
    mirrors:
      - host: "https://{{ registry_addr }}"
        capabilities: ["pull", "resolve"]
        header:
          Authorization: "Basic {{ (registry_user + ':' + registry_pass) | b64encode }}"

# containerd 1.7 -> legacy auth list
containerd_registry_auth:
  - registry: "{{ registry_host }}"
    username: "{{ registry_user }}"
    password: "{{ registry_pass }}"
```

This platform pins containerd 2.3.7 (the version Kubespray `release-2.32` ships), so the `containerd_registries_mirrors` form is the correct one.

### Generating the artifact list

The upstream guide provides `contrib/offline/generate_list.sh`, which reads `roles/kubespray_defaults/defaults/main/download.yml` and produces the file and image list templates, then expands them with Ansible.

```bash
# In a connected environment, with the pinned Kubespray checkout
cd contrib/offline
./generate_list.sh
```

It emits:
- `temp/files.list.template` — the static files (binaries, zips) to mirror.
- `temp/images.list.template` — every container image, with the `kube-apiserver`, `kube-controller-manager`, `kube-scheduler`, and `kube-proxy` images added separately because kubeadm pulls those and they are not in `download.yml`.

The same guide also offers a Kubespray container image (`quay.io/kubespray/kubespray`) with all Python dependencies baked in — mirror that image and run the playbooks inside it. It removes the Python dependency-closure problem from the offline environment entirely.

### OS package repositories

```yaml
# Oracle Linux / RHEL family
containerd_rh_repo_base_url: "{{ yum_repo }}/containerd"
containerd_rh_repo_gpgkey: "{{ yum_repo }}/containerd/gpg"

# Ubuntu
containerd_ubuntu_repo_base_url: "{{ ubuntu_repo }}/containerd"
containerd_ubuntu_repo_gpgkey: "{{ ubuntu_repo }}/containerd/gpg"
containerd_ubuntu_repo_repokey: 'YOURREPOKEY'
```

The upstream guide notes that only the container runtime packages come from these repositories; other packages come from the base OS repositories, which must also be mirrored.

### Alternative and less preferred

A Kubespray image-repository override that rewrites every image path to a differently-named internal path also works, but it requires the exact variable names in the pinned release and a rewritten image list. Use it only when the internal registry cannot mirror the upstream repository paths.

## G. Deployment

Execution context: **Automation Management Server** (or a bastion with the Ansible venv).

```bash
# 1. Pre-check
ansible -i inventory/<cluster>/hosts.ini all -m ping
ansible-playbook -i inventory/<cluster>/hosts.ini cluster.yml --syntax-check
ansible-playbook -i inventory/<cluster>/hosts.ini cluster.yml -b --check --diff --limit control-plane

# 2. Deploy
ansible-playbook -i inventory/<cluster>/hosts.ini cluster.yml -b

# 3. Post-check
kubectl get nodes -o wide
kubectl get pods -A
```

## H. Idempotency and reruns

Kubespray is idempotent by design. Reruns are safe and are the normal way to apply a corrected variable. A rerun after a failed deploy is the recommended recovery step, not a fresh install.

Rules:
- Never delete `/etc/kubernetes` to "start clean" on a node that holds state. Use `kubespray reset` (see below) as the intended teardown.
- Keep the inventory and group vars in Git so a rerun is reproducible from the recorded state.

## I. Node lifecycle

| Task | Procedure |
|---|---|
| Add worker | Add to `k8s-node` in hosts.ini, run `cluster.yml --limit <host>` |
| Add control-plane | Add to `control-plane` and `etcd`, run `cluster.yml --limit <host>` |
| Remove worker | `kubectl drain <node> --ignore-daemonsets --delete-emptydir-data`, remove from inventory, `cluster.yml --limit <host>` |
| Replace worker | Drain + remove + rebuild the host via Ansible + re-add |
| Remove control-plane | Requires care: etcd membership must be removed first, then the host |
| Reset a node | `ansible-playbook ... reset.yml --limit <host>` (Kubespray-provided), then rebuild |

## J. Upgrades

Upgrades are managed by Kubespray: set the new `kube_version` in group vars and re-run `cluster.yml`. The upgrade is sequential (one node at a time) and control-plane nodes are upgraded first.

Constraints:
- Kubernetes supports only one minor version skew in each direction. Do not skip minors.
- The kubeadm version must be compatible with the target Kubernetes version.
- etcd is upgraded as part of the node upgrade.
- CNI and CSI may need separate upgrades. Plan them explicitly.
- Rollback of a Kubernetes minor version is not supported. Take a snapshot before starting.

Full procedure with the upgrade-order checklist: `lifecycle/upgrades/kubernetes.md`.

## K. Validation

```bash
kubectl get nodes -o wide
kubectl get --raw='/readyz?verbose'
kubectl -n kube-system get pods
etcdctl --endpoints=https://127.0.0.1:2379 endpoint health --cluster \
  --cacert=/etc/kubernetes/pki/etcd/ca.crt \
  --cert=/etc/kubernetes/pki/etcd/healthcheck-client.crt \
  --key=/etc/kubernetes/pki/etcd/healthcheck-client.key
```

## L. Best practices

Mandatory:
- Pin the Kubespray release in `kubespray/VERSION`; never track `master`.
- Keep the inventory and group vars in Git; the cluster must be reproducible from the repo.
- Mirror every image the deploy uses, verified by a pull test in the offline environment.
- Keep `kubespray reset` available as the documented node teardown path.
- Run `--check --diff` on the control-plane before any real run.

Strongly recommended:
- Keep a `patches/` directory for site-specific overrides so they are visible in review.
- Run the deploy from the Automation Management Server, never from a laptop that also runs a browser.
- Record the Ansible and Python versions in `requirements.txt` and pin them.
