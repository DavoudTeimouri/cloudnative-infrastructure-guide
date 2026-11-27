# Phase 2 — Management Layer

## Rancher Management Installation

### Install
Rancher on its own 3-node K8s cluster (RKE2/K3s HA) behind an L4 LB:

```bash
helm repo add rancher-stable https://releases.rancher.com/server-charts/stable
helm install rancher rancher-stable/rancher \
  --namespace cattle-system --create-namespace \
  --set hostname=rancher.example.com \
  --set ingress.tls.source=letsEncrypt \
  --set replicas=3
```

### Day-2 Operations
- Import existing clusters via cluster registration token
- Provision new clusters with RKE2 (Fleet manages downstream)
- Identity: LDAP/AD or OIDC (Keycloak/Okta/Azure AD)
- RBAC: project-based membership, PodSecurity Policies or PSP replacement
- Fleet: GitOps for downstream clusters alongside ArgoCD

### Relationship with ArgoCD
Rancher Fleet manages cluster provisioning and baseline add-ons. ArgoCD manages application lifecycle inside each cluster.

### Management Layer Verification
- Rancher server healthy and accessible via HTTPS
- Cluster registration token valid and usable
- Downstream clusters visible in Rancher UI
- Fleet sync running without errors