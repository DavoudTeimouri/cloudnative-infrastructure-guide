# Backup and disaster recovery

## A. Scope

Backup targets and their recovery procedures, and the failure scenarios the platform must survive.

## B. What backs up what

| Target | Tool | Backup mechanism | Backup stored in | RPO | RTO | Restore procedure |
|---|---|---|---|---|---|---|
| OS configuration | Ansible + Git | Git repository | GitLab (replicated + off-site) | Immediate (commit) | 1 h | Re-run the baseline playbook |
| Kubespray inventory | Git | Git repository | GitLab | Immediate | 1 h | Restore from Git |
| etcd | Kubespray + etcdctl | `etcdctl snapshot save` | Object storage + offline | 24 h | 1 h | `etcdctl snapshot restore` |
| Kubernetes resources + PVs | Velero | CSI snapshots + object storage | Object storage (Ceph RGW) | 24 h | 4 h | `velero restore` |
| Ceph (platform) | RBD export / CephFS snapshot | Object storage | RGW bucket | 24 h | 4 h | `rbd import` / snapshot restore |
| GitLab | GitLab backup + object storage | `gitlab-backup` | Object storage + off-site | 24 h | 4 h | `gitlab-restore` |
| Harbor | DB dump + registry storage | `pg_dump` + filesystem copy | Object storage | 24 h | 2 h | Restore DB and registry |
| Nexus | Task + DB backup | Nexus task + `pg_dump` | Object storage | 24 h | 2 h | Restore task + DB |
| Vault | `vault operator raft snapshot save` | Object storage + offline | RGW + offline media | 24 h | 1 h | `vault operator raft snapshot restore` + unseal |
| Keycloak | Realm export + DB | `kc.sh export` + `pg_dump` | Object storage | 24 h | 2 h | Import realm |
| Argo CD | Git + DB | Git + `pg_dump` | GitLab + object storage | Immediate | 1 h | Restore DB, re-sync from Git |
| Prometheus | Volume snapshot | CSI snapshot | Object storage | 24 h | 4 h | Restore PVC |
| Loki | Volume snapshot | CSI snapshot | Object storage | 24 h | 4 h | Restore PVC |
| GPU worker config | Ansible + Git | Git | GitLab | Immediate | 1 h | Re-run playbook |
| AI model artifacts | Object store | Versioned + replicated | RGW (replicated) | n/a (immutable) | 1 h | Re-mirror from staging |
| PKI root material | Manual | Encrypted export | Offline media | n/a | 30 min | Import into Vault PKI |
| TLS leaf certs | cert-manager | Re-issued | n/a | n/a | 5 min | cert-manager re-issues |
| Red Hat / Oracle entitlements | n/a | Not backup-able | Vendor | n/a | n/a | Re-apply with the entitlement |

Critical distinction: **replication is not backup, and backup is not DR**.
- Replication (Ceph 3x, GitLab HA, Vault Raft) protects against a single component failure.
- Backup protects against logical corruption, accidental deletion, and ransomware.
- Disaster recovery is the full procedure: restore into a new environment, in a defined order, with the dependencies respected.

## C. Velero

Velero backs up Kubernetes resources and, with the CSI snapshotter, the persistent volumes.

```bash
# Install (via Argo CD in this platform)
velero install \
  --provider aws \
  --bucket <backup-bucket> \
  --secret-file ./credentials \
  --backup-location-config region=<region> \
  --use-volume-snapshots=true \
  --snapshot-move-data=true \
  --default-volumes-to-restic=false
```

Backup schedule:

```yaml
apiVersion: velero.io/v1
kind: Schedule
metadata:
  name: daily-full
  namespace: velero
spec:
  schedule: "0 2 * * *"
  template:
    ttl: 720h          # 30 days
    includedNamespaces: ["*"]
    excludedNamespaces: ["velero", "kube-system", "kube-public"]
    storageLocation: default
    snapshotVolumes: true
    defaultVolumesToFsBackup: true
    hooks:
      resources:
        - apiVersion: v1
          kind: Pod
          name: fsfreeze
          namespaces: [postgres]
          labelSelector: "app=postgres"
          beforeOperation:
            - exec:
                container: postgres
                command: ["/bin/sh", "-c", "psql -U postgres -c 'SELECT pg_backup_start()'"]
          afterOperation:
            - exec:
                container: postgres
                command: ["/bin/sh", "-c", "psql -U postgres -c 'SELECT pg_backup_stop()'"]
```

The freeze hook is what makes the backup application-consistent. Without it, a database backup is a torn copy.

Backup location: a bucket in the Ceph RGW (or MinIO), with versioning enabled and object lock if the platform supports it.

Recovery:

```bash
velero backup get
velero backup describe <backup> --details
velero restore create <backup> --namespace-mappings <old>:<new>
velero restore get
velero restore describe <restore> --details
```

Tested restore procedure (must be executed at least quarterly):
1. Create a scratch cluster from the same Kubespray inventory.
2. Install Velero pointing at the same bucket.
3. Restore the most recent backup.
4. Verify a sample of applications, their data checksums, and their connectivity.
5. Record the actual RTO.

## D. Vault backup

```bash
# Snapshot
vault operator raft snapshot save -name=backup-$(date +%F)
# Verify
vault operator raft snapshot status -name=backup-$(date +%F)

# Restore (on a new or rebuilt cluster)
vault operator raft snapshot restore backup-2026-10-22
# Then unseal with the offline shares
```

The backup set must include: the raft snapshot, the unseal key shares (or the auto-unseal KMS configuration), the root token, and the CA material. Store the shares and the root token in separate physical locations from the snapshot. A backup that cannot be unsealed is not a backup.

## E. GitLab backup

```bash
# Omnibus install
gitlab-backup create
# Copy the tar to object storage
```

Also back up: the repositories (via the backup or a mirror), LFS objects, the container registry data, the configuration files, and the encryption keys/secrets file. The secrets file is required to restore — without it, the backup cannot be restored usefully.

## F. Failure scenarios and procedures

| Scenario | Immediate impact | Procedure | Target RTO |
|---|---|---|---|
| Single node loss | One node's workloads reschedule | Drain, replace, rejoin via Kubespray | 2 h |
| Control-plane quorum loss | No API access | Restore the etcd snapshot onto a healthy member | 1 h |
| Worker pool loss | Reduced capacity | Rebuild nodes from Ansible + Kubespray | 4 h |
| GPU worker loss | Reduced inference capacity | Replace the card or the node | 4 h |
| Ceph disk loss | Pool degraded, rebalancing | Replace the disk, Rook/cephadm recreates the OSD | 4 h |
| Ceph node loss | OSDs down, rebalance | Replace the host, recreate the OSDs | 8 h |
| Management Cluster loss | No GitOps sync, no Rancher | Restore Argo CD and Rancher from backup; workloads keep running | 4 h |
| Vault outage | No secret issuance or renewal | Restore from the raft snapshot and unseal; or run on the existing cluster if sealed data is intact | 2 h |
| Identity provider outage | No new logins | Use break-glass local accounts | 1 h (workaround) |
| Registry outage | No new image pulls | Pull from the node cache; re-import from Nexus | 4 h |
| Automation server loss | No Ansible, no CI | Rebuild from GitLab; restore the AWX database | 4 h |
| GitLab outage | No commits, no CI | Work from a mirror; restore from backup | 4 h |
| Complete environment loss | Everything | Follow the full rebuild order below | 24-48 h |

## G. Full environment rebuild order

The order is dictated by dependencies, and the whole point of the architecture is that it works without a cluster.

```
1.  Network, DNS, NTP           (no dependencies)
2.  OS baseline via Ansible      (needs the automation host or an Ansible runner)
3.  Internal CA / PKI            (needs the OS)
4.  Artifact repositories        (Harbor, Nexus) — image + package source
5.  GitLab (source of truth)     (needs artifacts + PKI)
6.  Identity (Keycloak)          (needs PKI + GitLab for realm export)
7.  Vault                        (needs PKI + a KMS/unseal procedure)
8.  Automation server / AWX      (needs GitLab + Vault)
9.  Storage (Ceph)               (needs OS + network)
10. Kubernetes cluster           (needs artifacts + storage + Vault)
11. Management cluster + Rancher (needs identity + Vault)
12. Argo CD + add-ons            (needs GitLab + Vault + cluster)
13. GPU workers                  (needs cluster + artifacts)
14. Applications                 (needs Argo CD + everything above)
```

The critical property: steps 1-8 do not require Kubernetes. If the cluster is lost, the recovery path does not depend on the thing that was lost.

## H. Validation

Backup validation is part of the acceptance criteria, not an afterthought:

- A Velero backup exists and its contents are listed.
- A restore into a scratch namespace succeeds and the application data matches.
- A Vault snapshot restores and unseals with the offline shares.
- A GitLab backup restores into a scratch instance.
- The full rebuild procedure is exercised at least once in the offline environment.
- Every backup has a recorded RPO and a measured RTO.

## I. Best practices

Mandatory:
- Backups stored outside the failure domain of the source. A backup on the same cluster does not survive the cluster.
- Vault's backup set includes the unseal material and the root token, stored separately.
- Backups are encrypted at rest and access-controlled.
- Restore is tested, not assumed. A backup that has never been restored is a hypothesis.
- `fsfreeze`/quiesce hooks for every stateful application.

Strongly recommended:
- 3-2-1 for the most critical data: 3 copies, 2 media types, 1 off-site.
- Immutable or object-locked backup storage where the platform supports it, so a compromised administrator cannot delete the backups.
- Monthly restore drills of one application, quarterly of the full environment.
- Record the measured RTO in this file after each drill.
