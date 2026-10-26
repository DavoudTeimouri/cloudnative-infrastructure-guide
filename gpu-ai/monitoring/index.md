# GPU monitoring

GPU metrics come from DCGM Exporter, scraped by the platform Prometheus and
rendered in Grafana. This is the observability layer for the GPU estate; the
scheduling model is in `gpu-ai/scheduling/index.md`.

Design context: `gpu-ai/gpu-ai-architecture.md` §9.5 and the monitoring summary.

## Data path

```
GPU node (DCGM Exporter :9400) -> Prometheus (scrape) -> Grafana / Alertmanager
```

DCGM Exporter is deployed by the GPU Operator as a DaemonSet on GPU nodes. It is
not a per-application exporter: one instance per node serves every GPU on that node.

## Versions and ports

| Item | Value | Source |
|---|---|---|
| DCGM Exporter | 4.8.4 | `compatibility/version-matrix.md` |
| GPU Operator | 26.7.2 | `compatibility/version-matrix.md` |
| Scrape port | TCP 9400 | `network-matrix/network-communication-matrix.md` row 43 |

## Metrics that matter

| Signal | Use |
|---|---|
| Utilization | Idle GPUs are the most expensive waste in the estate |
| Framebuffer memory used | Distinguishes real capacity pressure from transient spikes |
| Temperature and power | Thermal throttling shows up here before it shows up as latency |
| ECC errors (correctable and uncorrectable) | Uncorrectable errors mean the device must be drained |
| PCIe replay and link errors | Host or riser fault, not a GPU fault |
| XID errors | Driver-level faults; map the XID code to the NVIDIA table before acting |

## Alerts

- GPU OOM events (container killed with an OOM reason on a GPU node).
- Uncorrectable ECC error — page the on-call; drain the node.
- Sustained temperature above the vendor throttle threshold.
- Device plugin crash or DCGM Exporter down on a GPU node.
- GPU allocated but utilization near zero for a sustained window (waste, and often
  a stuck job).
- Pods pending with a GPU request while GPUs are free (scheduling defect, not
  capacity).

Thresholds are site values. Record them with the alert rules so a change is a
reviewed diff, not a UI edit.

## Dashboards

Store dashboard JSON in `gpu-ai/monitoring/dashboards/` and provision them from
Git (Grafana provisioning or the Grafana Operator). A dashboard edited in the UI
is lost on rebuild.

Minimum set:
1. Fleet view — GPUs per node, utilization, memory, temperature.
2. Node detail — per-device metrics, XID and ECC counters.
3. Workload view — GPU requests vs allocation, pending GPU pods, namespace quota usage.

## Validation

```bash
kubectl -n gpu-operator get pods -l app=nvidia-dcgm-exporter
curl -s http://<gpu-node>:9400/metrics | grep -c '^DCGM_FI_'
kubectl -n monitoring get servicemonitor | grep -i dcgm
```

A scrape target that is up but returns zero `DCGM_FI_*` series means the exporter
is running without device access — check the driver container, not Prometheus.

## Failure modes

| Failure | Effect | Recovery |
|---|---|---|
| DCGM Exporter down | No GPU metrics or alerts from that node; workloads unaffected | Restart the DaemonSet pod; check driver container |
| Prometheus scrape misconfigured | Metrics missing fleet-wide | Fix the ServiceMonitor; the exporter is still serving on :9400 |
| Alert threshold drift | Real incidents do not page, or noise hides them | Keep thresholds in Git with the rules |
| Dashboard edited in UI | Change lost on rebuild | Re-apply from `dashboards/` |

## Related

- Scheduling: `gpu-ai/scheduling/index.md`
- Platform monitoring: `management-cluster/platform-services/index.md`
- Backlog item: `requirements/component-guide-backlog.md` item 50
