# AWX

AWX is the optional web UI, RBAC layer, and scheduler in front of the Ansible
control repository (`ansible/README.md`). It does not replace the repository: the
playbooks, inventories, and group vars stay in Git, and AWX runs them.

**Version: not pinned.** No AWX release is recorded in
`compatibility/version-matrix.md`, so no version is asserted here. Add a row with a
source URL and check date before deploying, and mirror the images offline.

## When to use it

Use AWX when more than one team needs to run automation without SSH access to the
automation server, or when jobs must run on a schedule with an audit trail.
A single platform team running playbooks from the automation server does not need
it — `automation/ansible/index.md` is sufficient and has fewer moving parts.

## Deployment shape

| Decision | Choice | Reason |
|---|---|---|
| Runtime | Kubernetes (Operator) in the management cluster | Reuses the platform's HA, backup, and ingress instead of a second VM stack |
| Database | PostgreSQL inside the cluster, backed up with Velero | AWX state is job history and credentials, not cluster state |
| Exposure | Ingress with TLS, identity through Keycloak | Same SSO path as the rest of the platform (ADR-0031) |
| Credentials | AWX credential objects sourced from Vault at job start | No long-lived secrets in AWX's database where avoidable |

Images must be copied to the internal registry before deployment; AWX pulls
several images (web, task, EE) and the default execution environment.

## Prerequisites

1. Management cluster running: `management-cluster/rancher/rancher.md`.
2. Internal registry with the AWX images and an execution environment image that
   contains the pinned Ansible and Python versions (`compatibility/version-matrix.md`).
3. A PostgreSQL instance or the operator's bundled database, with backup coverage
   (`lifecycle/backup/backup-and-dr.md`).
4. Keycloak client registration if SSO is required (`management-cluster/keycloak/keycloak.md`).

## Operating rules

- Projects are synced from Git; "manual" projects are not permitted, because they
  make the running configuration unverifiable.
- Inventories are sourced from the repository, not typed into the UI, for the same
  reason.
- Job templates map one-to-one to playbooks in `site.yml`'s import graph.
- Credentials are attached to job templates, never to ad-hoc jobs run by users.
- Job output is retained long enough to cover an audit window; the retention value
  is a site decision, recorded in the deployment values.

## Validation

```bash
kubectl -n awx get pods
kubectl -n awx logs deploy/awx-operator-controller-manager --tail=50
# A test job must complete against a staging inventory before production use.
```

## Failure modes

| Failure | Effect | Recovery |
|---|---|---|
| AWX unavailable | Scheduled jobs stop; playbooks can still be run from the automation server | Restore the AWX namespace from Velero, or run the playbook manually |
| Execution environment image missing from the mirror | Jobs fail at start | Mirror the image; do not point AWX at a public registry |
| Database loss | Job history and AWX-local credentials lost | Restore from Velero; re-create credentials from Vault |
| SSO misconfiguration | Users cannot log in | Local admin account remains as break-glass, stored offline |
