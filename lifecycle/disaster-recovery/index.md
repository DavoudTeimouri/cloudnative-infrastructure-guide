# Disaster recovery runbooks

This directory holds the recovery procedures. Backup **mechanics** are in
`lifecycle/backup/backup-and-dr.md`; this index is the entry point for using them
under pressure, and it defines the recovery order that the individual runbooks
must follow.

## Recovery order

The order is not negotiable: each step depends on the one before it.

1. **Vault** — unseal and confirm read access to secrets
   (`lifecycle/backup/backup-and-dr.md` §D, `secrets-management/vault/recovery/restore.md`).
2. **Identity** — Keycloak, so platform components can authenticate users
   (`management-cluster/keycloak/keycloak.md`).
3. **Management cluster** — Rancher, Argo CD, and the platform services
   (`management-cluster/rancher/rancher.md`).
4. **Application clusters** — restore from Velero, then let Argo CD reconcile
   (`lifecycle/backup/backup-and-dr.md` §C).
5. **Workload data** — Ceph pools and application data, verified per application.

Restoring a cluster before Vault is available produces pods that cannot start;
restoring before identity means no one can log in to verify the result.

## Scenario index

| Scenario | Runbook | Notes |
|---|---|---|
| Single control-plane node lost | `kubernetes/control-plane/index.md` | No snapshot restore; rejoin the node |
| etcd quorum lost | `kubernetes/control-plane/index.md` §Backup | Restore from snapshot; running pods are not preserved |
| Management cluster lost | `lifecycle/disaster-recovery/management-cluster.md` | Velero restore, then Argo CD sync |
| Application cluster lost | `lifecycle/disaster-recovery/application-cluster.md` | Velero restore plus Ceph CSI reattachment |
| Vault lost or sealed | `secrets-management/vault/recovery/restore.md` | First step in every other recovery |
| Storage cluster degraded | `storage/ceph/cephadm-deployment.md` §Recovery | Do not restore workloads into a degraded pool |
| Full site rebuild | `lifecycle/backup/backup-and-dr.md` §G | Follows the same five-step order |

Runbooks named above that do not yet exist are tracked in
`requirements/component-guide-backlog.md` item 53. Until they are written, the
corresponding section of `lifecycle/backup/backup-and-dr.md` is authoritative.

## Rules that apply to every recovery

- **Declare the incident and the recovery point first.** Decide whether the target
  is the last backup or the last known-good state, and write down the timestamp.
  Restoring without a stated target turns into an open-ended investigation.
- **Restore into an isolated cluster when possible.** Verify data before pointing
  users at it.
- **One change at a time.** Restore, verify, then move to the next layer. Parallel
  restores make it impossible to attribute a failure.
- **Record actual RTO.** The elapsed time from declaration to verified service is
  the number that matters; it is also the input to the next test.
- **Test on a schedule.** A backup that has never been restored is a hypothesis.
  Test at least quarterly, and after any change to the backup path.

## Validation after recovery

```bash
vault status                       # unsealed, HA mode as designed
kubectl get nodes                  # all expected nodes Ready
kubectl get pods -A | grep -v Running | grep -v Completed
velero get restore                 # restore completed, no partial failures
kubectl get pvc -A                 # all bound
```

A restore is complete when the validation commands pass and the application owner
has confirmed data, not when the restore job reports `Completed`.

## Related

- Backup scope and mechanics: `lifecycle/backup/backup-and-dr.md`
- Upgrade and rollback: `lifecycle/upgrades/upgrade-procedures.md`
- Failure domains: `architecture/03-failure-domains.md`
