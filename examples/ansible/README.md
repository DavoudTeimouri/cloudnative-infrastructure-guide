# Ansible Playbooks

## Directory Structure
```
ansible/
├── inventory/
│   ├── hosts.yml
│   └── group_vars/
│       ├── all.yml
│       ├── lb.yml
│       ├── k8s-masters.yml
│       ├── k8s-workers.yml
│       └── ceph.yml
├── playbooks/
│   ├── 00-host-preparation.yml
│   ├── 01-loadbalancer.yml
│   ├── 02-ceph-cluster.yml
│   ├── 03-kubernetes.yml
│   ├── 04-csi-drivers.yml
│   ├── 05-monitoring.yml
│   └── validate.yml
├── roles/
│   ├── host-preparation/
│   │   ├── tasks/
│   │   │   ├── main.yml
│   │   │   ├── sysctl.yml
│   │   │   ├── modules.yml
│   │   │   ├── limits.yml
│   │   │   ├── swap.yml
│   │   │   ├── thp.yml
│   │   │   ├── cpu-governor.yml
│   │   │   ├── io-scheduler.yml
│   │   │   └── journal.yml
│   │   ├── handlers/
│   │   │   └── main.yml
│   │   └── templates/
│   │       ├── 99-kubernetes-ceph.conf.j2
│   │       └── kubernetes-ceph.conf.j2
│   ├── containerd/
│   ├── haproxy/
│   ├── keepalived/
│   ├── kubernetes/
│   ├── ceph/
│   ├── csi-drivers/
│   └── monitoring/
└── templates/
    ├── 99-cluster-network.yaml.j2
    ├── hosts.j2
    └── resolved.conf.j2
```

## Example: Inventory (ansible/inventory/hosts.yml)

```yaml
all:
  vars:
    ansible_user: root
    ansible_ssh_private_key_file: ~/.ssh/id_ed25519
    ansible_python_interpreter: /usr/bin/python3
  children:
    lb:
      hosts:
        lb-node-1:
          ansible_host: 192.168.1.10
          keepalived_state: MASTER
          keepalived_priority: 101
        lb-node-2:
          ansible_host: 192.168.1.11
          keepalived_state: BACKUP
          keepalived_priority: 100
      vars:
        haproxy_vip_k8s_api: 192.168.1.100
        haproxy_vip_ingress_http: 192.168.1.101
        haproxy_vip_ingress_https: 192.168.1.102
    
    k8s-masters:
      hosts:
        k8s-master-1:
          ansible_host: 192.168.1.20
        k8s-master-2:
          ansible_host: 192.168.1.21
        k8s-master-3:
          ansible_host: 192.168.1.22
      vars:
        k8s_version: "1.29.0"
        cni: "calico"
        pod_cidr: "10.244.0.0/16"
        service_cidr: "10.96.0.0/12"
    
    k8s-workers:
      hosts:
        k8s-worker-1:
          ansible_host: 192.168.1.30
        k8s-worker-2:
          ansible_host: 192.168.1.31
        k8s-worker-3:
          ansible_host: 192.168.1.32
```

## Example: Host Preparation Playbook (ansible/playbooks/00-host-preparation.yml)

```yaml
- hosts: all
  become: yes
  roles:
    - host-preparation

- hosts: all
  become: yes
  tasks:
    - name: Install containerd
      include_role:
        name: containerd

    - name: Install Kubernetes tools (masters + workers)
      include_role:
        name: kubernetes
        tasks_from: install-tools.yml
      when: "'k8s-masters' in group_names or 'k8s-workers' in group_names"
```

## Run Playbooks

```bash
cd ansible

# Validate inventory
ansible-inventory -i inventory/hosts.yml --list

# Run all preparation
ansible-playbook -i inventory/hosts.yml playbooks/00-host-preparation.yml

# Deploy load balancer
ansible-playbook -i inventory/hosts.yml playbooks/01-loadbalancer.yml

# Deploy Ceph
ansible-playbook -i inventory/hosts.yml playbooks/02-ceph-cluster.yml

# Deploy Kubernetes
ansible-playbook -i inventory/hosts.yml playbooks/03-kubernetes.yml

# Deploy CSI
ansible-playbook -i inventory/hosts.yml playbooks/04-csi-drivers.yml

# Deploy monitoring
ansible-playbook -i inventory/hosts.yml playbooks/05-monitoring.yml

# Validate
ansible-playbook -i inventory/hosts.yml playbooks/validate.yml
```