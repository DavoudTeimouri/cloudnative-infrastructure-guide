# Terraform vSphere Examples

## Directory Structure
```
terraform/vsphere/
├── main.tf
├── variables.tf
├── outputs.tf
├── versions.tf
├── modules/
│   ├── vsphere-vm/
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   └── vsphere-network/
│       ├── main.tf
│       ├── variables.tf
│       └── outputs.tf
└── environments/
    ├── dev/
    │   ├── main.tf
    │   ├── terraform.tfvars
    │   └── backend.tf
    ├── staging/
    │   ├── main.tf
    │   ├── terraform.tfvars
    │   └── backend.tf
    └── prod/
        ├── main.tf
        ├── terraform.tfvars
        └── backend.tf
```

## Example: Main Module (modules/vsphere-vm/main.tf)

```hcl
variable "vm_name" {
  type        = string
  description = "Name of the VM"
}

variable "template_name" {
  type        = string
  description = "Template to clone from"
}

variable "datastore" {
  type        = string
  description = "Datastore to deploy VM on"
}

variable "resource_pool" {
  type        = string
  description = "Resource pool"
}

variable "network_label" {
  type        = string
  description = "Network label (port group)"
}

variable "num_cpus" {
  type        = number
  default     = 4
}

variable "memory_mb" {
  type        = number
  default     = 16384
}

variable "disk_size_gb" {
  type        = number
  default     = 100
}

variable "customization_spec" {
  type        = string
  description = "Customization spec name"
}

resource "vsphere_virtual_machine" "vm" {
  name             = var.vm_name
  resource_pool_id = var.resource_pool
  datastore_id     = var.datastore
  folder           = var.folder
  
  num_cpus = var.num_cpus
  memory   = var.memory_mb
  guest_id = var.guest_id
  
  network_interface {
    network_id   = var.network_id
    adapter_type = "vmxnet3"
  }
  
  disk {
    label            = "disk0"
    size             = var.disk_size_gb
    eagerly_scrub    = false
    thin_provisioned = true
  }
  
  clone {
    template_uuid = var.template_id
    customize {
      linux_options {
        host_name = var.vm_name
        domain    = var.domain
      }
      network_interface {
        ipv4_address = var.ipv4_address
        ipv4_netmask = var.ipv4_netmask
      }
      ipv4_gateway = var.ipv4_gateway
      dns_server_list = var.dns_servers
      dns_suffix_list = var.dns_suffixes
    }
  }
}
```

## Usage

```bash
cd terraform/vsphere/environments/prod
terraform init
terraform plan
terraform apply
```