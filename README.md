# 🌐 Cloud-Native Infrastructure Master Guide

Welcome! This repository is a comprehensive, step-by-step, and hands-on guide designed to help you **provision, prepare, deploy, maintain, and troubleshoot** production-grade, bare-metal or virtualized Cloud-Native infrastructure.

This guide walks you through building a highly available, robust infrastructure utilizing industry-standard open-source tools, starting all the way from Virtual Machine provisioning up to Kubernetes & Storage clusters.

---

## 🏗️ Core Architecture & Components

This guide walks you through building a resilient infrastructure from scratch, covering:
* **VM & Hypervisor Provisioning:** Automating VM creation on VMware vSphere using Terraform and Packer templates.
* **Operating System (OS):** Linux kernel tuning, sysctl optimizations, and system limits.
* **Load Balancer (LB):** High-availability Layer 4 & 7 load balancing (HAProxy & Keepalived).
* **Kubernetes Cluster (K8s):** Multi-master control plane provisioning using Kubeadm.
* **Distributed Storage (Ceph):** Production-ready Ceph cluster integration with K8s via CSI.

---

## 🗺️ Documentation Roadmap

The documentation is modularized into 6 main phases. Click on each section to deep-dive:

### [0. VM Provisioning (vSphere/Hypervisor)](docs/00-vm-provisioning/README.md)
* **Goal:** Create optimized VM templates (Ubuntu/Rocky Linux) using Packer and provision the virtual machines on vSphere using Terraform.
* **Verification:** Automated VM deployment verification and IP/MAC allocation checks.

### [1. Core Concepts](docs/01-concepts/README.md)
* **Goal:** Understand the underlying theory of VIPs, CRUSH maps (Ceph), VM virtualization templates, and K8s networking (CNI).
* **Verification:** Architectural diagrams and mental model check-ins.

### [2. Environment Preparation](docs/02-preparation/README.md)
* **Goal:** Configure host operating systems, disable swap, set up sysctl/limits, and configure firewalls on provisioned VMs.
* **Verification:** Run automated validation scripts to ensure environment compliance before installing anything.

### [3. Infrastructure Provisioning](docs/03-provisioning/README.md)
* **Goal:** Step-by-step deployment of HAProxy/Keepalived, a multi-node Ceph cluster, and a multi-master K8s cluster.
* **Verification:** Execute health verification commands (e.g., `ceph health detail`, `kubectl get nodes`).

### [4. Day-2 Operations & Upgrades](docs/04-operations-updates/README.md)
* **Goal:** Upgrading K8s control plane/nodes, scaling Ceph OSDs, rotating TLS certificates, and managing backups.
* **Verification:** Performing zero-downtime rolling updates while monitoring active workloads.

### [5. Advanced Troubleshooting](docs/05-troubleshooting/README.md)
* **Goal:** Diagnose and fix common networking loops, CrashLoopBackOff states, Ceph placement group (PG) errors, and disk failures.
* **Verification:** Practical fault-injection scenarios and step-by-step recovery playbooks.

---

## 🚀 How to Use This Repository

1. **Provision the Virtual Machines:** Start with `docs/00-vm-provisioning/` to launch your infrastructure on vSphere.
2. **Read the Concepts:** Read `docs/01-concepts/` to grasp the architecture of K8s, Ceph, and Networking.
3. **Set up the Nodes:** Follow `docs/02-preparation/` to configure your target operating systems.
4. **Use the Examples:** Head over to the `examples/` directory for ready-to-use Terraform configs, Packer templates, Ansible playbooks, and K8s manifests.
5. **Verify Each Step:** Never skip the **Verification** section at the end of each document.

---
✍️ **Contributing:** Contributions, bug reports, and suggestions are welcome! Feel free to open an Issue or submit a Pull Request.