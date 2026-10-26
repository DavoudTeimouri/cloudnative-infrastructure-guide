# Ansible control repository (layout contract)

This directory holds the Ansible control repository. The layout is defined in
`automation/ansible/ansible-structure.md`; this file records the contract that
`automation/gitlab-ci/pipeline.md` and the Kubespray documents assume.

## Contract

```
ansible/
├── ansible.cfg               # inventory path, roles_path, host_key_checking = True
├── requirements.yml          # collections, pinned
├── requirements.txt          # python packages, pinned (Ansible 2.19.x, Python 3.12)
├── site.yml                  # single entry point
├── inventories/
│   ├── staging/hosts.ini
│   └── production/hosts.ini
├── group_vars/
│   ├── all/{main,offline,vault}.yml
│   └── <cluster>/main.yml
├── host_vars/
├── roles/{base,repositories,security,identity,monitoring,containerd,kubernetes,ceph,gpu,vault}/
└── playbooks/
```

The `identity` role exists as a placeholder and must stay empty: Linux hosts are
not joined to Active Directory or LDAP (ADR-0015, `decisions/ADR-0015-identity-integration-layer.md`).
Identity is application-layer only, through Keycloak.

## Version pins

| Component | Pin | Source |
|---|---|---|
| Ansible core | `>=2.19.0, <2.20.0` | `compatibility/version-matrix.md` |
| Python (control node) | 3.12 (supported 3.11–3.13) | `compatibility/version-matrix.md` |

Pin the same versions in `requirements.txt`; the Kubespray release branch defines
the window (`kubespray/multi-version-support.md`).

## Offline operation

`group_vars/all/offline.yml` carries the internal repository and registry
addresses. No playbook may reach the public internet: package, Python, and
collection installs resolve to the internal mirrors described in
`operating-systems/host-configuration.md` and `offline-artifacts/artifact-matrix.md`.

## Related

- Structure and `ansible.cfg`: `automation/ansible/ansible-structure.md`
- CI invocation (`--syntax-check`, `--check --diff`, then apply): `automation/gitlab-ci/pipeline.md`
- Automation server itself: `automation/ansible/index.md`
- Network paths used by Ansible: `network-matrix/network-communication-matrix.md` rows 20–21
