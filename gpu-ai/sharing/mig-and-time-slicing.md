# MIG and GPU sharing

**Check date: 2026-10-17.** Profile data from the NVIDIA Multi-Instance GPU User Guide (`https://docs.nvidia.com/datacenter/tesla/mig-user-guide/latest/supported-mig-profiles.html`).

## The three sharing mechanisms are not equivalent

| Property | MPS | Time-slicing | MIG |
|---|---|---|---|
| Partition type | Logical | Logical | Physical |
| Max partitions | 48 | Unlimited | 7 |
| Performance isolation | No | No | Yes, by percentage (not partitioning) |
| Memory protection | No | No | Yes |
| Memory bandwidth QoS | No | No | Yes |
| Error isolation | No | No | Yes |
| Cross-partition interop | Always (IPC) | IPC | Limited IPC |
| Reconfigure | Dynamic | On process launch | When the GPU is idle |

The load-bearing line: **time-slicing provides no memory protection and no memory bandwidth QoS**. One tenant's memory pressure can OOM another tenant's process inside the same GPU, and a tenant saturating the memory bandwidth degrades the other tenant. MPS is worse in one respect: it is a single process address space, so a fault in one tenant can affect the others.

MIG is the only mechanism that delivers hardware-level memory isolation. That is why it is the production choice in this platform (ADR-0022).

## Supported GPUs

From the NVIDIA MIG User Guide supported-GPUs table:

| Product | Architecture | Compute capability | Memory | Max instances |
|---|---|---|---|---|
| H100-SXM5 | Hopper | 9.0 | 80 GB | 7 |
| H100-PCIE | Hopper | 9.0 | 80 GB | 7 |
| H100-SXM5 | Hopper | 9.0 | 94 GB | 7 |
| H100-PCIE | Hopper | 9.0 | 94 GB | 7 |
| H100 on GH200 | Hopper | 9.0 | 96 GB | 7 |
| H200-SXM5 | Hopper | 9.0 | 141 GB | 7 |
| H200 NVL | Hopper | 9.0 | 141 GB | 7 |
| A100-SXM4 | Ampere | 8.0 | 40 GB / 80 GB | 7 |
| A100-PCIE | Ampere | 8.0 | 40 GB / 80 GB | 7 |
| A30 | Ampere | 8.0 | 24 GB | 4 |
| B200 | Blackwell | 10.0 | 180 GB | 7 |
| GB200 | Blackwell | 10.0 | 186 GB | 7 |

MIG starts at the Ampere generation (compute capability 8.0+). Consumer GPUs do not support MIG.

## H100 profiles

H100 80GB (PCIe and SXM5):

| Profile | Memory fraction | SM fraction | L2 | Copy engines | Instances |
|---|---|---|---|---|---|
| 1g.10gb | 1/8 | 1/7 | 1/8 | 1 | 7 |
| 1g.10gb+me | 1/8 | 1/7 | 1/8 | 1 | 1 (media extensions) |
| 1g.20gb | 1/4 | 1/7 | 1/8 | 1 | 4 |
| 2g.20gb | 2/8 | 2/7 | 2/8 | 2 | 3 |
| 3g.40gb | 4/8 | 3/7 | 4/8 | 3 | 2 |
| 4g.40gb | 4/8 | 4/7 | 4/8 | 4 | 1 |
| 7g.80gb | Full | 7/7 | Full | 8 | 1 |

H100 94GB:

| Profile | Memory fraction | SM fraction | Instances |
|---|---|---|---|
| 1g.12gb | 1/8 | 1/7 | 7 |
| 1g.12gb+me | 1/8 | 1/7 | 1 |
| 1g.24gb | 1/4 | 1/7 | 4 |
| 2g.24gb | 2/8 | 2/7 | 3 |
| 3g.47gb | 4/8 | 3/7 | 2 |
| 4g.47gb | 4/8 | 4/7 | 1 |
| 7g.94gb | Full | 7/7 | 1 |

H100 96GB (GH200): 1g.12gb (7), 1g.12gb+me (1), 1g.24gb (4), 2g.24gb (3), 3g.48gb (2), 4g.48gb (1), 7g.96gb (1).

## H200 profiles

H200 141GB:

| Profile | Memory fraction | SM fraction | Hardware units | Instances |
|---|---|---|---|---|
| 1g.18gb | 1/8 | 1/7 | 1 NVDEC, 1 JPEG, 0 OFA | 7 |
| 1g.18gb+me | 1/8 | 1/7 | 1 NVDEC, 1 JPEG, 1 OFA | 1 |
| 1g.35gb | 1/4 | 1/7 | 1 NVDEC, 1 JPEG, 0 OFA | 4 |
| 2g.35gb | 2/8 | 2/7 | 2 NVDEC, 2 JPEG, 0 OFA | 3 |
| 3g.71gb | 4/8 | 3/7 | 3 NVDEC, 3 JPEG, 0 OFA | 2 |
| 4g.71gb | 4/8 | 4/7 | 4 NVDEC, 4 JPEG, 0 OFA | 1 |
| 7g.141gb | Full | 7/7 | 7 NVDEC, 7 JPEG, 1 OFA | 1 |

## What MIG does and does not give

Gives:
- Hard memory isolation: an instance cannot address memory outside its slice.
- Memory bandwidth QoS: each slice has its own memory controllers and DRAM paths.
- Fault isolation: a hang in one instance does not take down the others.
- A schedulable resource per instance, published by the device plugin.

Does not give:
- Shared VRAM between instances. Two MIG instances cannot be combined into one larger device.
- More total memory than the physical GPU.
- Zero reconfiguration cost. Reconfiguration requires the GPU to be idle.

## Multi-GPU is not unified memory

Multiple physical GPUs on a node are separate devices. They are connected by NVLink or PCIe, and used in one of two ways:

- **Model parallelism** — one model sharded across the GPUs (vLLM `--tensor-parallel-size N`). Requires N GPUs in one pod, on one node, with the GPUs NVLink-connected for acceptable performance.
- **Independent replicas** — each GPU runs its own copy of the model. This is `replicas: N` with `--tensor-parallel-size 1`.

There is no configuration where two H100s behave as one 160 GB device. Total aggregate VRAM is available to a sharded model, but the model is split layer by layer and the engines communicate over NVLink; VRAM is not pooled.

## Kubernetes resource names

The device plugin publishes one resource per MIG profile. The exact names are published per node and must be read from the live node, not assumed:

```bash
kubectl describe node <gpu-node> | sed -n '/Allocatable/,/^Events/p'
```

Typical shape: `nvidia.com/mig-1g.10gb`, `nvidia.com/mig-2g.20gb`, `nvidia.com/mig-3g.40gb`, `nvidia.com/mig-4g.40gb`, `nvidia.com/mig-7g.80gb` for H100 80GB. The `+me` (media extension) profiles are published separately, for example `nvidia.com/mig-1g.10gb+me`.

Requesting the plain `nvidia.com/gpu` resource on a MIG-configured node will not schedule: on a MIG-mode GPU the device plugin no longer advertises a whole-GPU resource. This is a common and confusing failure.

## MIG configuration procedure

```bash
# On the node (GPU must be idle)
nvidia-smi -q | grep -i "MIG Mode"
# Current: Disabled -> enable
sudo nvidia-mig-mode -m 1

# Apply a profile
sudo nvidia-mig-parted -i 0 -m 1g.10gb

# Verify
nvidia-smi -L
nvidia-smi mig -lgip
```

The GPU Operator manages MIG configuration declaratively:

```yaml
# gpu-operator values
mig:
  enabled: true
  strategy: mixed
  # or a single profile for all GPUs
```

`strategy: mixed` lets the device plugin expose multiple profile sizes on the same GPU, which is more flexible but makes the node's advertised resource set harder to reason about. `single` gives one profile size per GPU, which is simpler to schedule against. For production multi-tenancy, one profile size per GPU is easier to operate.

## Reconfiguration

MIG reconfiguration requires the GPU to be idle — no processes, no clients. In Kubernetes that means draining the node and evicting every GPU pod:

```bash
kubectl drain <gpu-node> --ignore-daemonsets --delete-emptydir-data
# reconfigure
kubectl uncordon <gpu-node>
```

An in-place reconfiguration of a live profile (for example 1g.20gb to 1g.10gb) also requires the GPU to be idle.

## Scheduling with MIG

```yaml
resources:
  limits:
    nvidia.com/mig-1g.10gb: 1
```

Combined with a per-tenant namespace quota:

```yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: gpu-quota
  namespace: team-a
spec:
  hard:
    requests.nvidia.com/mig-1g.10gb: "4"
    limits.nvidia.com/mig-1g.10gb: "4"
```

## Validation

```bash
# The node advertises the MIG resources
kubectl get node <gpu-node> -o jsonpath='{.status.allocatable}' | tr ',' '\n' | grep nvidia

# A pod gets exactly its slice
kubectl run migtest --rm -it --restart=Never \
  --image=harbor.internal/platform/cuda:<version> \
  --overrides='{"spec":{"nodeSelector":{"node-role.kubernetes.io/gpu":"true"},"containers":[{"name":"migtest","image":"harbor.internal/platform/cuda:<version>","command":["nvidia-smi","-L"],"resources":{"limits":{"nvidia.com/mig-1g.10gb":1}}}]}}' \
  -- nvidia-smi -L
```

Hard-isolation test (mandatory acceptance test G-02): in a `1g.10gb` instance, allocate more than 10 GB. The allocation must fail with an out-of-memory error, and the co-tenant instance must remain unaffected and continue serving.
