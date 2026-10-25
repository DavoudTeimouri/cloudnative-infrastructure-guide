# 06. Management cluster

**Purpose:** Deploy the platform control plane — Rancher for cluster lifecycle, Argo CD for GitOps,
Keycloak for identity, Vault for secrets — in a dedicated management cluster that is separate from
application workloads.

## Prerequisites
- Step 05 complete: at least one Kubernetes cluster deployed and reachable via kubeconfig.
- Step 01 complete: break-glass and Vault unseal key stored offline.

## Steps

### 06.1 Deploy Rancher
Install Rancher into the management cluster (HA: 3 replicas + etcd). Configure the Rancher server URL,
TLS cert, and admin password (`[REDACTED]`).

Source: `management-cluster/rancher/rancher.md`

### 06.2 Deploy Argo CD
Install Argo CD as the GitOps engine. Connect it to your internal GitLab instance; sync app manifests
from `config/`.

Source: `management-cluster/argocd/argocd.md`

### 06.3 Deploy Keycloak (identity)
Install Keycloak in the management cluster, not joined to AD (ADR-0015). Create:
- Realm `platform`
- Clients: Rancher, Argo CD, Vault, Harbor, Nexus
- User federation: local users only; break-glass admin account offline

Identity is application-layer; hosts keep local accounts.

### 06.4 Deploy Vault
Install Vault (standalone Raft, 3 nodes) with an offline unseal key stored in the break-glass safe.
Configure auth methods (Kubernetes for workloads, OIDC via Keycloak for users) and secrets engines
(KV v2).

Source: `secrets-management/vault/` if present, else `management-platform/`

## Validation
- [ ] Rancher UI reachable via the edge VIP; admin login works.
- [ ] Argo CD UI reachable; at least one app syncs from internal GitLab.
- [ ] Keycloak issues tokens to Rancher and Argo CD.
- [ ] Vault is unsealed; `vault status` reports initialized/sealed=false.
- [ ] Management cluster has no application workloads (control plane only).

## Navigation
**[← Prev · 05. Kubernetes](./05-kubernetes.md)** | **[Next → 07. Application cluster](./07-application-cluster.md)**
