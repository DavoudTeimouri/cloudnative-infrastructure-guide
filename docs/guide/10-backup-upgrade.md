# 10. Backup & upgrade

**Purpose:** Make the platform recoverable and updatable — Velero for cluster backup/restore to Ceph,
Ceph disaster recovery, and Kubespray release upgrades.

## Prerequisites
- Steps 01–09 complete: platform fully deployed.

## Steps

### 10.1 Backup with Velero
Back up every cluster's resources and PVs to a Ceph RBD repository. Schedule regular backups and test
restores.

```bash
velero backup create --include-namespaces default,monitoring --schedule "0 2 * * *"
velero restore create --from-backup <latest>
```

Source: `lifecycle/backup/backup-and-dr.md`

### 10.2 Ceph disaster recovery
Back up the monmap and OSD maps; document the OSD data location. In a full-node loss, replace the host,
re-add via cephadm, and let Ceph rebalance. Never delete an OSD's data disk during recovery.

Source: `lifecycle/backup/backup-and-dr.md` (§Ceph recovery)

### 10.3 Upgrade Kubespray
Kubespray supports ≥ 5 releases in parallel. Upgrade one cluster at a time, control plane first, then
workers. Pin the target release in `compatibility/version-matrix.md`.

```bash
ansible-playbook -i inventory/my-cluster/hosts.yaml upgrade.yml -b
```

Source: `kubespray/multi-version-support.md`, `lifecycle/upgrades/upgrade-procedures.md`

### 10.4 Upgrade Ceph
Rolling upgrade of MON/MGR first, then OSDs, then RGW/MDS. Verify `HEALTH_OK` between each phase.

Source: `storage/ceph/cephadm-deployment.md` (§upgrade)

## Validation
- [ ] Velero backup completes; a restore test succeeds in a dry-run cluster.
- [ ] Ceph recovery runbook tested: a node loss is recoverable.
- [ ] Kubespray upgrade test run on a non-production cluster.
- [ ] Ceph upgrade tested on a dev cluster; `HEALTH_OK` after each phase.

## Navigation
**[← Prev · 09. Platform services](./09-platform-services.md)** | **[Back to guide index](./index.md)**
