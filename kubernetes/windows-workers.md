# Windows worker nodes

Kubespray can join Windows Server nodes to a Linux control plane. The support is real but narrower
than Linux: the CNI, the storage and the workload model all change.

## What works, what does not

| Capability | Windows worker | Note |
|---|---|---|
| Calico CNI | Yes | The supported path. BGP or VXLAN, Windows nodes in their own block |
| Cilium CNI | Partial | Requires Cilium with the Windows daemon set and strict tunnel mode; not the default here |
| HostProcess containers | Yes | The Windows equivalent of a privileged pod |
| CSI: Ceph RBD | No | RBD maps a Linux kernel device; Windows has no ceph-csi node plugin |
| CSI: SMB / Azure Files | Yes | Only if the storage backend provides an SMB CSI driver |
| GPU (DirectX / CUDA) | Yes, separately | Needs the NVIDIA Windows driver and the Windows GPU device plugin |
| Linux-only workloads | No | A Deployment with a Linux image will not schedule on Windows |

Consequence for this platform: a Windows node pool is for .NET Framework, IIS and Windows
containers. Stateful workloads that need Ceph stay on Linux.

## Enabling it in the configurator

The **Application cluster** page has a Windows node group: count, vCPU, RAM, disk. When the count is
above zero:

- the inventory gains a `[windows]` group and adds it to `[k8s-cluster:children]`;
- the sizing table gains a Windows row;
- the generated `windows-vars.yaml` sets the Kubernetes version, the CNI and the container runtime
  for the group;
- the runbook adds the Windows prerequisites step.

Calico is required when Windows nodes exist. If Cilium is selected, the runbook warns and the
generated vars keep `kube_network_plugin: calico` for the Windows group — a mixed CNI cluster is not
a supported configuration.

## Prerequisites on each Windows node

1. Windows Server 2022 (or 2019 with the current cumulative update).
2. The `Containers` feature and the container runtime (containerd 1.7+ or the Mirantis runtime that
   matches the Kubespray release).
3. WinRM over HTTPS, or SSH, reachable from the Ansible host.
4. The node in the same L2/L3 path as the Linux nodes for the CNI overlay; no NAT between them.
5. The internal registry reachable and the CA installed in the Windows certificate store.
6. `nssm` or a native service wrapper so the kubelet and kube-proxy survive a reboot.

Kubespray's Windows playbook expects `ansible_connection: winrm`, `ansible_winrm_transport: ntlm` (or
`certificate`), and an account in the local Administrators group.

## Version alignment

The Windows node must run the same Kubernetes minor version as the control plane. Kubespray installs
`kubernetesVersion` from the release it is pinned to; do not let a Windows node lag a minor behind.
The generated `windows-vars.yaml` pins `kube_version` so a mixed cluster cannot drift.
