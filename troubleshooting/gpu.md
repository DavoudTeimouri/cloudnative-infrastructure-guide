# GPU troubleshooting

## Symptoms

- The node is not labeled `nvidia.com/gpu.present=true`.
- A pod requesting `nvidia.com/gpu: 1` stays `Pending`.
- A pod starts but `nvidia-smi` inside it fails.
- The GPU Operator pods are crash-looping.
- A pod requests `nvidia.com/gpu` on a MIG-configured node and never schedules.
- Inference pods get OOM-killed.

## Likely causes

| Cause | Discriminator |
|---|---|
| The driver is not installed or was built for a different kernel | `nvidia-smi` on the host fails with "NVIDIA-SMI has failed because it couldn't communicate with the NVIDIA driver" |
| The kernel was upgraded and the module is stale | `lsmod \| grep nvidia` shows nothing after a kernel change |
| The device plugin is not running | `kubectl -n gpu-operator get pods` |
| The container toolkit is not configured in containerd | `nvidia-ctk runtime configure` was not run, or containerd was not restarted |
| The pod requests the wrong resource name on a MIG GPU | `kubectl describe node` shows MIG resources, not `nvidia.com/gpu` |
| The pod has no toleration for the GPU taint | The node has `nvidia.com/gpu:NoSchedule` |
| The pod does not request the GPU resource | The container has no `nvidia.com/gpu` limit |
| VRAM exhaustion in the inference engine | The vLLM log reports KV cache allocation failure |

## Diagnostic commands

```bash
# Host state
nvidia-smi
nvidia-smi -L
nvidia-smi -q | grep -i "driver version\|mig mode"
lsmod | grep nvidia
uname -r
ls /lib/modules/
dmesg | grep -i nvidia | tail -20

# Operator state
kubectl -n gpu-operator get pods -o wide
kubectl -n gpu-operator logs -l app=nvidia-driver-daemonset --tail=100
kubectl -n gpu-operator logs -l app=nvidia-device-plugin-daemonset --tail=100
kubectl -n gpu-operator logs deploy/nvidia-operator --tail=100

# Node labels and resources
kubectl get node <gpu-node> -o jsonpath='{.metadata.labels}' | tr ',' '\n' | grep nvidia
kubectl describe node <gpu-node> | sed -n '/Allocatable/,/^Events/p'
kubectl describe node <gpu-node> | grep -i taint

# Pod scheduling
kubectl describe pod <pod> -n <ns> | grep -A10 Events

# Container runtime configuration
grep -A5 "runtimes" /etc/containerd/config.toml
cat /etc/containerd/certs.d/*/hosts.toml 2>/dev/null

# In-container check
kubectl exec -it <pod> -- nvidia-smi
kubectl exec -it <pod> -- ls -l /dev/nvidia*
```

## Expected healthy state

Host:

```
$ nvidia-smi
+-----------------------------------------------------------------------------+
| NVIDIA-SMI 595.71.05   Driver Version: 595.71.05   CUDA Version: 13.0     |
|   0  H100 80GB HBM3          On    |  00000000:17:00.0 Off |  0 Default |
+-----------------------------------------------------------------------------+
```

Node:

```
$ kubectl get node <gpu-node> -o jsonpath='{.status.allocatable}' | tr ',' '\n' | grep nvidia
"nvidia.com/gpu":"8"
```

Pod: `nvidia-smi` inside the container lists exactly the GPUs the pod requested.

## Remediation

### The driver is missing or stale after a kernel upgrade

```bash
# Rebuild the module against the current kernel
sudo dkms autoinstall
sudo modprobe nvidia
nvidia-smi
```

On a managed node, let the GPU Operator rebuild it: drain the node, delete the driver DaemonSet pod, and let the operator recreate it.

### The container toolkit is not configured

```bash
sudo nvidia-ctk runtime configure --runtime=containerd --config=/etc/containerd/config.toml
sudo systemctl restart containerd
```

Verify the runtime section of `/etc/containerd/config.toml` now contains the `nvidia` runtime.

### The pod cannot get a GPU

```bash
# Check the taint and the toleration
kubectl get node <gpu-node> -o jsonpath='{.spec.taints}'
```

A workload that needs a GPU must have both:

```yaml
tolerations:
  - key: nvidia.com/gpu
    operator: Equal
    value: "true"
    effect: NoSchedule
containers:
  - name: app
    resources:
      limits:
        nvidia.com/gpu: 1
```

Both are required. A toleration without the resource limit schedules on a GPU node but gets no GPU.

### MIG resource mismatch

```bash
kubectl describe node <gpu-node> | sed -n '/Allocatable/,/^Events/p'
```

If the node advertises `nvidia.com/mig-1g.10gb` and not `nvidia.com/gpu`, the request must use the MIG resource name. On a MIG-mode GPU the device plugin does not advertise a whole-GPU resource.

### GPU pod OOM-killed

This is usually the vLLM engine exceeding VRAM, not the pod's memory limit.

```bash
kubectl describe pod <pod> -n <ns> | grep -i "reason\|message"
kubectl logs <pod> -c vllm --previous | tail -50
```

Fixes, in order of effect:
- Lower `--gpu-memory-utilization`.
- Lower `--max-model-len` (the KV cache scales with it).
- Quantize the model.
- Use more GPUs with `--tensor-parallel-size`.
- Raise the pod's memory limit if the container OOM (not the GPU) was the limit.

A pod OOM with `Reason: OOMKilled` and a low memory limit is a container memory issue; a vLLM error about "No available memory for the cache blocks" is a VRAM issue. They look similar in `kubectl describe` but are fixed differently.

## Risks

- Rebuilding the driver module on a node with running GPU pods interrupts them.
- Changing the MIG profile requires the GPU to be idle, which means draining the node.
- `nvidia-smi --gpu-reset` on a GPU with active compute processes fails and, in some configurations, requires the host to be rebooted.
- A kernel upgrade on a GPU node without a matching driver build makes the GPU invisible. Always verify `nvidia-smi` before uncordoning.

## Verification after remediation

```bash
nvidia-smi
kubectl run gputest --rm -it --restart=Never \
  --image=harbor.internal/platform/cuda:<version> \
  --overrides='{"spec":{"nodeSelector":{"node-role.kubernetes.io/gpu":"true"},"containers":[{"name":"gputest","image":"harbor.internal/platform/cuda:<version>","command":["nvidia-smi"],"resources":{"limits":{"nvidia.com/gpu":1}}}]}}' \
  -- nvidia-smi
```

Then re-run acceptance test G-01 (GPU scheduling).
