# 4. Day-2 Operations

## Overview
Day-2 operations cover ongoing maintenance, scaling, upgrades, backups, and disaster recovery for the deployed infrastructure.

## Contents
- [Kubernetes Upgrades](k8s-upgrades.md) - kubeadm upgrade plans, node draining
- [Ceph Operations](ceph-operations.md) - OSD replacement, PG rebalancing, scrub
- [Backup & Disaster Recovery](backup-dr.md) - Velero, Ceph RBD snapshots, etcd backup
- [Scaling Operations](scaling.md) - Adding/removing K8s workers, Ceph OSDs
- [Monitoring & Alerting](monitoring.md) - Prometheus, Grafana, Alertmanager rules
- [Certificate Rotation](cert-rotation.md) - etcd, kubelet, API server certs

## Operational Cadence
| Task | Frequency |
|------|-----------|
| Ceph health check | Daily |
| etcd backup | Daily |
| K8s certificate check | Weekly |
| OS patching | Monthly |
| K8s minor version upgrade | Quarterly |
| Ceph major version upgrade | Annually |

## Runbooks
See `runbooks/` directory for step-by-step operational procedures.