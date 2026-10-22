# Deliverable 9 — GPU and AI Architecture

## 9.1 GPU worker reference architecture

```
+--------------------------------------------------+
| GPU Worker Node                                   |
|  CPU: 2x socket, NUMA-aware, AVX-512              |
|  RAM: >= 512 GB (H200) / >= 256 GB (H100)         |
|  Disks: 2x NVMe 3.84TB (model cache + container  |
|         runtime), 1x boot disk                    |
|  NIC: 2x 25/100GbE (RDMA/RoCE for multi-GPU)     |
|  GPU: 4-8x H100 SXM 80GB or H200 141GB           |
|                                                  |
|  [GPU Operator]  driver + toolkit + device plugin|
|        |                                         |
|  [DCGM Exporter] -> Prometheus                   |
|        |                                         |
|  [vLLM / llama.cpp] -> OpenAI-compatible API     |
+--------------------------------------------------+
```

Isolation from general workers: dedicated taints, dedicated node pool, dedicated network segment, separate resource quota. Reason: GPU nodes are expensive, have different failure modes (ECC, thermal, driver), and are a noisy-neighbour risk for CPU/memory-constrained workloads.

## 9.2 Hardware and software compatibility

Exact versions are maintained in `compatibility/version-matrix.md` and `gpu-ai/drivers/compatibility-matrix.md`. The chain that must line up:

```
NVIDIA driver (branch) -> CUDA runtime -> NVIDIA Container Toolkit -> containerd -> GPU Operator -> k8s-device-plugin
```

Rule: the NVIDIA Container Toolkit must be compatible with the installed driver. The GPU Operator upgrades driver + toolkit + operator together and can transiently break running GPU pods during upgrade — plan a GPU node drain for operator upgrades.

MIG: only on supported GPUs and only on specific SKUs. Verify per model: H100 SXM and H100 PCIe support MIG; H200 supports MIG. A100 supports MIG on specific SKUs. Consumer GPUs do not. The exact profile list per GPU must be read from the official NVIDIA documentation — recorded with the check date in `gpu-ai/sharing/mig-profiles.md`.

## 9.3 GPU sharing decision matrix

| Mechanism | Isolation | VRAM partitioning | Reconfigure downtime | Overhead | Multi-tenant | Inference fit | Recommendation |
|---|---|---|---|---|---|---|---|
| Exclusive (whole GPU per pod) | Full | N/A | None | None | One pod per GPU | High-throughput serving | **Production default** |
| MIG | Hardware-level, hard | Yes, fixed profiles | Yes (drain + reconfigure) | Low | Strong | Latency-sensitive multi-tenant | **Production, multi-tenant** |
| Time-slicing | None | No (shared VRAM pool) | None | Medium-high (context switching) | Weak | Dev, burst, batch | Dev only |
| MPS | Same process address space | No | None | Low | Weak | Low-latency shared inference | Limited use |

Hard facts to hold: time-slicing does **not** provide VRAM isolation — one tenant's memory pressure can OOM another tenant's process. MIG provides hardware-level partition but each MIG instance is a separate GPU partition with a fixed memory slice; it cannot be combined with time-slicing of the same parent GPU in a useful way (time-slicing across MIG instances is possible but pointless for isolation goals). Multiple physical GPUs do **not** combine into one device with unified VRAM: they are separate devices, connected by NVLink/PCIe, and used either for model parallelism (sharded weights) or independent replicas. vLLM tensor parallelism splits one model across GPUs; it does not create a single larger GPU.

## 9.4 GPU scheduling

Labels and taints:

```yaml
# Applied by Ansible to GPU nodes
nodeLabels:
  nvidia.com/gpu.present: "true"
  nvidia.com/gpu.deploy.k8s.io/operator: "true"
  nvidia.com/gpu.product: "H100-80GB-HBM3"   # exact value from `nvidia-smi -L` + operator discovery
nodeTaints:
  - key: nvidia.com/gpu
    value: "true"
    effect: NoSchedule
```

Workload side:

```yaml
resources:
  limits:
    nvidia.com/gpu: 1
```

MIG-mode scheduling uses the MIG resource name published by the device plugin, e.g. `nvidia.com/mig-1g.10gb` — the exact resource names must be read from the live node (`kubectl describe node` shows advertised resources), not assumed.

Isolation model:
- Namespace-level quota on `nvidia.com/gpu`.
- PriorityClass for interactive inference vs batch.
- Gang scheduling for multi-GPU jobs (Volcano/Kueue) — required to avoid partial allocation deadlock.

## 9.5 LLM serving platform

| Engine | Throughput | Latency | Batching | Quantization | VRAM need | Ops complexity | Offline | Best fit |
|---|---|---|---|---|---|---|---|---|
| vLLM | High | Good | Continuous + chunked prefill | AWQ/GPTQ/FP8/FP16 | High (sharded across GPUs) | Medium | Yes | Primary production serving |
| llama.cpp | Low-Med | Low | Basic | GGUF (Q4/Q5/Q8/K-quants) | Low | Low | Yes | Edge, small models, CPU fallback |
| Triton | Medium-High | Good | Dynamic + model ensemble | Per-backend | Medium | High | Yes | Multi-framework estate |
| NIM | High (pre-optimized) | Good | Vendor-managed | Vendor-defined | Medium-High | Low (if license permits) | Image must be mirrored | Fast deploy, license permitting |

Selection: vLLM primary. llama.cpp for small/quantized models and CPU fallback. Triton only if non-LLM model types enter the estate. NIM evaluated against license and offline artifact size.

Serving API: OpenAI-compatible `/v1/chat/completions`, `/v1/completions`, `/v1/models`. Put an API gateway (NGINX + auth) in front; do not expose the vLLM port directly to the DMZ.

## 9.6 Multi-GPU inference

- **Tensor parallelism**: one model sharded across N GPUs. All N GPUs must be on the same node, connected by NVLink for acceptable performance; PCIe-only cross-socket works but with significant latency. Requires one pod requesting N GPUs.
- **Pipeline parallelism**: layers split across GPUs; higher latency, better for very large models where tensor parallelism is memory-constrained.
- **Data parallelism / replicas**: independent models on independent GPUs. Best throughput scaling, no inter-GPU communication.
- **Inter-node**: RDMA/RoCE + InfiniBand required for acceptable cross-node model parallelism. Design the fabric accordingly or keep model-parallel workloads node-local.

Network requirement: for H100 SXM 8-GPU nodes with NVSwitch, intra-node is fine; cross-node model parallelism must be sized on measured fabric bandwidth, not on nominal line rate.

## 9.7 Model artifact distribution

| Concern | Approach |
|---|---|
| Storage | Ceph RGW S3 (or MinIO) on the storage segment; models are large objects, not registry artifacts |
| Mirroring | Connected staging pulls from Hugging Face (or vendor CDN), records exact revision SHA, pushes to internal RGW |
| Integrity | SHA256 of each file recorded in `gpu-models` repo manifest; verify at load time |
| Versioning | Model = `<org>/<model>:<revision-sha>`; never "latest" |
| Pull path | Init container pulls from RGW, verifies checksum, populates a node-local NVMe cache (hostPath or local PV) |
| Cache | Per-node cache on NVMe; image-based distribution of weights is an alternative when the model is small or the fleet is uniform |
| Auth | Workload Identity to RGW (SigV4) with a per-team IAM-ish policy; credentials from Vault via External Secrets |
| Licensing | Some models carry usage licenses; record them in the model manifest and enforce approval before mirroring |

## 9.8 GPU observability

| Metric | Source |
|---|---|
| Utilization, memory, temp, power, ECC, PCIe errors | DCGM exporter |
| Driver/health, operator reconciliation | GPU Operator metrics |
| Container allocation, device plugin state | device plugin metrics + kubelet state |
| Inference throughput, req/s, tokens/s | vLLM `/metrics` |
| Time to first token, inter-token latency | vLLM metrics |
| Model load time, KV-cache usage | vLLM metrics |
| OOM events, restarts | Kubernetes + DCGM |

Dashboards: `gpu-ai/monitoring/dashboards/`. Alerts: OOM, ECC errors, sustained high temp, device plugin crash, low utilization with pending requests, KV-cache pressure.

## 9.9 AI security

- Model artifacts verified by checksum and stored in an access-controlled bucket; write-once.
- Serving images scanned (Trivy), signed (Cosign), and pulled by digest.
- API auth via OIDC tokens validated at the gateway; per-tenant quota and rate limits.
- GPU access controlled by namespace quota and taint tolerance; no default access.
- Audit: inference request metadata logged (model, tokens, tenant, latency), never prompt contents by default — add content logging only if a policy requires it, with explicit data-handling rules.
- Network: inference API only reachable from the DMZ gateway and approved cluster networks; model store only from GPU nodes.
