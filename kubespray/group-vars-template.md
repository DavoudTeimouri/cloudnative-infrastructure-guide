# Core group vars — reference template

Copy to `kubespray/inventory/<cluster>/group_vars/`. Every value must be verified against the pinned Kubespray release before use; the variable names change between releases.

## group_vars/k8s_cluster/k8s-cluster.yml

```yaml
# Kubernetes version. Must be inside the pinned Kubespray release's supported
# range (floor v1.34.0 for release-2.32).
kube_version: v1.36.5

# CNI. The release ships cilium 1.20.3.
kube_network_plugin: cilium

# Disable kube-proxy; Cilium replaces it. Requires k8sServiceHost/Port below.
kube_proxy_mode: ""

# Pod and service CIDRs. One pair per cluster.
kube_pods_subnet: "10.30.0.0/16"
kube_service_addresses: "10.32.0.0/16"

# Cilium needs the API endpoint when kube-proxy is absent.
k8sServiceHost: "10.20.0.100"      # the control-plane VIP
k8sServicePort: 6443

enable_coredns: true
```

## group_vars/all/main.yml

```yaml
container_manager: containerd
containerd_version: "2.3.7"        # the version release-2.32 ships

# Cert-manager and Argo CD are installed by Argo CD, not by Kubespray.
cert_manager: false

# Node labels applied by Kubespray, if any.
kube_node_labels: {}
```

## group_vars/all/offline.yml

```yaml
# Internal registry and file mirror. See the Kubespray release-2.32 offline guide.
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

# containerd 2+ mirrors
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

# Cilium chart served from the internal file mirror
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
      override: "{{ registry_host }}/cilium/operator-generic:v1.20.3"
      useDigest: false
      extension: ""
  certgen:
    image:
      useDigest: false
  envoy:
    image:
      useDigest: false

# OS package repositories (Oracle Linux / RHEL family)
containerd_rh_repo_base_url: "{{ yum_repo }}/containerd"
containerd_rh_repo_gpgkey: "{{ yum_repo }}/containerd/gpg"

# OS package repositories (Ubuntu)
containerd_ubuntu_repo_base_url: "{{ ubuntu_repo }}/containerd"
containerd_ubuntu_repo_gpgkey: "{{ ubuntu_repo }}/containerd/gpg"
containerd_ubuntu_repo_repokey: 'YOURREPOKEY'
```

## site variables (not in this file)

`registry_host`, `registry_addr`, `registry_user`, `registry_pass`, `files_repo`, `yum_repo`, `ubuntu_repo` come from the environment overlay (`site-<env>`) or from Ansible Vault. They are never committed.

## Verify before use

```bash
# Confirm the variable names exist in the pinned release
grep -rn "kube_proxy_mode\|k8sServiceHost" roles/kubespray_defaults/defaults/main/ | head
grep -rn "containerd_registries_mirrors" roles/ | head
```
