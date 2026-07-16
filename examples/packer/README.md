# Packer Templates

## Directory Structure
```
packer/
├── ubuntu-22.04/
│   ├── ubuntu-22.04.pkr.hcl
│   ├── http/
│   │   └── user-data
│   ├── scripts/
│   │   ├── base-packages.sh
│   │   ├── kernel-tuning.sh
│   │   ├── containerd.sh
│   │   ├── kubernetes.sh
│   │   └── cleanup.sh
│   └── variables.pkrvars.hcl
├── ubuntu-24.04/
│   ├── ubuntu-24.04.pkr.hcl
│   ├── http/
│   │   └── user-data
│   ├── scripts/
│   └── variables.pkrvars.hcl
├── rocky-9/
│   ├── rocky-9.pkr.hcl
│   ├── http/
│   │   └── ks.cfg
│   ├── scripts/
│   └── variables.pkrvars.hcl
└── vsphere-iso.pkr.hcl (shared configuration)
```

## Example: Ubuntu 22.04 Template (packer/ubuntu-22.04/ubuntu-22.04.pkr.hcl)

```hcl
packer {
  required_plugins {
    vsphere = {
      version = ">= 2.5.0"
      source  = "github.com/hashicorp/vsphere"
    }
  }
}

variable "vsphere_server"      { type = string }
variable "vsphere_user"        { type = string }
variable "vsphere_password"    { type = string }
variable "vsphere_datacenter"  { type = string }
variable "vsphere_datastore"   { type = string }
variable "vsphere_cluster"     { type = string }
variable "vsphere_network"     { type = string }
variable "vsphere_folder"      { type = string }
variable "vsphere_template"    { type = string }
variable "vm_name"             { type = string, default = "ubuntu-22.04-template" }
variable "vm_cpu"              { type = number, default = 2 }
variable "vm_memory"           { type = number, default = 4096 }
variable "vm_disk_size"        { type = number, default = 50 }

source "vsphere-iso" "ubuntu-22.04" {
  # vSphere connection
  vcenter_server     = var.vsphere_server
  username           = var.vsphere_user
  password           = var.vsphere_password
  insecure_connection = true
  
  # VM configuration
  datacenter         = var.vsphere_datacenter
  datastore          = var.vsphere_datastore
  cluster            = var.vsphere_cluster
  network            = var.vsphere_network
  folder             = var.vsphere_folder
  
  # VM specs
  cpu                = var.vm_cpu
  memory             = var.vm_memory
  disk_size          = var.vm_disk_size
  
  # Guest OS
  guest_os_type      = "ubuntu64Guest"
  
  # ISO
  iso_paths          = ["[datastore] iso/ubuntu-22.04.4-live-server-amd64.iso"]
  boot_order         = "disk,cdrom"
  boot_command       = [
    "<enter><wait>",
    "linux /casper/vmlinuz autoinstall ds=nocloud-net;s=http://{{ .HTTPIP }}:{{ .HTTPPort }}/ cloud-config-url=http://{{ .HTTPIP }}:{{ .HTTPPort }}/user-data ip=dhcp ---<enter>"
  ]
  
  # HTTP directory for cloud-init
  http_directory = "http"
  
  # SSH
  ssh_username = "ubuntu"
  ssh_password = "ubuntu"
  ssh_wait_timeout = "30m"
  
  # Post-processor: convert to template
  conversion_options = {
    "template" = true
  }
}

build {
  sources = ["source.vsphere-iso.ubuntu-22.04"]
  
  provisioner "shell" {
    scripts = [
      "scripts/base-packages.sh",
      "scripts/kernel-tuning.sh",
      "scripts/containerd.sh",
      "scripts/kubernetes.sh",
      "scripts/cleanup.sh"
    ]
    environment_vars = [
      "DEBIAN_FRONTEND=noninteractive"
    ]
  }
  
  post-processor "manifest" {
    output_path = "manifest.json"
    strip_path  = true
  }
}
```

## Build Commands

```bash
cd packer/ubuntu-22.04/

# Initialize
packer init .

# Validate
packer validate .

# Build with variables file
packer build -var-file=variables.pkrvars.hcl .

# Or build with inline variables
packer build \
  -var 'vsphere_server=vcenter.example.com' \
  -var 'vsphere_user=administrator@vsphere.local' \
  -var 'vsphere_password=secret' \
  -var 'vsphere_datacenter=DC1' \
  -var 'vsphere_datastore=datastore1' \
  -var 'vsphere_cluster=Cluster1' \
  -var 'vsphere_network=VM Network' \
  -var 'vsphere_folder=templates' \
  -var 'vm_name=ubuntu-22.04-k8s-template' \
  .
```