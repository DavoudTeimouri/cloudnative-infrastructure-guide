# Automation management server (Ansible)

The automation server is the only host allowed to push configuration to the
estate. It runs Ansible from the control repository described in
`ansible/README.md`, and optionally AWX (`automation/awx/index.md`) as a UI and
scheduler in front of the same playbooks.

## Role in the design

| Concern | Decision |
|---|---|
| Configuration transport | SSH from the automation server to every managed node (port 22) |
| Secrets | Read from Vault at run time (port 8200); no secret values in Git or in `group_vars` |
| Directory integration | None on the hosts (ADR-0015); the automation server uses local accounts |
| Internet access | None. Packages, collections, and images come from internal mirrors |

Network paths: `network-matrix/network-communication-matrix.md` rows 20 and 21.

## Prerequisites

1. Host built from the OS baseline: `operating-systems/host-configuration.md`.
2. Internal mirrors reachable for `dnf`/`apt`, PyPI, and Ansible collections
   (`offline-artifacts/artifact-matrix.md`).
3. Vault reachable and unsealed; the automation server authenticates with its own
   AppRole or token, scoped to read only the paths its playbooks need.
4. SSH host keys for every managed node collected out of band and installed in
   `known_hosts`. `host_key_checking = True` is deliberate: do not disable it.
5. A dedicated automation account with sudo, plus the break-glass account that
   stays offline (`operating-systems/host-configuration.md`).

## Install

```bash
# Python and Ansible from the internal mirror
python3 -m venv /opt/ansible/venv
/opt/ansible/venv/bin/pip install -r requirements.txt   # pinned, no index fallback

# Collections from the internal Galaxy mirror
ansible-galaxy collection install -r requirements.yml
```

`pip` and `ansible-galaxy` must be configured to use the internal mirror only
(`group_vars/all/offline.yml`). A run that reaches the public internet has failed
the offline requirement.

## Operating rules

- `site.yml` is the only entry point; ad-hoc `ansible -m shell` is for diagnosis,
  not for change.
- Every change runs `--check --diff` first, then applies. CI enforces this order
  (`automation/gitlab-ci/pipeline.md`).
- Playbooks are idempotent. A second run with no changes reports zero changed
  tasks; a non-zero changed count on a no-op run is a defect.
- The control repository is the source of truth. Manual edits on managed nodes are
  drift and are reconciled by re-running the role that owns the file.

## Validation

```bash
ansible all -i inventories/production/hosts.ini -m ping
ansible-playbook -i inventories/production/hosts.ini site.yml --syntax-check
ansible-playbook -i inventories/production/hosts.ini site.yml --check --diff
```

## Failure modes

| Failure | Effect | Recovery |
|---|---|---|
| Automation server lost | No configuration changes possible; running workloads unaffected | Rebuild from the OS baseline and re-clone the control repository; Vault still holds secrets |
| Vault unreachable | Playbooks that read secrets fail before changing anything | Restore Vault first: `lifecycle/backup/backup-and-dr.md` §D |
| SSH key or host key mismatch | Playbook stops on the affected host | Re-collect the host key out of band; never disable host key checking |
| Mirror unreachable | Package and collection steps fail | Fix the mirror; do not add a public fallback |
