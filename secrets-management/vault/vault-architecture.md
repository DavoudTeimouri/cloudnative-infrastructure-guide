# Deliverable 8 — Secrets Management Architecture

**Product decision and licence position: `secrets-management/vault/hashicorp-vault-decision.md`.** HashiCorp Vault is the platform standard. OpenBao is the documented fallback if legal rejects the BSL.

## 8.1 Candidate comparison

| Criterion | HashiCorp Vault | OpenBao | SOPS + age | Sealed Secrets |
|---|---|---|---|---|
| License | BUSL since 1.15 (source-available, not OSI open source) | MPL 2.0 | Apache 2.0 | Apache 2.0 |
| Dynamic secrets | Yes (DB, SSH, PKI, cloud) | Yes (core set) | No | No |
| Leases/TTL/revocation | Yes | Yes | No | No |
| HA storage | Integrated Raft | Integrated Raft | n/a | n/a |
| Kubernetes auth | Yes | Yes | n/a | n/a |
| Secret injection | Agent, injector, CSI | Agent, injector, CSI | kubectl decrypt | controller |
| Audit log | Yes | Yes | No | No |
| Air-gap install | Yes | Yes | Yes | Yes |
| Ecosystem breadth | Largest | Smaller, no Vault Enterprise-only features | n/a | n/a |
| Ops burden | Medium | Medium | Low | Low |
| Verdict | **Adopted** (license review required) | Fallback | Bootstrap static only | Bootstrap static only |

Selection: **HashiCorp Vault** as primary because dynamic credentials, PKI, and leases are hard requirements in the master prompt (§15.4) and SOPS/Sealed Secrets cannot satisfy them. **OpenBao** is the documented fallback if the BUSL license is rejected by legal — the deployment model, policies, and integrations are designed to be portable; the only Vault-specific pieces are the Consul/Consul-template integration and any Vault Enterprise features.

License note: the Vault license changed with the 1.15 release. Confirm the current terms from the official HashiCorp licensing page before adopting, and record the check date in `compatibility/version-matrix.md`. Do not assume a version's license from memory.

## 8.2 Deployment model (provisional)

**Decision: Vault runs on dedicated Linux hosts outside the Management Cluster.**

| Option | Pros | Cons | Verdict |
|---|---|---|---|
| Dedicated Linux hosts (3) | Independent of K8s failure; unseal path independent of cluster; no circular dependency | 3 more hosts; manual HA config | **Adopted** |
| Inside Management Cluster | Cheaper; Helm-managed | Cluster loss = secret loss; unseal may need the cluster; admission issues on startup | Rejected (ADR-0025) |
| Kubernetes on a separate small cluster | Middle ground | Still couples secrets to K8s | Alternative if host count is constrained |

Topology: 3 Vault nodes, integrated storage (Raft), TLS on 8200, one-way replication for DR.

```
vault-a (active) ── raft ── vault-b (standby) ── raft ── vault-c (standby)
      │
      └─ File storage backend + periodic snapshot to S3 (Ceph RGW) or offline media
```

Break-glass unseal: Shamir key shares (3 of 5) held offline by separate custodians; or a KMS auto-unseal device if available. Both are documented in `secrets-management/vault/recovery/`.

## 8.3 Identity integration

| Consumer | Auth method | Notes |
|---|---|---|
| Human admins | OIDC via Keycloak | Group -> Vault role mapping |
| Ansible (automation server) | AppRole or JWT | AppRole with CI-like workflow; prefer JWT/OIDC if the identity flow allows |
| GitLab CI jobs | OIDC (GitLab ID token) -> Vault JWT auth | Edition/compat must be verified; fallback = AppRole with short TTL |
| Argo CD | Kubernetes auth (service account token) | Vault's own Kubernetes auth method; alternate = External Secrets Operator with Vault provider |
| Applications (in-cluster) | Kubernetes auth (SA token) | Least-privilege per app SA |
| Workload identity (K8s 1.24+ projected tokens) | Vault Kubernetes auth | Short-lived, no static SA secret |
| Ceph RGW / RBD | Ceph-native auth keys (separate from Vault) | Ceph keys stored in Vault, distributed to Ceph at deploy time |

Key point: AD integration for Linux (SSSD/realmd) does **not** automatically configure Vault, Kubernetes, or any application. Each application gets an explicit integration procedure.

## 8.4 Secret categories and storage

| Category | Vault path (example) | Delivery | Rotation |
|---|---|---|---|
| Linux/root creds | `secret/infra/linux/*` | Ansible fetch at runtime | 90d |
| SSH keys | `secret/infra/ssh/*` | Ansible + Vault SSH agent signing | 90d / on use |
| Kubespray bootstrap creds | `secret/infra/kubespray/*` | Ansible vault lookup | 90d |
| K8s app secrets | `secret/apps/<ns>/*` | External Secrets Operator -> K8s Secret | 30d |
| DB creds | `database/creds/<role>` | Dynamic (Vault DB engine) | 24h lease |
| Ceph keys | `secret/infra/ceph/*` | Ansible -> Ceph | 180d |
| GitLab CI creds | `secret/ci/*` | GitLab CI masked variables or OIDC | 30d |
| Harbor/Nexus auth | `secret/registry/*` | Ansible, containerd registries.conf | 90d |
| Argo CD repo creds | `secret/gitops/*` | Argo CD repo creds via API (not in Git) | 90d |
| Monitoring creds | `secret/observability/*` | External Secrets | 90d |
| Keycloak client secrets | `secret/identity/*` | Ansible / External Secrets | 90d |
| TLS certs + keys | `pki/issue/<role>` | cert-manager via Vault PKI | 30d, auto-renew |
| GPU service creds | `secret/ai/*` | External Secrets | 90d |
| Model API keys | `secret/ai/models/*` | External Secrets | 90d |
| Backup encryption keys | `secret/backup/*` | Ansible, Velero | 180d |
| Root CA private key | `pki/root/ca` (offline storage recommended) | Offline only | long, rotate by re-issue |

## 8.5 Dynamic secrets and rotation

- **Database credentials**: Vault DB engine issues username/password with TTL (default 24h). Application must re-read the credential on renewal. Vault has no control over apps that cache credentials forever — this must be verified per application.
- **SSH certificates**: Vault SSH signer issues short-lived certs; host/user trust against a CA. Requires `sshd` `TrustedUserCAKeys` configuration.
- **PKI**: Vault PKI issues and renews certs; cert-manager consumes it. Root CA private key stored offline; intermediate held in Vault.
- **Cloud/registry**: where the upstream supports dynamic tokens, use them; otherwise rotate static tokens on a schedule.
- **Revocation**: revoke leases, remove policies, rotate the underlying credential. For static credentials, rotation is an external automation action (Ansible job) — it is not transparent to the application.
- **After compromise**: revoke lease, rotate the credential at the source, re-deploy dependents, verify the new value is in use.

## 8.6 Secret delivery to Kubernetes — comparison

| Method | Mechanism | Persisted in etcd | Rotation behavior | App reload needed | Complexity | Notes |
|---|---|---|---|---|---|---|
| Vault Agent Injector | Sidecar writes file, syncs on renewal | Only if app uses K8s Secret; agent uses memory/file | Agent renews and rewrites file | App must re-read file or SIGHUP | Med | Best for file-based apps |
| Vault Agent templates (no injector) | DaemonSet/Deployment writes templated file | No | Same | Same | Med | Good for static config |
| Secrets Store CSI Driver | Mounts secret as file via CSI | No (unless synced) | Driver refreshes on renew | App must re-read | Med | Needs Vault CSI provider |
| External Secrets Operator | Syncs Vault -> K8s Secret | **Yes** | ESO refreshes on interval | App must restart or reload | Low | Operator-agnostic; adds etcd exposure |
| Direct app -> Vault API | App authenticates and reads | No | App handles renewal | App-native | Varies | No extra infra; more app work |
| K8s native Secret | Plain etcd secret | **Yes** | Manual | Yes | Low | Baseline only; no dynamic |

Explicit statement: External Secrets Operator does **not** eliminate the etcd persistence risk. It centralizes the source of truth and rotation, but the synchronized value still lands in etcd and is readable by anyone with RBAC on that Secret in that namespace. Mitigation: namespace-scoped RBAC, separate namespaces per team, encrypt etcd at rest, enable etcd encryption at rest with a KMS-backed key, restrict `get secrets` audit logging.

## 8.7 PKI

| Element | Owner | Location |
|---|---|---|
| Root CA (offline) | Vault PKI root | Encrypted Vault entry + offline backup; ideally on separate host/media |
| Intermediate CA | Vault PKI intermediate | Vault only, auto-expiry renewal policy |
| Server certs (ingress, services) | cert-manager | Kubernetes TLS Secrets |
| Client certs (Vault auth, mesh) | cert-manager or Vault | Depends |
| K8s internal PKI (apiserver, kubelet) | Kubespray | `/etc/kubernetes/pki` per node, rotated by Kubespray workflow |

Root CA rotation: issue new intermediate from root, switch issuance, wait for leaf expiry, revoke old intermediate. This is a multi-step, downtime-sensitive process — not a one-line operation. Document the runbook in `secrets-management/pki/root-ca-rotation.md`.

## 8.8 Recovery

- Vault backup: snapshot storage + `vault operator raft snapshot save`; store offline.
- Unseal: Shamir shares offline, or auto-unseal KMS.
- Restore runbook: `secrets-management/vault/recovery/restore.md`.
- Recovery order: Vault first (unseal), then identity (Keycloak), then Management Cluster, then Application Clusters. Argo CD may re-sync applications once Vault is back.
- A Kubernetes backup (Velero) does **not** include Vault's data unless Vault runs in-cluster and its storage is included. Our model keeps Vault outside the cluster, so Vault backup is a separate, mandatory procedure.

## 8.9 Monitoring and audit

Monitored: seal status, cluster leadership, replication health, storage usage, request latency and error rate, auth failures, lease/token expiry, certificate expiry, audit device health, backup freshness, rotation failures.

Audit: file or syslog device shipped to the logging platform. Audit logs must never contain secret values — Vault's audit log contains request/response metadata; HMAC-request-response mode is available to further protect values.

Never log: secret values, tokens, private keys, request payloads containing credentials.
