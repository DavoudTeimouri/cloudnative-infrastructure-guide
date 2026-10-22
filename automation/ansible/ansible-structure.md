# Ansible automation structure

## Layout

```
ansible/
├── ansible.cfg
├── requirements.yml          # collections
├── requirements.txt          # python packages (pinned)
├── site.yml                  # entry point
├── inventories/
│   ├── staging/hosts.ini
│   └── production/hosts.ini
├── group_vars/
│   ├── all/
│   │   ├── main.yml
│   │   ├── offline.yml       # internal repo and registry settings
│   │   └── vault.yml         # vault host/paths, no secret values
│   └── <cluster>/
│       └── main.yml
├── host_vars/
├── roles/
│   ├── base/                 # base OS, users, ssh, sudo
│   ├── repositories/         # internal rpm/deb/pypi/helm
│   ├── security/             # sysctl, sshd, firewall, audit
│   ├── identity/             # sssd/realmd
│   ├── monitoring/           # node_exporter, fluent-bit
│   ├── containerd/           # runtime install and registry config
│   ├── kubernetes/           # kubespray wrapper
│   ├── ceph/                 # cephadm nodes
│   ├── gpu/                  # driver, labels, taints
│   └── vault/                # vault server nodes
└── playbooks/
```

## ansible.cfg

```ini
[defaults]
inventory = inventories/staging/hosts.ini
roles_path = roles
collections_path = ~/.ansible/collections:/usr/share/ansible/collections
host_key_checking = True
stdout_callback = yaml
callbacks_enabled = profile_tasks
interpreter_python = auto_silent
vault_password_file = ~/.vault_pass
gpg_private_key = ~/.gnupg/gitlab-runner.asc
timeout = 30

[persistent_connection]
command_timeout = 60
connect_timeout = 30

[ssh_connection]
pipelining = True
ssh_args = -o ControlMaster=auto -o ControlPersist=300s -o PreferredAuthentications=publickey
```

`host_key_checking = True` is deliberate. Disabling it removes the protection against a swapped host key.

## requirements

```yaml
# requirements.yml
collections:
  - name: community.general
    version: ">=8.0.0,<10.0.0"
  - name: ansible.posix
    version: ">=1.5.0,<2.0.0"
  - name: kubernetes.core
    version: ">=3.0.0,<5.0.0"
  - name: community.crypto
    version: ">=2.20.0,<3.0.0"
```

```txt
# requirements.txt — pinned exactly
ansible-core==2.19.2
ansible-lint==25.1.0
netaddr==1.3.0
jinja2==3.1.6
```

The Ansible version must match the Kubespray release's supported range. For Kubespray `release-2.32` that is ansible-core >=2.19.0, <2.20.0 with Python 3.11-3.13.

## Idempotency

Ansible playbooks are re-run routinely; a second run must report 0 changed.

Rules:
- Use modules, not shell commands, wherever a module exists.
- Where a shell command is unavoidable, guard it: `changed_when` on a meaningful condition, and `creates`/`removes` for file operations.
- Never use `command` without `changed_when: false` when the command is idempotent by nature.

Example of a correctly guarded task:

```yaml
- name: Ensure the containerd registry mirror is configured
  ansible.builtin.template:
    src: hosts.toml.j2
    dest: /etc/containerd/certs.d/{{ item }}/hosts.toml
    owner: root
    group: root
    mode: "0644"
  loop: "{{ containerd_registries }}"
  notify: restart containerd
```

Example of an incorrectly guarded task:

```yaml
# Wrong: always reports changed
- name: Set sysctl
  ansible.builtin.shell: sysctl -w {{ item.key }}={{ item.value }}
  loop: "{{ sysctl_settings }}"
```

The correct form uses `ansible.posix.sysctl`, which is idempotent and persists the value.

## Secrets in Ansible

| Use | Method |
|---|---|
| Look up at execution time | `community.general.hashi_vault` lookup, or `lookup('community.general.vault', ...)` |
| Bootstrap-time offline secrets | `ansible-vault` encrypted files, key stored in Vault and offline |
| Credentials in an inventory | Never. Use a lookup or a vault-encrypted variable file |

```yaml
- name: Read the registry password from Vault
  ansible.builtin.set_fact:
    registry_pass: "{{ lookup('community.general.hashi_vault', 'secret/registry/harbor', url=lookup('env','VAULT_ADDR'), auth_method='jwt') }}"
  no_log: true
```

`no_log: true` on any task that handles a secret. Without it the value appears in the job log.

## Vault lookup configuration

```yaml
# group_vars/all/vault.yml
vault_addr: "https://vault.internal:8200"
vault_role: "ansible"
vault_auth_path: "jwt"
vault_jwt_claim: "sub"
vault_validate_certs: true
vault_ca_path: /etc/pki/ca-trust/source/anchors/internal-ca.crt
```

The Vault JWT auth method needs the ansible user identity from Keycloak, with a Vault policy that grants read access to the paths the automation needs and nothing more.

## Execution order

`site.yml`:

```yaml
- name: Configure the operating system
  ansible.builtin.import_playbook: playbooks/base.yml

- name: Configure identity and monitoring
  ansible.builtin.import_playbook: playbooks/identity.yml

- name: Install and configure the container runtime
  ansible.builtin.import_playbook: playbooks/containerd.yml

- name: Deploy Kubernetes with Kubespray
  ansible.builtin.import_playbook: playbooks/kubernetes.yml
```

Each play targets a host group, so a partial run is possible with `--limit`.

## Tags

| Tag | Scope |
|---|---|
| `base` | OS baseline, packages, users |
| `security` | sysctl, sshd, firewall, audit |
| `identity` | SSSD/realmd |
| `monitoring` | node_exporter, Fluent Bit |
| `containerd` | Runtime and registry configuration |
| `kubernetes` | Kubespray cluster.yml |
| `ceph` | Ceph storage nodes |
| `gpu` | GPU worker preparation |
| `vault` | Vault server nodes |

## Validation

```bash
# Syntax
ansible-playbook -i inventories/staging/hosts.ini site.yml --syntax-check

# Lint
ansible-lint playbooks/ roles/

# Idempotency check (in staging)
ansible-playbook -i inventories/staging/hosts.ini site.yml --check --diff

# Post-run verification
ansible all -i inventories/staging/hosts.ini -m setup
```

## AWX integration

AWX consumes the same roles and inventories. Job templates map to the playbooks, with tags limiting the scope. Survey variables carry the environment-specific values.

AWX-specific configuration:
- Vault credentials are stored in AWX, sourced from Vault through a credential type plugin.
- Job templates run with `--check --diff` in the "Check" mode for validation.
- Instance groups point at the automation server or dedicated runners.
- The audit log records who ran what and when — that is the change-management evidence trail.
