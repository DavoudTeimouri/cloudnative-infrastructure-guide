# Performance and capacity planning

Guidance is separated into what is measured and proven versus what is workload-dependent. Every recommendation states the prerequisite, the impact, and how to undo it.

## Linux kernel

| Setting | Value | Why | Risk |
|---|---|---|---|
| `net.ipv4.ip_forward` | 1 | Required for routing | None |
| `net.bridge.bridge-nf-call-iptables` | 1 | Required for pod networking with bridged CNI | Traps bridged traffic through iptables |
| `fs.inotify.max_user_instances` | 8192 | Node agents watch many files | Memory per watch |
| `fs.inotify.max_user_watches` | 524288 | Same | Memory |
| `fs.file-max` | 1048576 | File descriptor ceiling | None |
| `vm.max_map_count` | 262144 | Required by Elasticsearch and OpenSearch | Memory |
| `vm.swappiness` | 1 | Kubernetes nodes should not swap | A swap-heavy workload will OOM instead |
| `net.core.somaxconn` | 32768 | Listen backlog | Memory per socket |
| `net.ipv4.tcp_keepalive_*` | 600/30/10 | Detect dead peers faster | None |

Baseline and rollback: the values live in `/etc/sysctl.d/99-kubernetes.conf`, applied by Ansible. Rollback is to delete the file and `sysctl --system`.

Measured, not guessed: any sysctl change is benchmarked before and after, with the same workload, and the numbers are recorded in the change record.

## CPU and memory

- Every container declares requests and limits. Requests drive scheduling; limits bound the blast radius.
- CPU limits throttling is a symptom of an incorrect limit, not a fix for contention.
- Memory limits equal the application's actual peak plus headroom. Too low causes OOM kills; too high allows one pod to starve a node.
- QoS classes: Guaranteed (requests == limits for CPU and memory) for critical system components; Burstable for applications; BestEffort for nothing.
- Do not set a CPU limit on latency-sensitive services without measuring the throttling.

## NUMA

- One GPU per NUMA node on H100/H200 SXM systems (the vendor topology).
- Pin GPU workloads with `nvidia.com/gpu` plus a topology-aware scheduler (Volcano, or a topology manager policy).
- Verify with `nvidia-smi topo -m` and `lscpu -e`.
- Impact: a workload that crosses NUMA boundaries pays a memory-bandwidth penalty.

## Disk and filesystem

| Media | Use | Notes |
|---|---|---|
| NVMe | etcd, Ceph journal, OSD DB, model cache, Prometheus | Local, not shared |
| SSD | Ceph data (hot), container logs | |
| HDD | Ceph data (cold), backup, archive | |

- XFS with `ftype=1` for any filesystem under an overlay2 container runtime.
- `noatime` on data filesystems: a measurable reduction in write amplification.
- Separate the journal from the data device on Ceph.
- Use `fio` for a baseline before any storage change. Record the queue depth and the block size; the numbers are meaningless without them.

## Network throughput and latency

- Measure the fabric before sizing storage. A 3x replicated pool consumes roughly 2x the client write bandwidth on the replication path.
- `iperf3` between OSD hosts establishes the real ceiling.
- MTU: with VXLAN, pod MTU = physical MTU - 50. With native routing, pod MTU = physical MTU.
- Bonding and LACP need the switch configured for the same mode; a mismatched hash policy causes poor distribution.
- RDMA/RoCE for multi-node model parallelism. Without it, inter-node tensor parallelism collapses.

## Container runtime

- containerd 2.x, `SystemdCgroup = true`.
- The runtime's log configuration controls disk growth: `max-size` and `max-file` on the containerd log driver.
- Registry mirror latency is on the critical path of every pod start. Keep the registry local to the cluster.

## Kubernetes scheduling

- Spread constraints for the control plane and for storage nodes.
- Pod anti-affinity for replicas of the same service, so a node loss does not take all of them.
- Topology spread constraints across zones where the site has them.
- Priority classes: system-node-critical for the platform, a defined priority for applications.
- Draining a node with a pod that has no matching toleration or a long grace period takes longer than expected. Test the drain time.

## Resource requests and limits

- Requests drive the scheduler's decision. An application with no requests is scheduled first-come-first-served and lands on the fullest node.
- A CPU request above the real usage wastes capacity; below it causes the scheduler to overcommit.
- Memory requests are the hard reservation. Set them from the measured peak.

## Autoscaling

| Controller | Use | Caution |
|---|---|---|
| HPA | Stateless services on a CPU or request-rate metric | Scale-up lag; the metric must reflect saturation |
| VPA | Memory-heavy services, in recommendation mode | Do not use with an HPA on the same metric |
| KEDA | Event-driven and queue-driven scaling | The queue metric must be real |
| Cluster autoscaler | Node count | Needs a working node template and a working CNI on new nodes |

For GPU inference, scale on queue depth, not on GPU utilization: a batched server shows high utilization while requests are still queuing.

## CNI and service mesh

- Cilium with kube-proxy replacement removes the iptables bottleneck. Measure the improvement before and after.
- Hubble adds flow observability with modest overhead.
- A service mesh adds a sidecar tax: roughly 10-30 MB per pod. Measure it before adopting (ADR-0009).

## Ceph

See `storage/ceph/cephadm-deployment.md` for the capacity worksheet. Performance-relevant settings:

| Setting | Guidance |
|---|---|
| `osd_pool_default_size` | 3 for production |
| `osd_pool_default_size` with EC | 4+2 for capacity-bound, read-mostly data |
| `mon_osd_min_in_size` / `max_in_size` | 1 / 2 during a degraded period only, as a temporary measure |
| `osd_max_backfills` | 1 for predictable IO during recovery, higher for faster rebuild |
| `osd_recovery_sleep` | 0 for faster rebuild at the cost of foreground IO |
| BlueStore allocator | `bluestore_allocator` on NVMe |
| `osd_memory_target` | Percentage of RAM for the OSD process cache; tune against the observed working set |

These are workload-dependent. Every change is benchmarked with `fio` against the same pool before and after.

## Prometheus and logging

- Prometheus: cardinality is the cost driver. Fix the label set before adding retention.
- Use recording rules for the expensive queries that dashboards run.
- Remote write to long-term storage rather than a longer local retention, when the object store is cheaper.
- Loki: label count per stream is the cost driver. Do not index the log content.
- OpenSearch: JVM heap and the merge policy dominate. Size the heap at half the container memory and no more.

## etcd

- etcd latency is disk latency. Use a dedicated local NVMe, never a shared filesystem.
- Monitor `etcd_disk_backend_commit_duration_seconds`. The p99 above 25 ms means the disk is the bottleneck.
- `--max-txn-ops` and the client-side rate limiters protect etcd from a burst.
- Compaction and defragmentation during business hours cause write latency spikes. Schedule them.

## GPU inference

See `gpu-ai/inference/llm-serving.md` for the serving configuration and `gpu-ai/drivers/compatibility-matrix.md` for the driver matrix.

- `--gpu-memory-utilization` controls how much VRAM the engine claims. Higher means more KV cache and more concurrency, but less headroom for fragmentation.
- `--max-model-len` is the context window. It scales the KV cache linearly with the sequence length, so an oversized value silently reduces concurrency.
- Continuous batching is why vLLM outperforms a naive implementation at high concurrency.
- Quantization (AWQ, GPTQ, FP8) reduces VRAM and increases throughput, at a documented accuracy cost. Measure the accuracy impact for the specific model before adopting it in production.
- Prefix caching removes repeated prefill cost for shared system prompts.
- The model load time is the scale-up latency. Keep `minReplicaCount` high enough to cover the steady-state load.

## Benchmarking discipline

A benchmark result without metadata is not a result. Record:

| Field | Example |
|---|---|
| Software versions | vLLM 0.32.0, CUDA 13.x, driver 595.71.05 |
| Model and revision | org/model@sha256:... |
| Quantization | AWQ INT4 |
| Hardware | 4x H100 80GB SXM5, NVSwitch |
| Parallelism | tensor-parallel 4 |
| Engine settings | max-model-len 8192, gpu-memory-utilization 0.90 |
| Workload | 200 prompts, 512 in / 512 out, concurrency 32 |
| Seed | 42 |
| Results | throughput, TTFT p50/p95/p99, ITL p50/p95/p99 |

Re-run the identical benchmark before and after every change. A claim of improvement without a re-run is not evidence.
