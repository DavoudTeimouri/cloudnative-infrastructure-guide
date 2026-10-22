# Vault recovery

The recovery path must work when the cluster, the identity provider, and the network are all in a bad state. This procedure is written for that case.

## Preconditions

| Item | Where it lives | Who holds it |
|---|---|---|
| Vault raft snapshot | Object storage (Ceph RGW bucket `vault-backup/`) and offline media | SRE + a second custodian |
| Unseal key shares | Offline, split between custodians | 3+ custodians, quorum of 3 |
| Root token | Offline, separate from the shares | Security lead |
| Configuration backup (`vault` config directory) | Encrypted offline archive | SRE |
| CA material | Vault PKI, backed up offline | SecOps |

If any of these is missing, the backup is not a backup. Verify the procedure quarterly.

## Backup

```bash
# On a Vault node
vault operator raft snapshot save -name=backup-$(date +%F)
vault operator raft snapshot status -name=backup-$(date +%F)

# Copy to object storage
aws --endpoint-url https://rgw.internal s3 cp \
  backup-$(date +%F).snapshot s3://vault-backup/snapshots/

# Copy to offline media (physically separate, later)
```

Also back up the Vault server configuration:

```bash
tar czf vault-config-$(date +%F).tar.gz /etc/vault.d /etc/systemd/system/vault.service
```

## Restore onto new hosts

1. Install the same Vault binary version on the new hosts. Verify with `vault version`.
2. Restore the configuration archive and set the file ownership to the `vault` user, mode 0640 for `/etc/vault.d`.
3. Initialize the new cluster's storage:

```bash
# On the first new node, with the storage backend configured but not initialized
vault operator init -key-shares=5 -key-threshold=3
```

This prints the unseal key shares and the root token. Do not store them in a ticket, a chat message, or a Git repository. Print them, record them offline, and destroy the terminal output.

4. Join the remaining nodes:

```bash
vault operator raft join -node-id=<node-id>
```

5. Unseal with the quorum of shares:

```bash
vault operator unseal <key-share-1>
vault operator unseal <key-share-2>
vault operator unseal <key-share-3>
```

6. Verify leadership and health:

```bash
vault status
# expect: initialized, unsealed, HA enabled, leader = true
```

7. Restore the raft snapshot (this replaces the freshly initialized data):

```bash
# Stop Vault on all nodes first
vault operator raft snapshot restore backup-2026-10-17.snapshot
```

Restoring a snapshot into a freshly initialized cluster and then unsealing works. Restoring into a cluster that already has data requires the documented `snapshot_force_restore` procedure — read the Vault documentation for the pinned version before using it.

8. Re-authenticate with the root token from the offline escrow:

```bash
vault login
```

9. Verify the data:

```bash
vault secrets list
vault auth list
vault policy list
vault kv list secret/
```

10. Restart the remaining nodes and confirm HA:

```bash
systemctl start vault
vault status
```

## Recovery of a single failed node

```bash
# On the failed node
systemctl stop vault
rm -rf /etc/vault.d/raft
# Re-join from a healthy node
vault operator raft join -node-id=<node-id>
```

## Recovery when the seal status cannot be cleared

If a quorum of the original shares is unavailable, the cluster cannot be unsealed with them. The options, in order of preference:

1. Use the root token with `vault operator generate-root` to generate a new set of shares. This requires a quorum of existing shares, so it does not help if the shares are lost.
2. Restore from the raft snapshot (the path above). This loses everything since the snapshot.
3. Accept the loss of the secrets and re-issue them. This is why some secrets have an external source of truth (the directory, the GitLab registry, the OS configuration) and why a rotation plan exists.

There is no fourth option. A sealed Vault with lost shares is unrecoverable. That is the reason for offline custody of the shares and the reason for the break-glass procedure.

## Post-recovery verification

```bash
# Auth methods work
vault auth list

# Dynamic secret engines issue credentials
vault read database/creds/<role>

# PKI issues certificates
vault write pki/issue/<role> common_name=test.internal ttl=1h

# The Kubernetes auth method can reach the API server
vault write auth/kubernetes/login role=<role> jwt=<token>

# Audit device is active
vault audit list
```

Then re-run the acceptance tests for secrets: S-01 (delivery), S-02 (rotation), S-03 (certificate renewal), and D-06 (failover).

## Order of recovery in a total-loss scenario

```
1. Network, DNS, NTP
2. OS baseline via Ansible
3. Internal CA
4. Artifact repositories (Harbor, Nexus)
5. GitLab
6. Keycloak
7. VAULT          <- before the cluster
8. Automation server / AWX
9. Ceph
10. Kubernetes cluster
11. Management Cluster + Rancher
12. Argo CD + add-ons
13. GPU workers
14. Applications
```

Vault comes before Kubernetes on purpose. The cluster's secrets must exist before the cluster that consumes them, and a cluster loss must not be able to take the secrets with it.
