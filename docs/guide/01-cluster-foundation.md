# Phase 1 — Cluster Foundation

## Kubernetes HA with Kubespray

### Prerequisites
- 3+ control-plane nodes, 3+ worker nodes
- Ubuntu 22.04/24.04 or RHEL 9
- Python3 + pip on bootstrap host
- SSH key access to all nodes, passwordless sudo
- swap disabled on all nodes

### Bootstrap
Run `scripts/bootstrap-k8s.sh`. It installs Ansible, clones Kubespray, and prepares an inventory directory. Then edit the inventory and run `cluster.yml`.

### Inventory
Edit `inventory/<cluster>/hosts.ini`:

```ini
[control-plane]
k8s-master-1 ansible_host=10.0.0.1 ip=10.0.0.1
k8s-master-2 ansible_host=10.0.0.2 ip=10.0.0.2
k8s-master-3 ansible_host=10.0.0.3 ip=10.0.0.3

[etcd]
k8s-master-1
k8s-master-2
k8s-master-3

[k8s-node]
k8s-worker-1 ansible_host=10.0.0.11 ip=10.0.0.11
k8s-worker-2 ansible_host=10.0.0.12 ip=10.0.0.12

[k8s-cluster:children]
control-plane
k8s-node
```

### CNI
Kubespray defaults to Calico. Switch to Cilium in `inventory/<cluster>/group_vars/k8s_cluster/k8s-cluster.yml`:

```yaml
kube_network_plugin: cilium
```

### Run
```bash
ansible-playbook -i inventory/<cluster>/hosts.ini cluster.yml -b
```

### Validation
```bash
kubectl get nodes -o wide
./scripts/validate-cluster.sh
```

### Kubespray Version Notes
- **release-2.32** targets Kubernetes v1.36.5 but verified compatible with v1.36.4
- Pin to the highest patched sub-version within the declared K8s major.minor range
- Always run `scripts/validate-kubespray-compatibility.sh <release> <k8s-version>` before production deployment