# NVIDIA driver, CUDA and GPU Operator compatibility

**Check date: 2026-10-17.** Source: NVIDIA official documentation.

## Driver branch lifecycle

From `https://docs.nvidia.com/datacenter/tesla/drivers/latest/driver-lifecycle.html`:

| Branch type | Purpose | Cadence | Support length |
|---|---|---|---|
| New Feature Branch (NFB) | Early adopters, new CUDA APIs | ~quarterly | Not supported for production |
| Production Branch (PB) | Qualified for enterprise/data center GPUs | Twice a year | 1 year of bug and security updates |
| Long Term Support Branch (LTSB) | Production, longer cycle | At least once per hardware architecture | 3 years |

## CUDA toolkit vs driver branch matrix

From `https://docs.nvidia.com/datacenter/tesla/drivers/latest/supported-drivers-and-cuda-toolkit-versions.html`:

| Branch | Designation | EOL | Max CUDA major without forward-compat |
|---|---|---|---|
| R535 | LTSB | June 2026 | CUDA 12 |
| R580 | LTSB | June 2028 | CUDA 13 |
| R595 | Production Branch | March 2027 | CUDA 13 |
| R610 | New Feature Branch | August 2026 | CUDA 13 |

Note: R535 and R610 are at or past their EOL. For this platform the candidate branches are **R580 (LTSB, to June 2028)** and **R595 (Production, to March 2027)**.

Latest listed driver release: **595.71.05 (Linux) / 596.36 (Windows)**, released 2026-04-28, carrying CUDA Toolkit 13.x.
Source: `https://docs.nvidia.com/datacenter/tesla/tesla-release-notes-595-71-05/index.html`

## Architecture support

From `https://docs.nvidia.com/datacenter/tesla/drivers/cuda-toolkit-driver-and-architecture-matrix.html`:

| Architecture | Compute capability | First CUDA toolkit | Last driver support |
|---|---|---|---|
| Blackwell | 10.0 | CUDA 12.8 | Ongoing |
| Hopper (H100/H200) | 9.0 | CUDA 11.8 | Ongoing |
| Ada | 8.9 | CUDA 11.8 | Ongoing |
| Ampere (A100) | 8.0 / 8.6 | CUDA 11.0 | Ongoing |
| Turing | 7.5 | CUDA 10.0 | Ongoing |
| Volta | 7.0 | CUDA 9.0 | CUDA 12.x |
| Pascal | 6.0 / 6.1 | CUDA 8.0 | CUDA 12.x |

## Minimum driver for MIG

From the NVIDIA Multi-Instance GPU User Guide:

| GPU | CUDA version | Minimum driver |
|---|---|---|
| A100 / A30 | CUDA 11 | R525 (>= 525.53) or later |
| H100 / H200 | CUDA 12 | R450 (>= 450.80.02) or later |
| B200 | CUDA 12 | R570 (>= 570.133.20) or later |
| RTX PRO 6000 Blackwell | CUDA 12 | R575 (>= 575.51.03) or later |
| GB300 (DGX Station) | CUDA 13 | R595 (>= 595.58.03) or later |

The MIG minimum is a floor, not a target. Use a current production or LTSB branch.

## Component matrix

| Component | Version | Source | Status |
|---|---|---|---|
| GPU Operator | 26.7.2 | `https://github.com/NVIDIA/gpu-operator/releases` | VERIFIED |
| k8s-device-plugin | v0.20.1 | `https://github.com/NVIDIA/k8s-device-plugin/releases` | VERIFIED |
| NVIDIA Container Toolkit | v1.20.1 | `https://github.com/NVIDIA/nvidia-container-toolkit/releases` | VERIFIED |
| Driver branch | R580 or R595 | NVIDIA driver matrix | VERIFIED for the branch set, UNVERIFIED for the exact patch to deploy |
| Driver patch | 595.71.05 | NVIDIA release notes | VERIFIED as the latest listed release; not yet pinned |
| CUDA toolkit (container) | 13.x with R595, 12.x with R580 | NVIDIA driver matrix | VERIFIED for the branch mapping |

## GPU Operator version pairing

The GPU Operator upgrades the driver, the container toolkit, the device plugin, and DCGM together. The driver and toolkit versions it ships must be compatible with each other.

Procedure before every operator upgrade:
1. Read the operator release notes for the target version and list the `driver.version` and `toolkit.version` it ships.
2. Confirm the toolkit release notes for that version state compatibility with the driver version.
3. Confirm the operator's supported Kubernetes versions cover the cluster version.
4. Mirror the new driver, toolkit, and operator images into Harbor before the upgrade.
5. Drain one GPU node first, upgrade it, verify `nvidia-smi` and a test pod, then continue.

## Kernel and driver coupling

The NVIDIA kernel module is built against the running kernel. A kernel update without a matching module makes the GPU invisible. On a managed node the GPU Operator rebuilds the module as part of the driver deployment, but the rebuild takes time and the node must be drained.

Rule: never upgrade the kernel on a GPU node without a planned drain, and never uncordon it before `nvidia-smi` returns a valid result.

## Offline artifacts

| Artifact | Destination | Notes |
|---|---|---|
| NVIDIA driver runfile / RPM | `nexus.internal/rpm-nvidia` | Pin the exact patch version; keep the matching kernel-module package for each kernel version in the fleet |
| CUDA toolkit container | `harbor.internal/platform/cuda` | Multi-GB; mirror per version |
| NVIDIA Container Toolkit | `nexus.internal/rpm-nvidia` + `harbor.internal/platform/nvidia-container-toolkit` | The toolkit ships a container toolkit and a `nvidia-ctk` binary; the operator consumes the container |
| GPU Operator chart | `harbor.internal/charts/gpu-operator` | Pin the chart version |
| GPU Operator images | `harbor.internal/platform/gpu-operator` | driver, toolkit, device plugin, dcgm-exporter, k8s-device-plugin, and the operator itself |
| DCGM Exporter | `harbor.internal/platform/dcgm-exporter` | Pin the version matching the operator release |

## Validation after any driver change

```bash
# On the node
nvidia-smi                       # must list the expected GPUs
nvidia-smi -q | grep -i "driver version"
lsmod | grep nvidia

# In a pod
kubectl run gputest --rm -it --restart=Never \
  --image=harbor.internal/platform/cuda:<version> \
  --overrides='{"spec":{"nodeSelector":{"node-role.kubernetes.io/gpu":"true"},"containers":[{"name":"gputest","image":"harbor.internal/platform/cuda:<version>","command":["nvidia-smi"],"resources":{"limits":{"nvidia.com/gpu":1}}}]}}' \
  -- nvidia-smi
```

Expected: `nvidia-smi` inside the pod lists the same GPU count as on the host, and the driver version matches the host driver version.
