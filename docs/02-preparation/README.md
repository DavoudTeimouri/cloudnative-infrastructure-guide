# 2. Environment Preparation

## Overview
This section covers preparing the host operating systems on provisioned VMs for Kubernetes and Ceph workloads.

## Contents
- [OS Hardening & Tuning](os-hardening.md) - Kernel parameters, sysctl, limits
- [Container Runtime Setup](container-runtime.md) - containerd, CRI-O installation
- [Network Configuration](network-config.md) - Firewall, IP forwarding, CNI prerequisites
- [Ceph Prerequisites](ceph-prerequisites.md) - Disk preparation, NTP, SSH keys
- [Verification Scripts](verification.md) - Automated validation scripts

## Prerequisites
- Provisioned VMs from Phase 0
- SSH access to all nodes
- Root/sudo access on all nodes

## Quick Start
1. Run OS hardening scripts (see `os-hardening.md`)
2. Install container runtime (see `container-runtime.md`)
3. Configure networking (see `network-config.md`)
4. Prepare Ceph prerequisites (see `ceph-prerequisites.md`)
5. Run verification scripts (see `verification.md`)