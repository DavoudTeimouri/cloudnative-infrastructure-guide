# 05. Kubernetes

**Purpose:** Deploy application Kubernetes clusters with Kubespray — control plane, workers, CNI
(Cilium), CoreDNS, MetalLB — in the air-gapped site using images from the internal registry.

## Prerequisites
- Step 04 complete: Ceph healthy with `kube-rbd` pool (for Rook CSI) or `ceph-csi` installed later.
- Step 03 complete: container engine running on every future K8s node.
- Kubespray versions pinned in `compatibility/version-matrix.md` (≥ 5 releases in parallel).

## Steps

### 05.1 Choose deployment model
- **Kubespray** — Ansible-based, from-scratch control plane + worker nodes (this guide).
- **RKE2** — alternative for air-gapped bare metal; not covered here.

Source: `kubespray/kubespray-deployment.md`

### 05.2 Bootstrap from the operation server
On the automation host:

```bash
git clone https://github.com/kubernetes-sigs/kubespray.git
cd kubespray
pip3 install -r requirements.txt   # from internal PyPI mirror
cp -rfp inventory/sample inventory/my-cluster
```

Edit `inventory/my-cluster/hosts.yaml` with your node IPs and roles. Keep role labels consistent with
step 01/02.

### 05.3 Pin air-gap image registry
Override every Kubespray image to pull from `harbor.internal` (your internal registry), not Docker Hub:

```yaml
# group_vars/k8s_cluster/k8s-cluster.yml (example)
kube_image_repo: harbor.internal/k8s
container_manager: containerd
containerd_registries:
  - registry: harbor.internal
    server: harbor.internal
```

Source: `kubespray/kubespray-deployment.md` (§air-gap)

### 05.4 Deploy the control plane
```bash
ansible-playbook -i inventory/my-cluster/hosts.yaml cluster.yml -b
```
Expected: `PLAY RECAP` green on all control-plane and worker nodes; `kube-apiserver` listening on
6443.

### 05.5 Verify control plane health
```bash
kubectl get nodes
kubectl get componentstatuses
kubectl cluster-info
```

### 05.6 CNI — Cilium
Install Cilium with eBPF. Confirm L3/L4 policy mode and that pods can reach each other across nodes.

Source: `kubernetes/networking/cilium.md`

### 05.7 CoreDNS forwarding
Configure upstream forwarding to your internal DNS (step 01.5) so internal hostnames resolve from
inside the cluster.

Source: `kubernetes/networking/coredns-forwarding.md`

### 05.8 Load balancer — MetalLB
Configure MetalLB with a Layer 2 address pool from the `nodeport` segment for `LoadBalancer` Services,
and as a fallback for external access when the edge LB is not yet in place.

Source: `kubernetes/networking/metallb.md`

## Validation
- [ ] `kubectl get nodes` shows all nodes `Ready`.
- [ ] `kubectl get componentstatuses` healthy (or check via metrics-server).
- [ ] Pod-to-pod ping works across two nodes (Cilium).
- [ ] CoreDNS resolves `kubernetes.default.svc` and an internal hostname.
- [ ] MetalLB `AddressPool` exists with a valid CIDR range.
- [ ] All container images pulled from `harbor.internal`.

## Navigation
**[← Prev · 04. Storage — Ceph](./04-storage-ceph.md)** | **[Next → 06. Management cluster](./06-management-cluster.md)**
