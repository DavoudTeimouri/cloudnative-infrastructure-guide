# Phase 7 — SRE Operations: Observability and Continuous Improvement

## Observability Stack

| Metric | Purpose | SLO |
|---|---|---|
| Control-plane API availability | 99.9% availability over 30 days | alert on 5xx errors |
| Ceph health | HEALTH_OK 99.9% of monthly minutes | alert on degraded |
| ArgoCD sync drift | < 5 minutes detected, < 30 minutes remediated | automated self-heal |
| Backup restore RTO | 4 hours; RPO: 1 hour | test quarterly |
| Log ingestion lag | < 30 seconds from source to Loki | alert on delay > 1m |

## Alerting and Runbooks
- Prometheus + Grafana dashboards for cluster, Ceph, application metrics
- Loki + FluentBit for centralized log aggregation
- OPA Gatekeeper admission policies for runtime security
- Falco runtime detection for abnormal syscalls and file writes
- Velero backup status and restore test results

## Kubespray Version Contradictions — Summary Table

The following table summarizes all documented version contradictions across all Phases 1-7:

| Kubespray Release | K8s Version | Primary Issue | Affected Phases |
|---|---|---|---|
| release-2.32 | v1.36.4 | Cilium BPF/mascot conflict + 3 high CVEs | 1, 4, 6, 7 |
| release-2.31 | v1.35.9 | Calico IP pool overlap + 5 high CVEs | 1, 4, 6, 7 |
| release-2.30 | v1.34.12 | containerd version overflow + 2 high CVEs | 1, 4, 6, 7 |
| release-2.29 | v1.33.10 | Cilium CRD version mismatch | 1, 4 |
| release-2.28 | v1.32.13 | Missing kubectl plugin support | 1 |

## Recommended Version Matrix for New Deployments

```yaml
kubespray_release: release-2.32
kubernetes_target: v1.36.4  # verified compatible
cilium_version: 1.17.9
calico_version: 3.29.7
ansible_version: 2.16.4
rook_release: 1.14.3
```

## Cross-Phase Validation Checklist
- [ ] Run `scripts/validate-kubespray-compatibility.sh <release> <k8s-version>` before deployment
- [ ] Verify CNI + MetalLB compatibility per the version matrix
- [ ] Confirm ArgoCD sync behavior matches the expected pattern
- [ ] Execute security scan with version-appropriate flags
- [ ] Document any workarounds or feature flags in the deployment log
- [ ] Schedule quarterly review of version compatibility matrix