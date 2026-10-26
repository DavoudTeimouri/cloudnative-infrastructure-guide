# GPU scheduling

GPU nodes are dedicated, tainted, and labelled so that only GPU workloads land on
them. The NVIDIA GPU Operator installs the driver, container toolkit, device
plugin, and DCGM exporter; scheduling then depends on the resource the device
plugin advertises.

Design context: `gpu-ai/gpu-ai-architecture.md` §9.4.

## Node preparation

Applied by Ansible to every GPU node:

```yaml
nodeLabels:
  nvidia.com/gpu.present: "true"
  nvidia.com/gpu.deploy.k8s.io/operator: "true"
  nvidia.com/gpu.product: "H100-80GB-HBM3"   # exact value from `nvidia-smi -L` + operator discovery
nodeTaints:
  - key: nvidia.com/gpu
    value: "true"
    effect: NoSchedule
```

The product label must be read from the node, not assumed: the device plugin
publishes the model string it discovers.

## Workload request

```yaml
resources:
  limits:
    nvidia.com/gpu: 1
```

A pod that requests a GPU but tolerates no taint stays Pending. That is the
intended failure: it makes a missing toleration visible instead of silently
scheduling onto a GPU node.

## Isolation model

| Mechanism | Use |
|---|---|
| Namespace quota on `nvidia.com/gpu` | Caps each team's total devices |
| PriorityClass | Interactive inference above batch |
| Gang scheduling (Volcano or Kueue) | Multi-GPU jobs; without it, partial allocation can deadlock |
| MIG | Hardware partitioning on supported GPUs only; resource names come from the live node |
| Time-slicing | Oversubscription, **no VRAM isolation** — one tenant can OOM another |

MIG resource names are not portable across GPU models or profiles. Read them from
`kubectl describe node` and record them per cluster; do not copy a name from
another site.

## Versions

| Component | Pin | Source |
|---|---|---|
| NVIDIA GPU Operator | 26.7.2 | `compatibility/version-matrix.md` |
| DCGM Exporter | 4.8.4 | `compatibility/version-matrix.md` |

The GPU Operator version determines the driver and DCGM versions it deploys.
Changing it is a node-level change with a drain.

## Validation

```bash
kubectl get nodes -l nvidia.com/gpu.present=true
kubectl describe node <gpu-node> | grep -A5 "Allocatable"     # nvidia.com/gpu: N
kubectl get pods -n gpu-operator
kubectl run gpu-test --rm -it --restart=Never \
  --image=<internal-registry>/cuda-vectoradd --limits=nvidia.com/gpu=1
```

## Failure modes

| Failure | Effect | Recovery |
|---|---|---|
| Device plugin not running | Node advertises no GPU; GPU pods stay Pending | Restart the operator pod on that node; check the driver container logs |
| Driver mismatch after node upgrade | Device plugin crash-loops | Pin the driver to the operator release; re-run the GPU role |
| Taint removed by drift | Non-GPU pods consume GPU nodes | Re-apply labels and taints from the `gpu` Ansible role |
| MIG configuration changed | Advertised resource names change; existing requests no longer match | Drain, reconfigure, and update workload requests |

## Related

- Architecture and serving: `gpu-ai/gpu-ai-architecture.md`
- Monitoring: `gpu-ai/monitoring/index.md`
- Ports: `network-matrix/network-communication-matrix.md` row 45
- Backlog item: `requirements/component-guide-backlog.md` item 46
