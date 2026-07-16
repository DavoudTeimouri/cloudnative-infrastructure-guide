# 5. Advanced Troubleshooting

## Overview
This section provides diagnostic procedures and solutions for common infrastructure issues.

## Contents
- [Networking Issues](networking-issues.md) - Pod connectivity, CNI, DNS, VXLAN
- [Kubernetes Issues](kubernetes-issues.md) - CrashLoopBackOff, Node NotReady, etcd
- [Ceph Issues](ceph-issues.md) - PG stuck, OSD down, HEALTH_WARN/ERR
- [Storage Issues](storage-issues.md) - PVC pending, mount failures, CSI driver
- [Load Balancer Issues](lb-issues.md) - VIP failover, HAProxy backend checks

## Common Scenarios
- Pod-to-Pod communication fails
- Service/Ingress not accessible via VIP
- CrashLoopBackOff / ImagePullBackOff
- Node NotReady
- Ceph PGs degraded/undersized
- OSD down/out
- PVC stuck in Pending
- Volume mount fails

## Diagnostic Tools
- kubectl debug, logs, describe, get events
- ceph health detail, osd tree, pg dump
- HAProxy stats socket, Keepalived logs
- tcpdump, netstat, ss, iptables, ipvsadm

## Log Locations
Comprehensive log locations for all components included in each troubleshooting document.