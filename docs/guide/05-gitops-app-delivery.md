# Phase 5 — SRE Operations: GitOps and Application Delivery

## ArgoCD GitOps Installation

### Install
```bash
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
```

### HA Configuration
- Redis HA (3 replicas)
- argocd-server, repo-server, application-controller with `replicaCount: 2+`
- External PostgreSQL (not SQLite)

### Access
- LoadBalancer or Ingress with TLS
- `admin` password from secret `argocd-initial-admin-secret`
- OIDC/SSO via dex (Keycloak, Okta, Azure AD)

### GitOps Model
- `AppProject` per team, scoped to namespaces and source repos
- `Application` or `ApplicationSet` for microservice families
- Sync policy: automated + prune + self-heal
- Resource hooks and health checks per application

### Policy
- OPA Gatekeeper as admission webhook
- ArgoCD resource exclusions and ignore differences

### GitOps — Kubespray Version Contradictions
ArgoCD application sync properties vary with Kubespray versions:

| Kubespray Release | K8s Version | ArgoCD Sync Behavior | Issue |
|---|---|---|---|
| release-2.32 | v1.36.4 | Self-heal loops on privileged containers | OPA Gatekeeper policy update required |
| release-2.31 | v1.35.9 | Drift detection delayed > 5 min | Increase sync windows |
| release-2.30 | v1.34.12 | Resource retention on delete | Manual cleanup required |

### Recommended ArgoCD Configuration per Kubespray Version
- release-2.32 + v1.36.4: Set `healthCheck` timeout to 120s, enable `prune: true`
- release-2.31 + v1.35.9: Increase `interval` to 2m, set `healthCheck` timeout to 90s
- release-2.30 + v1.34.12: Enable `automated.prune: true`, monitor `resource.prune.errors`