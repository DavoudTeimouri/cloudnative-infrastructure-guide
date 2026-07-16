# 3. Infrastructure Provisioning

## Overview
This section covers the step-by-step deployment of the core infrastructure components: HAProxy/Keepalived for load balancing, Ceph for distributed storage, and Kubernetes for container orchestration.

## Contents
- [Load Balancer (HAProxy/Keepalived)](load-balancer.md) - HA Layer 4/7 LB with VRRP
- [Ceph Cluster Deployment](ceph-cluster.md) - Multi-node Ceph with MON, MGR, OSD
- [Kubernetes Cluster (Kubeadm)](kubernetes-cluster.md) - Multi-master HA cluster with kubeadm
- [CSI Integration](csi-integration.md) - Ceph CSI driver for K8s persistent volumes
- [Verification](verification.md) - Health checks: `ceph health detail`, `kubectl get nodes`

## Prerequisites
- Prepared VMs from Phase 2
- Load balancer VIPs allocated
- Ceph disks prepared
- Kubernetes version selected

## Deployment Order
1. Deploy HAProxy/Keepalived (Load Balancer)
2. Deploy Ceph Cluster (Storage)
3. Deploy Kubernetes Cluster (Control Plane + Workers)
4. Install Ceph CSI Driver
5. Run verification checks