# 🖥️ VM Provisioning & Base Config (vSphere, Packer, Terraform, PowerCLI, and Ansible)

This phase covers the end-to-end automation of generating golden operating system images, cloning VMs dynamically using Terraform or VMware PowerCLI, and establishing a baseline environment using Ansible.

## 🎯 Objectives
* **Packer:** Create standardized Ubuntu/Rocky Linux vSphere templates.
* **Terraform / PowerCLI:** Automate the cloning and sizing of cluster nodes on vSphere.
* **Ansible:** Configure base network configurations, system updates, and user keys post-boot.

## 🛠️ Infrastructure Provisioning Options

We provide two primary lanes to provision your virtual hardware:

### Option A: Modern IaC (Terraform)
Highly recommended for team environments and GitOps flows.
1. Configure your state in `examples/terraform/vsphere/`.
2. Run `terraform apply` to provision the topology declared in your TF manifests.

### Option B: Scripted Orchestration (VMware PowerCLI)
Best for system administrators transitioning from manual workflows.
1. Open PowerShell with VMware.PowerCLI module installed.
2. Review and execute the script: `./examples/powercli/provision_vms.ps1`

## 🚀 Step 3: Base Configuration via Ansible

Once VMs are spun up via Terraform or PowerCLI, Ansible takes over to bootstrap them.

1. Navigate to `examples/ansible/`.
2. Map your correct target IPs inside `hosts.ini`.
3. Run the baseline playbook:
   ```bash
   ansible-playbook -i hosts.ini baseline.yml
   ```

## 🔍 Verification & Diagnostics

1. **Verify SSH Fingerprints:**
   Confirm that Ansible can ping and authenticate with all newly created VMs:
   ```bash
   ansible all -i hosts.ini -m ping
   ```

2. **Verify Hard Disk layout:**
   For Ceph nodes, confirm the existence of unformatted secondary disks across all targets:
   ```bash
   ansible ceph_nodes -i hosts.ini -a "lsblk"
   ```