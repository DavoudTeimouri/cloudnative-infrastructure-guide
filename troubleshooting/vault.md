# Vault troubleshooting

## Symptoms

- `vault status` reports `Sealed: true`.
- `vault login` returns a permission error.
- A secret is not found at an expected path.
- Secret delivery to a workload stops.
- A certificate is not renewed.
- The audit log stops receiving entries.

## Likely causes

| Cause | Discriminator |
|---|---|
| The cluster is sealed after a restart or an unclean shutdown | `vault status` shows `Sealed: true` |
| The token expired | `vault token lookup` fails, or a 403 with "permission denied" |
| The token lacks the policy | `vault token capabilities <path>` |
| The secret is at a different mount or version | `vault secrets list -detailed` |
| The application is using a stale cached token | The workload has not restarted since the rotation |
| The seal keys are unavailable | Fewer than the threshold of shares are held |
| The audit device's disk is full or its host is down | `vault audit list`, and check the audit device host |
| The Vault node is not the leader | `vault status` shows `HA Enabled: true` with `leader: false` |

## Diagnostic commands

```bash
# Status and seal state
vault status
vault status -format=json

# Leader and cluster members
vault operator raft list-peers
vault operator raft autopilot state

# Sealed and unseal
vault operator unseal <key-share>
vault operator seal
vault operator unseal -status

# Token
vault token lookup
vault token capabilities secret/apps/payments/db
vault token create -policy=app-payments -ttl=1h -renewable=false

# Secrets
vault secrets list -detailed
vault kv get -format=json secret/apps/payments/db
vault kv metadata get secret/apps/payments/db

# Auth methods
vault auth list
vault write auth/kubernetes/login role=app jwt="$JWT"

# Audit
vault audit list
vault audit list -detailed

# Runtime
vault operator raft autopilot configuration
curl -s http://127.0.0.1:8200/v1/sys/health | jq
```

## Expected healthy state

```
Sealed          false
HA Enabled      true
Key Shares      5
Key Threshold   3
Last Half Rotation Time   ...
Next Half Rotation Time   ...
```

`vault status` shows `Sealed: false`, `HA Enabled: true`, and one leader among the peers.

## Remediation

### Sealed cluster

```bash
# With the required number of shares
vault operator unseal <share-1>
vault operator unseal <share-2>
vault operator unseal <share-3>
vault status
```

If the shares are lost, the cluster cannot be unsealed with them. Options, in order: use the root token with `vault operator generate-root` (needs a quorum of shares, so it does not help if the shares are lost), or restore from the raft snapshot (`secrets-management/recovery/restore.md`). There is no other path.

### Permission denied

```bash
# What the token can actually do
vault token capabilities secret/apps/payments/db
vault token lookup -format=json | jq '.data.policies'

# Read the policy
vault policy read app-payments
```

Common causes:
- The policy path does not match the actual path. `secret/apps/payments/*` does not match `secret/apps/payments` (no trailing wildcard).
- The token was created with a policy that has since been changed.
- The namespace binding on the Kubernetes role does not include this service account.
- The policy grants `create` but not `read`, or `update` but not `read`.

### A secret is not found

```bash
vault secrets list -detailed        # confirm the mount and the KV version
vault kv get secret/apps/payments/db
vault kv list secret/apps/payments/
```

For KV v2, the API path is `secret/data/<path>` while the CLI takes `secret/<path>`. A path written for v1 fails against v2 with "no handler for route".

### Secret delivery stopped

```bash
# The injector
kubectl -n <ns> get pods -l vault.hashicorp.com/agent-inject=true
kubectl -n <ns> logs <pod> -c vault-agent-init -c vault-agent

# The External Secrets Operator
kubectl get externalsecrets -A
kubectl describe externalsecret <name> -n <ns>
kubectl -n external-secrets logs deploy/external-secrets --tail=100
```

Common causes:
- The Vault token the pod uses expired and the injector could not renew it.
- The service account token bound to the Vault role was deleted or recreated with a different name.
- The Vault auth method's `token_reviewer_jwt` expired.
- The Vault role's TTL is shorter than the pod's lifetime and renewal is disabled.

### Certificate not renewed

```bash
kubectl get certificaterequest -A
kubectl describe certificate <name> -n <ns>
kubectl -n cert-manager logs deploy/cert-manager -c cert-manager --tail=100
vault write pki/issue/<role> common_name=test.internal ttl=1h
```

Common causes:
- The issuer cannot reach Vault.
- The Vault PKI role's `max_ttl` is shorter than the certificate's requested TTL, so cert-manager cannot renew with the requested duration.
- The CA is expired or its intermediate has expired.

### Audit device stopped

```bash
vault audit list
vault audit list -detailed
df -h <audit-path>
```

An audit device that cannot write is disabled by Vault. Check the disk on the audit device host and re-enable it.

## Risks

- `vault operator seal` requires the same quorum to unseal. Do not seal a cluster casually.
- `vault policy write` affects every token bound to that policy immediately. Review the diff before applying.
- Deleting an auth method or a policy breaks every consumer of it.
- `vault operator raft snapshot save` on a cluster with a large backend takes time; a snapshot taken during heavy writes may not be consistent.

## Verification after remediation

```bash
vault status
vault read database/creds/<role>          # dynamic credential issuance
vault write pki/issue/<role> common_name=test.internal ttl=1h
vault write auth/kubernetes/login role=<role> jwt="$JWT"
kubectl -n <ns> get externalsecret
```

Then re-run acceptance tests S-01, S-02, S-03, and D-06.
