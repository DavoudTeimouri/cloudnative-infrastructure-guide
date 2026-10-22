# LLM inference serving

## A. Purpose and scope

Serving large language models on the GPU worker pool: engine selection, model distribution, multi-GPU configuration, API exposure, autoscaling, and observability.

## B. Engine selection

| Criterion | vLLM | llama.cpp | Triton | NIM |
|---|---|---|---|---|
| Throughput (large model) | Highest | Low | High | High (pre-optimized) |
| Latency | Low with continuous batching | Low | Good | Low |
| Batching | Continuous + chunked prefill | Basic | Dynamic, multi-model | Vendor-managed |
| Quantization | AWQ, GPTQ, FP8, FP16 | GGUF (Q4/Q5/Q8, K-quants) | Per-backend | Vendor-defined |
| VRAM need | High | Low | Medium | Medium-high |
| Multi-GPU | Tensor/pipeline parallel | Layer split | Ensemble | Per deployment |
| Ops complexity | Medium | Low | High | Low (if licensed) |
| Offline | Yes (weights + image) | Yes | Yes | Yes if image mirrored and licence permits |
| Best fit | Production LLM serving | Small models, CPU, edge | Mixed model estate | Fast deploy |

Decision: vLLM primary. llama.cpp for small/quantized models and CPU fallback. Triton only if non-LLM model types enter the estate. NIM only after a licence review and an offline artifact size check.

## C. Model distribution

Models are large S3 objects, not container images. They live in Ceph RGW (or MinIO) in the `models/` bucket.

### Mirror procedure (connected staging)

```bash
# Record the exact revision, never "latest"
export HF_REPO=<org>/<model>
export HF_REV=<commit-sha>

huggingface-cli download "$HF_REPO" \
  --revision "$HF_REV" \
  --local-dir "./models/$(echo $HF_REPO | tr '/' '-')" \
  --include "*.safetensors" "*.json" "*.model" "*.txt"

# Checksums for verification at load time
find ./models -type f -exec sha256sum {} \; > model-checksums.txt

# Push to the internal object store
aws --endpoint-url https://rgw.internal s3 sync ./models s3://models/<org>/<model>/<rev>/
```

The manifest (model name, revision, files, checksums, licence, VRAM requirement, context length) is committed to the `gpu-models` GitLab project. Weights are not.

### Pull at runtime

An init container pulls and verifies:

```yaml
initContainers:
  - name: fetch-model
    image: harbor.internal/platform/model-fetcher:<pinned>
    command: ["/bin/sh", "-c"]
    args:
      - |
        set -e
        aws --endpoint-url "$S3_ENDPOINT" s3 cp \
          "s3://models/$MODEL_PATH/config.json" /models/config.json
        # ... remaining files
        sha256sum -c /models/checksums.txt
    env:
      - name: MODEL_PATH
        value: "org/model/rev"
      - name: S3_ENDPOINT
        value: "https://rgw.internal"
    volumeMounts:
      - name: model-cache
        mountPath: /models
    envFrom:
      - secretRef:
          name: model-store-credentials   # from Vault via External Secrets
```

Alternative for a uniform fleet: bake the weights into a container image. Simple, but the image becomes several tens of gigabytes and every model change means a new image. Use the image path only for small models or a single-model fleet.

### Local NVMe cache

```yaml
volumes:
  - name: model-cache
    hostPath:
      path: /mnt/models
      type: DirectoryOrCreate
```

Each node keeps a copy on local NVMe. A DaemonSet warms the cache before the inference pods start. The cache key is the model revision, so a rollout to a new revision pulls once per node.

## D. vLLM deployment

Single GPU:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: vllm-llama
  namespace: ai
spec:
  replicas: 2
  selector:
    matchLabels: {app: vllm-llama}
  template:
    metadata:
      labels: {app: vllm-llama}
    spec:
      nodeSelector:
        node-role.kubernetes.io/gpu: "true"
      tolerations:
        - key: nvidia.com/gpu
          operator: Equal
          value: "true"
          effect: NoSchedule
      containers:
        - name: vllm
          image: harbor.internal/platform/vllm:<pinned>
          args:
            - "--model=/models/model"
            - "--served-model-name=llama"
            - "--port=8000"
            - "--tensor-parallel-size=1"
            - "--gpu-memory-utilization=0.90"
            - "--max-model-len=8192"
            - "--trust-remote-code=false"
          ports:
            - containerPort: 8000
          resources:
            limits:
              nvidia.com/gpu: 1
              memory: 120Gi
            requests:
              nvidia.com/gpu: 1
              memory: 60Gi
          readinessProbe:
            httpGet: {path: /health, port: 8000}
            initialDelaySeconds: 120
            periodSeconds: 10
          livenessProbe:
            httpGet: {path: /health, port: 8000}
            initialDelaySeconds: 300
            periodSeconds: 30
          volumeMounts:
            - {name: model-cache, mountPath: /models}
          envFrom:
            - secretRef: {name: model-store-credentials}
      volumes:
        - name: model-cache
          hostPath: {path: /mnt/models, type: DirectoryOrCreate}
```

Key parameters:
- `--gpu-memory-utilization` — the fraction of VRAM vLLM may claim. Leave headroom for KV cache growth and for co-tenants. 0.90 is typical for a dedicated GPU.
- `--max-model-len` — context length. Larger costs KV cache memory. Set it to the real requirement; an oversized value silently reduces concurrency.
- `--tensor-parallel-size` — number of GPUs for one model replica. Must match `nvidia.com/gpu: N`.
- `--trust-remote-code=false` — keep it off unless a specific model requires it, and review the model code when it is on.

## E. Multi-GPU inference

Two distinct things, often confused:

**Model parallelism** — one model spread across several GPUs. vLLM's `--tensor-parallel-size N` shards the weights and the attention heads across N GPUs inside a single pod. It requires N GPUs on the same node. A pod requesting `nvidia.com/gpu: 4` with `--tensor-parallel-size 4` does this.

**Data parallelism** — independent model replicas, each on its own GPU. This is just `replicas: N` with `--tensor-parallel-size 1` and the scheduler spreading them across nodes. It scales throughput without any inter-GPU communication and is the preferred path unless a single model does not fit on one GPU.

What multi-GPU does NOT do: it does not create a single device with unified VRAM. A 4x H100 80GB setup with tensor parallelism gives 320 GB of *aggregate* memory for one model, and the model still must be sharded — the engines cooperate over NVLink, and each layer's activation still lives on its own GPU.

Cross-node model parallelism needs RDMA/RoCE. With plain TCP the all-reduce communication dominates and throughput collapses. Design the fabric accordingly or keep model-parallel workloads node-local.

### Memory sizing

```
weights_bytes ≈ params × bytes_per_param
KV_cache_bytes ≈ 2 × layers × kv_heads × head_dim × seq_len × batch × dtype_bytes
```

Measure with `vllm` startup logs, which report the weight size and the KV cache blocks allocated. Use those numbers, not the formula, for capacity planning.

## F. API exposure

The inference port is never exposed directly. An API gateway handles authentication, rate limiting, and routing:

```
client -> NGINX (TLS, OIDC token validation, rate limit) -> vLLM service -> GPU nodes
```

```nginx
upstream vllm_backend {
    least_conn;
    server vllm-llama.ai.svc.cluster.local:8000;
}

server {
    listen 443 ssl http2;
    server_name llm.internal;
    ssl_certificate     /etc/nginx/tls/tls.crt;
    ssl_certificate_key /etc/nginx/tls/tls.key;

    location / {
        auth_request /oauth2_verify;
        limit_req zone=llm burst=20 nodelay;
        proxy_pass http://vllm_backend;
        proxy_read_timeout 600s;
        proxy_buffering off;
    }
}
```

Token validation with Keycloak:

```nginx
location = /oauth2_verify {
    internal;
    proxy_pass https://keycloak.internal/realms/ai/protocol/openid-connect/token;
    proxy_pass_request_body off;
    proxy_set_header Content-Length "";
    proxy_set_header X-Original-URI $request_uri;
}
```

## G. Autoscaling

| Signal | Use |
|---|---|
| Queue depth / pending requests | Primary for LLM serving (KEDA on a queue metric) |
| GPU KV-cache utilization | Secondary — high utilization with pending requests means saturation |
| Request latency (TTFT) | Guardrail, not a scale-up signal on its own |
| GPU utilization | Misleading: a batched server can show high utilization and still be queueing |

KEDA ScaledObject:

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: vllm-llama
  namespace: ai
spec:
  scaleTargetRef:
    name: vllm-llama
  minReplicaCount: 2
  maxReplicaCount: 8
  triggers:
    - type: prometheus
      metadata:
        serverAddress: http://prometheus.monitoring.svc:9090
        metricName: vllm:num_requests_waiting
        threshold: "5"
        query: "sum(vllm:num_requests_waiting{namespace='ai'})"
```

Cooldown must exceed the model load time. A scale-up that starts a pod which takes 5 minutes to load the model does not help a latency-sensitive request. Keep `minReplicaCount` at a level that covers the expected load, and scale out for bursts.

## H. Observability

vLLM exposes Prometheus metrics on `/metrics`. The important ones:

| Metric | Meaning | Alert |
|---|---|---|
| `vllm:num_requests_waiting` | Queue depth | Scale signal |
| `vllm:num_requests_running` | Concurrent requests | Capacity |
| `vllm:gpu_cache_usage_perc` | KV cache utilization | Saturation |
| `vllm:request_success_total` | Counter | Error rate |
| `vllm:e2e_request_latency_seconds` (histogram) | End-to-end latency | SLO |
| `vllm:time_to_first_token_seconds` (histogram) | TTFT | SLO |
| `vllm:time_per_output_token_seconds` (histogram) | Inter-token latency | SLO |
| `vllm:model_load_time_seconds` | Model load | Slow load |

TTFT and inter-token latency are the metrics a user feels. Track p95 and p99, not averages.

DCGM covers the hardware side: `DCGM_FI_DEV_GPU_UTIL`, `DCGM_FI_DEV_FB_USED`, `DCGM_FI_DEV_FB_FREE`, `DCGM_FI_DEV_GPU_TEMP`, `DCGM_FI_DEV_POWER_USAGE`, `DCGM_FI_DEV_GPU_XID_ERRORS`, `DCGM_FI_DEV_ECC_ERRORS`.

## I. Benchmarking

```bash
# Throughput and latency
vllm bench serve \
  --backend vllm \
  --model llama \
  --dataset-name sharegpt \
  --dataset-path ./sharegpt.json \
  --host 10.50.0.11 --port 8000 \
  --num-prompts 200 \
  --save-result --result-dir ./results

# Reproducible run
vllm bench serve --backend vllm --model llama \
  --num-prompts 200 --seed 42 --save-result --result-dir ./results
```

Record: model, revision, quantization, GPU model and count, tensor-parallel size, batch settings, input/output length distribution, concurrency, and the resulting throughput, TTFT p50/p95/p99, and ITL p50/p95/p99. Without that metadata the result is not comparable.

Before and after any change (quantization, new engine, different GPU), re-run the same benchmark and compare. `gpu-ai/inference/benchmarking.md` holds the procedure and the result template.

## J. Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| OOM at startup | Model plus KV cache plus runtime exceed VRAM | Lower `--gpu-memory-utilization`, lower `--max-model-len`, use quantization, more GPUs |
| OOM under load | Concurrency exceeds KV cache capacity | Lower `--max-model-len`, raise `--gpu-memory-utilization` carefully, or scale out |
| Pod stays Pending | No GPU capacity, or the resource name does not match (MIG) | `kubectl describe pod`; check advertised resources on the node |
| Container starts, `nvidia-smi` fails | Toolkit/runtime mismatch or a missing device plugin | `kubectl -n gpu-operator logs`; re-run `nvidia-ctk runtime configure` |
| Model load timeout | Weights not cached, pulling from object storage at start | Pre-warm the node-local cache |
| TTFT spikes | Cold cache, no prefix caching, or GPU contention | Enable prefix caching, check co-tenancy, verify the model is on local NVMe |
| High ITL | GPU saturated, or a slow tokenization path | Scale out, or check the CPU contention on the node |

## K. Best practices

Mandatory:
- Serve by digest, from a signed image.
- Never expose the inference port directly to the DMZ.
- Request the exact advertised resource (including MIG profiles).
- Keep inference pods off nodes with other GPU tenants unless isolation is intentional.

Strongly recommended:
- Keep `minReplicaCount` high enough for the steady-state load, and use autoscaling for bursts only.
- Cache models on local NVMe.
- Record every benchmark with full metadata.
- Test the OOM behaviour deliberately before production: know what happens when a tenant exceeds its MIG profile.
