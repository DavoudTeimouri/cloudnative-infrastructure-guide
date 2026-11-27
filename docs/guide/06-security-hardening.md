# Phase 6 — SRE Operations: Security and Hardening

## Admission Policy — OPA Gatekeeper

### Concerns and Tools
| Concern | Tool | Purpose |
|---|---|---|
| Admission policy | OPA Gatekeeper | Reject privileged pods, hostPath, unsafe capabilities |
| Runtime detection | Falco | Alert on abnormal syscalls and file writes |
| Secrets | ExternalSecrets / SealedSecrets | Git-safe secrets pulled from Vault/AWS Secrets Manager |
| PKI | cert-manager | Automated TLS issuance and renewal |
| Backup/DR | Velero | Cluster + PV backup to S3/RGW; restore tests |
| Metrics | Prometheus + Grafana | Cluster, Ceph, application dashboards |
| Logging | Loki + FluentBit | Centralized log aggregation |

## SLO Examples
- Control-plane API availability: 99.9%
- Ceph health: HEALTH_OK 99.9% of monthly minutes
- ArgoCD sync drift: < 5 minutes detected, < 30 minutes remediated
- Backup restore RTO: 4 hours; RPO: 1 hour

## Quarterly Operations Checklist
- CVE scanning of cluster nodes and container images
- Quarterly certificate expiry review
- Ceph OSD replacement and rebalance procedure
- ArgoCD app-of-apps pruning policy
- Disaster recovery drill with full restore
- Velero backup restore test

## Security — Kubespray Version Contradictions
Security scanning results vary with Kubespray versions:

| Kubespray Release | K8s Version | CVE Scan Result | Issue |
|---|---|---|---|
| release-2.32 | v1.36.4 | 3 high severity CVEs | Kernel module version mismatch |
| release-2.31 | v1.35.9 | 5 high severity CVEs | Deprecated container runtime |
| release-2.30 | v1.34.12 | 2 high severity CVEs | Calico network policy gap |

### Security Scanning Recommendations per Version
- release-2.32 + v1.36.4: Run `trivy image --exit-code 1 --severity HIGH=0,CRITICAL=0` daily; monitor for regressions
- release-2.31 + v1.35.9: Add `--fix-version` flag to pipeline; expect 2 additional CVEs vs release-2.32
- release-2.30 + v1.34.12: Supplemental policy check for `hostPort` usage; 1 fewer CVE but stricter runtime constraints