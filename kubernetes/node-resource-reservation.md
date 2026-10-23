# Node resource reservation

A Kubernetes node is not only for pods. The kubelet, the container runtime, the CNI agent, the CSI
node plugin, the log shipper and the monitoring agent all run on the same CPU and memory. If none
of it is reserved, a busy workload can evict the kubelet's own dependencies and take the node down
with it.

Reservation has three parts:

| Part | Flag | What it protects |
|---|---|---|
| System reserved | `--system-reserved` | OS daemons, udev, sshd, the container runtime |
| Kube reserved | `--kube-reserved` | kubelet, CNI, CSI node plugin, device plugins |
| Eviction thresholds | `--eviction-hard` | The point where the kubelet starts killing pods instead of the node |

## Values the configurator sets

| Value | Default | Meaning |
|---|---|---|
| `reservedSystemCpu` | `500m` | CPU kept for the OS and its daemons |
| `reservedSystemMem` | `1Gi` | RAM kept for the OS and its daemons |
| `reservedKubeCpu` | `500m` | CPU kept for kubelet, CNI, CSI node plugin |
| `reservedKubeMem` | `1Gi` | RAM kept for kubelet, CNI, CSI node plugin |
| `evictionHardMem` | `100Mi` | Free memory below which the kubelet evicts pods |
| `evictionHardNodefs` | `10%` | Free node filesystem below which pods are evicted |

Sizing rule: reserve 10% of CPU and 15% of RAM on a worker; on a control-plane node reserve 1 vCPU
and 2 GiB. The numbers above are a floor for an 8 vCPU / 32 GiB node, not a universal answer.

## How it reaches the node

Kubespray writes kubelet flags from `kubelet_custom_flags`. The generated `k8s-cluster.yml` carries:

```yaml
kubelet_custom_flags:
  - "--system-reserved=cpu={{value.reservedSystemCpu}},memory={{value.reservedSystemMem}}"
  - "--kube-reserved=cpu={{value.reservedKubeCpu}},memory={{value.reservedKubeMem}}"
  - "--eviction-hard=memory.available<{{value.evictionHardMem}},nodefs.available<{{value.evictionHardNodefs}}"
```

Verify on the node, not in the playbook output:

```bash
kubectl get --raw "/api/v1/nodes/<node>/proxy/configz" | python3 -m json.tool | grep -A5 -i reserved
kubectl describe node <node> | grep -A6 "Allocated resources"
```

`Allocatable` must be lower than `Capacity`. If the two are equal, the reservation did not apply and
the kubelet silently kept its defaults.

## What not to do

- Do not reserve more than 20% of a node. The scheduler then reports capacity the cluster does not
  have and pods stay Pending while the node looks empty.
- Do not set `--kube-reserved` without a matching `--kube-reserved-cgroup` unless the cgroup exists;
  the kubelet logs a warning and continues without enforcing it.
- Do not rely on eviction thresholds instead of requests and limits. Eviction is the last resort,
  not the capacity plan.

## GPU nodes

A GPU node carries the device plugin, the driver container and the DCGM exporter. Reserve one extra
CPU and 2 GiB on top of the numbers above; `nvidia.com/gpu` is not compressible and cannot be
overcommitted, so CPU pressure is what actually breaks a GPU node.
