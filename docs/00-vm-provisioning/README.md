# 0. VM Provisioning (vSphere/Hypervisor)

## Overview
This section covers the automated provisioning of Virtual Machines on VMware vSphere using Terraform and Packer.

## Contents
- [Packer Templates](packer-templates.md) - Building Ubuntu/Rocky Linux VM templates
- [Terraform Provisioning](terraform-provisioning.md) - Provisioning VMs on vSphere
- [Verification](verification.md) - Automated VM deployment verification

## Prerequisites
- VMware vSphere environment
- Packer installed
- Terraform installed
- vSphere credentials with appropriate permissions

## Quick Start
1. Build VM templates using Packer (see `packer-templates.md`)
2. Provision VMs using Terraform (see `terraform-provisioning.md`)
3. Run verification scripts (see `verification.md`)