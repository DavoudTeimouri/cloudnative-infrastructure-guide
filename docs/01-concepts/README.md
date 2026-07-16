# 1. Core Concepts

## Overview
This section covers the theoretical foundations and architectural concepts underlying the cloud-native infrastructure stack.

## Contents
- [Kubernetes Architecture](kubernetes-architecture.md) - Control plane, worker nodes, CNI, CSI
- [Ceph Storage Architecture](ceph-architecture.md) - CRUSH maps, OSDs, MONs, PGs
- [Load Balancing & HA](load-balancing-ha.md) - VIPs, HAProxy, Keepalived, VRRP
- [VM Virtualization Templates](vm-templates.md) - Packer templates, cloud-init, cloud-config
- [Kubernetes Networking (CNI)](kubernetes-networking.md) - CNI plugins, Pod CIDR, Service CIDR

## Learning Objectives
- Understand VIP/VRRP for high availability
- Understand Ceph CRUSH map and data placement
- Understand VM template creation with Packer
- Understand Kubernetes CNI, Pod CIDR, Service CIDR concepts