# HashiCorp Vault — product decision

**Check date: 2026-10-17.** The project standard is **HashiCorp Vault**. This file records why, which edition, what it costs, and what to do about the license.

## Decision

**HashiCorp Vault is the platform standard for secrets management and PKI.** OpenBao remains the documented fallback if legal rejects the license (see the licensing section), but the primary design, the runbooks, and the integrations all target HashiCorp Vault.

## Why HashiCorp Vault

The requirement set from the master prompt §15:

| Requirement | Vault | OpenBao | SOPS / Sealed Secrets |
|---|---|---|---|
| Dynamic database credentials with leases | Yes (DB secrets engine) | Yes | No |
| Short-lived tokens with renewal and revocation | Yes | Yes | No |
| SSH certificate signing | Yes (SSH secrets engine) | Yes | No |
| Internal PKI with issuance and rotation | Yes (PKI secrets engine) | Yes | No |
| Kubernetes auth method (service account tokens) | Yes | Yes | No |
| Audit devices with request/response logging | Yes | Yes | No |
| HA with quorum (Raft integrated storage) | Yes | Yes | No |
| Air-gapped install | Yes | Yes | Yes |
| Air-gapped secret injection into workloads | Yes (Agent, injector, CSI) | Yes (Agent, injector, CSI) | Partial |
| Enterprise-grade support contract | Yes (HashiCorp) | Community only | No |
| Official commercial product with a support SLA | Yes | No | No |

The deciding factors are the **dynamic secrets engine**, the **PKI engine**, and the **support path**. The first two are impossible with the Git-encrypted tools, and the third is a procurement question that SOPS and OpenBao cannot answer.

## Edition selection

| Capability | Vault Community (BSL) | Vault Enterprise | HCP Vault (hosted) |
|---|---|---|---|
| Core secrets engines (KV, database, PKI, SSH, transit) | Yes | Yes | Yes |
| Integrated Raft storage | Yes | Yes | Yes |
| HA (multi-node) | Yes | Yes | Yes (hosted) |
| Auto-unseal (KMS, cloud) | Yes | Yes | Yes |
| Audit devices | Yes | Yes | Yes |
| Namespaces (multi-tenancy) | No | Yes | Yes |
| Replication | No | Yes | Yes |
| Performance (standalone, secondary, batch) | No | Yes | Yes |
| Sentinel policy-as-code | No | Yes | No |
| HSM / FIPS boundary support | Community only | Yes | n/a |
| Support contract | Community | Yes | Yes |
| Runs in an air-gapped environment | Yes | Yes | **No** |

Decision: **Vault Community (self-hosted)**, because the platform is air-gapped and HCP Vault is a hosted service.

Two consequences to accept explicitly:

1. **Namespaces are not available.** Multi-tenancy is provided by separate Vault deployments or by strict policy path separation, not by namespaces. Since Vault already runs outside the cluster on dedicated hosts (ADR-0016), running one Vault instance per trust boundary (platform, AI) is the natural way to get isolation without the Enterprise feature.
2. **Replication is not available.** The disaster-recovery copy is a raft snapshot to object storage plus an offline escrow of the unseal material, not a live secondary cluster. The DR procedure in `secrets-management/recovery/restore.md` is written for exactly that.

Move to Vault Enterprise if the organisation needs namespaces, live replication, Sentinel, or a support SLA. The deployment model does not change: the same host topology, the same Raft storage, the same unseal procedure. Only the binary, the license file, and the feature set change.

## Licensing — what to verify and with whom

| Fact | Verified | Source |
|---|---|---|
| HashiCorp changed from MPL 2.0 to BSL 1.1 on 2023-08-10 | Yes | `https://www.hashicorp.com/en/blog/hashicorp-adopts-business-source-license` |
| Vault 1.15.0 and later are BSL 1.1 | Yes | `https://github.com/hashicorp/vault/blob/main/LICENSE` |
| The licensor of record is IBM | Yes | Same LICENSE file: "The Licensed Work is (c) 2024 IBM Corp." |
| Internal production use is permitted | Yes | The Additional Use Grant permits production use that is not a "competitive offering"; "Hosting or using the Work for internal purposes within an organization is not considered a competitive offering" |
| Each version converts to MPL 2.0 four years after its first public distribution | Yes | Same LICENSE file: Change Date |
| HashiCorp's own guidance | The license FAQ is the reference for edge cases | `https://www.hashicorp.com/license-faq` |

What the organization must confirm with legal before adopting:

1. That the intended use is internal production use and not a competitive offering.
2. Whether any part of the platform is offered to third parties (for example a managed platform sold to customers) — that would be a competitive offering and would require a commercial license.
3. Whether the organization prefers to avoid BUSL for policy reasons, in which case OpenBao is the fallback.
4. The commercial cost of Vault Enterprise if the Enterprise features are required.

Record the legal decision and its date in `compatibility/version-matrix.md` next to the Vault row, and in the ADR.

### Why the design is not hostage to the license

Every Vault-dependent component is designed to be portable to OpenBao:

| Component | Vault-specific | Portable |
|---|---|---|
| Deployment (3 hosts, Raft, TLS, offline unseal) | No | Yes |
| Policies and roles (path-based) | No | Yes |
| Kubernetes auth method | No | Yes |
| PKI engine layout (root offline, intermediate in Vault) | No | Yes |
| External Secrets Operator with a Vault provider | The provider is Vault-specific | The operator is vendor-neutral; a different provider is a values change |
| Vault Agent and injector | Vault-specific | OpenBao provides equivalent components |
| Backup (raft snapshot + unseal escrow) | No | Yes |

The only genuinely Vault-specific pieces are the Consul integration and any Vault Enterprise-only feature. Neither is used in the base design.

## Version baseline

| Item | Version | Status |
|---|---|---|
| Vault Community | v2.2.0 | VERIFIED, `https://github.com/hashicorp/vault/releases/tag/v2.2.0` |
| Vault Helm chart | 0.34.1 (app 2.0.4) | VERIFIED, `https://helm.releases.hashicorp.com/index.yaml` |
| vault-k8s (injector, agent) | v1.7.6 | VERIFIED, `https://github.com/hashicorp/vault-k8s/releases` |
| OpenBao (fallback) | v2.7.1 | VERIFIED, `https://github.com/openbao/openbao/releases` |

The Helm chart is the pin, not the binary: the chart's `appVersion` defines the Vault binary version that is deployed. Confirm the two match before an upgrade.

## What the platform uses Vault for

| Use | Engine / method | Notes |
|---|---|---|
| Linux and SSH credentials | KV + SSH secrets engine | Short-lived, retrieved by Ansible at execution time |
| Application secrets | KV, via External Secrets Operator or the injector | Never in Git |
| Database credentials | Database secrets engine | Dynamic, 24h lease, renewable |
| Internal PKI (root offline, intermediate online) | PKI secrets engine | cert-manager consumes the intermediate |
| Kubernetes service identity | Kubernetes auth method | Short-lived projected service account tokens |
| CI authentication | JWT auth (GitLab OIDC) or AppRole | JWT preferred; AppRole is the fallback |
| Human access | OIDC via Keycloak | Group to policy mapping |
| Backup encryption keys | Transit secrets engine | Or a KMS outside the cluster |

## Operational rules for HashiCorp Vault

1. Vault runs on dedicated hosts outside every Kubernetes cluster (ADR-0016, ADR-0025).
2. Unseal material is held offline, split across custodians, and tested quarterly.
3. The root token is never used for routine access. It lives in offline escrow.
4. Policies are path-scoped per application and per namespace. A policy that can read `secret/apps/*` defeats namespace isolation.
5. Every use of the break-glass path is reviewed.
6. Audit devices are enabled and shipped off-host. Audit logs never contain secret values.
7. A raft snapshot is taken daily and verified; the unseal escrow is backed up separately.
8. Vault availability is monitored, and an alert fires on seal status, leader, replication health, lease expiry, and certificate expiry.

## Deprecation and replacement plan

| Trigger | Action |
|---|---|
| Legal rejects BUSL | Migrate to OpenBao. The deployment topology, policies, and runbooks carry over. Plan as a rebuild, not a binary swap: the data formats are compatible, but the unseal procedure and the audit device configuration must be re-verified |
| A critical CVE in Vault | Upgrade to the patched version. Vault's upgrade path is in-place; the raft snapshot is taken first |
| Vault Community lacks a required Enterprise feature | Buy Vault Enterprise. Same deployment, license file added, features enabled |
| HCP Vault becomes acceptable (network access restored) | Re-evaluate. In an air-gapped site this is not applicable |
| The platform moves to a different secrets model entirely | Re-evaluate the whole ADR-0016 decision. The external integration points (External Secrets Operator, the injector, the Ansible lookup) are the parts that must be replaced |

## Quick checklist for the adoption decision

- [ ] Legal has reviewed BSL 1.1 and confirmed internal use is permitted, and has recorded the decision and the date.
- [ ] The organization's requirement for Enterprise features (namespaces, replication, Sentinel, support) is confirmed.
- [ ] The offline install path for the pinned version is mirrored and pull-verified.
- [ ] The unseal procedure is written, tested, and the custodians are named.
- [ ] The audit device is configured and its log is shipped off-host.
- [ ] The snapshot and restore procedure has been executed at least once, with the measured RTO recorded.
- [ ] The OpenBao fallback is documented in `secrets-management/vault/vault-architecture.md` with the list of Vault-specific components.
