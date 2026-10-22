# GPU worker operations

## A. Purpose and scope

Dedicated NVIDIA GPU worker nodes for AI training and LLM inference: hardware preparation, driver installation, GPU Operator, scheduling, and day-2 operations.

## B. Hardware baseline

| Component | Requirement (H100 SXM) | Requirement (H200 SXM) |
|---|---|---|
| CPU | 2x 24+ core, AVX-512 | 2x 24+ core, AVX-512 |
| RAM | 256 GB+ | 512 GB+ |
| Boot disk | 2x 960 GB SSD (RAID1) | 2x 960 GB SSD (RAID1) |
| Data disk | 2x 3.84 TB NVMe (model cache + runtime) | 2x 3.84 TB NVMe |
| GPU | 4-8x H100 80GB SXM | 4-8x H200 141GB SXM |
| Interconnect | NVSwitch intra-node, 8x 400Gb/s IB or 8x 200Gb/s RoCE inter-node | Same |
| NIC | 2x 100 GbE | 2x 100 GbE |
| Power | 2x 3.0 kW+ per node, PDU A/B | Higher per GPU |
| Cooling | Direct liquid cooling for high-density SXM | Same |

BIOS settings that matter:
- Above 4G decoding: enabled
- IOMMU: enabled (needed for passthrough or isolation)
- NUMA: one NUMA node per GPU (for H100/H200 SXM systems, 1 GPU per NUMA node is the vendor layout)
- ACS enabled, if available, for IOMMU grouping
- Resizable BAR: enabled
- SR-IOV/IOMMU: enabled if virtualizing

Physical: confirm the GPU topology with `nvidia-smi topo -m` before scheduling anything. It determines which GPUs are NVLink-connected and therefore which multi-GPU topologies are usable.

## C. OS preparation

The GPU nodes use the same OS baseline as every other node (`operating-systems/`), plus:

```bash
# NVIDIA driver prerequisites
dnf install kernel-devel-$(uname -r) kernel-headers-$(uname -r) gcc make pciutils
# or on Ubuntu
apt install -y linux-headers-$(uname -r) build-essential pciutils

# Verify the kernel version matches the modules
uname -r
ls /lib/modules/
```

The NVIDIA kernel module must be built against the running kernel. A kernel update without a matching module build means the GPU is invisible until the driver is rebuilt or a prebuilt kmod is installed for that kernel.

## D. Driver installation

Path A — the GPU Operator (recommended): the operator manages the driver, the container toolkit, the device plugin, DCGM, and the operator's own monitoring, and can upgrade them together.

Path B — manual driver install (for troubleshooting or a driver the operator does not ship):

```bash
# NVIDIA driver (data center, production branch)
dnf install -y nvidia-driver:<branch>   # Oracle Linux
# or
apt install -y nvidia-driver-<branch>   # Ubuntu

nvidia-modprobe -u -c=0
nvidia-smi
```

The exact package name and branch for the pinned version must come from the NVIDIA official download page — record the check in `gpu-ai/drivers/compatibility-matrix.md`.

## E. NVIDIA Container Toolkit

```bash
# Install the toolkit from the internal repository
dnf install -y nvidia-container-toolkit   # or apt

# Configure containerd to use the NVIDIA runtime
nvidia-ctk runtime configure --runtime=containerd --config=/etc/containerd/config.toml
systemctl restart containerd
```

Verify:

```bash
# Run a test container from the internal registry
ctr -n k8s.io run --rm --net-host \
  --with-nvidia-runtime \
  harbor.internal/platform/cuda:<version> \
  nvidia-smi
```

## F. GPU Operator

Installed by Argo CD into the `gpu-operator` namespace.

```yaml
# values.yaml (relevant)
driver:
  enabled: true
  version: "<pinned>"
  repository: harbor.internal/platform/nvidia
toolkit:
  enabled: true
  version: "<pinned>"
  repository: harbor.internal/platform/nvidia
devicePlugin:
  enabled: true
  version: "<pinned>"
  repository: harbor.internal/platform/nvidia
dcgmExporter:
  enabled: true
  version: "<pinned>"
  repository: harbor.internal/platform/nvidia
  serviceMonitor:
    enabled: true
operator:
  env:
    USE_GPU_OPERATOR: "true"
    CLUSTER_TYPE: "kubernetes"
  initContainer:
    image: harbor.internal/platform/nvidia/cuda
```

The operator needs privileged DaemonSets and host mounts. It must be excluded from Pod Security Standards enforcement and from restrictive admission policies.

The operator's node selector targets the GPU pool:

```yaml
nodeSelector:
  nvidia.com/gpu.present: "true"
```

## G. Node labelling and scheduling

The operator adds `nvidia.com/gpu.present=true` automatically. Ansible adds the pool labels and the taint:

```yaml
nodeLabels:
  node-role.kubernetes.io/gpu: "true"
  accelerator: nvidia
nodeTaints:
  - key: nvidia.com/gpu
    value: "true"
    effect: NoSchedule
```

A workload requests a GPU through the extended resource name, which the device plugin publishes. For exclusive allocation:

```yaml
resources:
  limits:
    nvidia.com/gpu: 1
```

For MIG, the published resource names are per MIG profile. Read them from the live node rather than assuming them:

```bash
kubectl describe node <gpu-node> | grep -A 40 "Allocatable"
```

## H. Validation

```bash
# Node is ready and advertises GPUs
kubectl get nodes -l node-role.kubernetes.io/gpu
kubectl describe node <gpu-node> | grep nvidia.com/gpu

# Device plugin is running
kubectl -n gpu-operator get pods | grep device-plugin

# A pod sees the GPU
kubectl run gputest --rm -it --image=harbor.internal/platform/cuda:<version> \
  --overrides='{"spec":{"nodeSelector":{"node-role.kubernetes.io/gpu":"true"},"containers":[{"name":"gputest","image":"harbor.internal/platform/cuda:<version>","command":["nvidia-smi"],"resources":{"limits":{"nvidia.com/gpu":1}}}]}}' -- nvidia-smi
```

## I. Day-2 operations

| Task | Procedure |
|---|---|
| Node drain for maintenance | `kubectl drain <node> --ignore-daemonsets --delete-emptydir-data` — this stops the GPU pods; the operator's daemonsets stay |
| Driver upgrade | The operator upgrades the driver in place. GPU pods restart; use a drain first. Plan a window |
| Kernel upgrade | Requires a matching driver module. Drain, upgrade, rebuild the module, verify `nvidia-smi` before uncordoning |
| Replace a failed GPU | Replace the physical card, drain, rebuild the node, re-apply the operator, verify `nvidia-smi` |
| MIG reconfigure | Drain the node, run `nvidia-mig-parted` or the MIG manager to reconfigure, verify the new resource names |
| Add GPUs to a node | Power down, install, drain, reboot, verify topology with `nvidia-smi topo -m` |

## J. Known traps

1. **Kernel mismatch after an OS upgrade** — the GPU disappears. Fix: rebuild the module or install the matching kmod before uncordoning the node.
2. **`nvidia.com/gpu` vs MIG resources** — a workload requesting `nvidia.com/gpu` on a MIG-configured node will not schedule. Request the specific MIG resource.
3. **Operator upgrade restarts GPU pods** — a driver upgrade is not zero-disruption. Use a drain plus a maintenance window.
4. **The container toolkit and the driver must match** — a toolkit upgrade alone can break container GPU access.
5. **MIG reconfiguration requires the GPU to be idle** — a running GPU pod blocks it.
6. **`nvidia-smi topo -m` shows PCIe-only for some GPU pairs** — those GPUs are not usable for efficient model parallelism.

## K. Best practices

Mandatory:
- GPU nodes in their own node pool with a taint, so general workloads cannot land there.
- Node drain before any driver, kernel, or card change.
- `nvidia-smi` verified after every driver or kernel change, before the node returns to service.
- The exact driver, toolkit, CUDA, and operator versions pinned in `gpu-ai/drivers/compatibility-matrix.md` and mirrored offline.

Strongly recommended:
- Model cache on local NVMe to avoid pulling weights on every pod start.
- Health check on every inference pod that reports model load time and GPU memory.
- Record the GPU topology in the asset register, not only in the node description.
- A rolling node upgrade procedure, one GPU node at a time, with inference capacity headroom for the loss of one node.
