# Argo CD GitOps

## A. Purpose and architecture

Argo CD reconciles Kubernetes state against Git. It is the single writer for every Kubernetes-declared object except the Kubespray-managed ones (see ADR-0014).

```
GitLab repo ---> Argo CD repo-server ---> application-controller ---> K8s API
                      |                             |
                 ApplicationSet              Argo CD UI / API
```

## B. Installation

Managed by Argo CD itself (bootstrap is a one-time exception) and thereafter by Argo CD.

```bash
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
kubectl -n argocd rollout status deployment/argocd-server --timeout=300s
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath="{.data.password}" | base64 -d
```

HA configuration (Argo CD HA docs, pinned version):
- `argocd-server`, `argocd-repo-server`, `argocd-application-controller` with `replicas: 2`+
- Redis with a sentinel or a managed HA Redis
- PostgreSQL as the backend (never SQLite in production)
- A separate `argocd-application-controller` per cluster for large fleets, with sharding

## C. Project model

One `AppProject` per team:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: AppProject
metadata:
  name: team-payments
  namespace: argocd
spec:
  description: Payments team applications
  sourceRepos:
    - https://gitlab.internal/apps/payments
  destinations:
    - namespace: payments
      server: https://kubernetes.default.svc
  clusterResourceWhitelist:
    - group: ""
      kind: Namespace
  namespaceResourceWhitelist:
    - group: ""
      kind: ConfigMap
    - group: ""
      kind: Secret
    - group: apps
      kind: Deployment
    - group: ""
      kind: Service
    - group: networking.k8s.io
      kind: Ingress
  namespaceResourceBlacklist:
    - group: ""
      kind: Pod
    - group: rbac.authorization.k8s.io
      kind: ClusterRole
    - group: rbac.authorization.k8s.io
      kind: ClusterRoleBinding
```

Restricting destinations prevents a team from deploying into the platform namespaces.

## D. Application and ApplicationSet

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: payments-api
  namespace: argocd
  finalizers:
    - resources-finalizer.argocd.argoproj.io
spec:
  project: team-payments
  source:
    repoURL: https://gitlab.internal/apps/payments
    targetRevision: main
    path: k8s/api
    helm:
      valueFiles: [values-production.yaml]
  destination:
    server: https://kubernetes.default.svc
    namespace: payments
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
      - ServerSideApply=true
    retry:
      limit: 5
      backoff: {duration: 15s, factor: 2, maxDuration: 5m}
```

`ServerSideApply=true` matters at scale: client-side apply has a size limit and loses field ownership for some types.

ApplicationSet for a fleet of identical services:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: microservices
  namespace: argocd
spec:
  generators:
    - list:
        elements:
          - service: payments
            tier: gold
          - service: ledger
            tier: gold
          - service: notify
            tier: silver
  template:
    metadata:
      name: '{{service}}'
    spec:
      project: team-payments
      source:
        repoURL: https://gitlab.internal/apps/payments
        targetRevision: main
        path: 'k8s/{{service}}'
      destination:
        server: https://kubernetes.default.svc
        namespace: '{{service}}'
      syncPolicy:
        automated: {prune: true, selfHeal: true}
```

Git generator variant for a directory-of-services layout:

```yaml
  generators:
    - git:
        repoURL: https://gitlab.internal/apps/payments
        revision: main
        directories:
          - path: k8s/*
```

## E. Offline configuration

| Need | Configuration |
|---|---|
| Internal GitLab | `repoURL` points at the internal GitLab |
| Internal image registry | `image` rewrite rule in `argocd-cm`, or the images are already named with the internal registry in Git |
| Internal Helm chart repo | `helm.repoURL` points at the internal OCI registry in Harbor |
| Repository credentials | Argo CD repository secret in the `argocd` namespace, value from Vault via External Secrets |
| TLS trust for the internal CA | Mounted into the repo-server pods (see below) |

Image rewrite rule (`argocd-cm`):

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: argocd-cm
  namespace: argocd
data:
  application.resourceTrackingMethod: annotation
  application.instanceLabelKey: argocd.argoproj.io/instance
  resource.customizations.health.lua: |
    hs = {}
    if obj.status ~= nil then
      if obj.status.phase == "Running" then hs.status = "Healthy"
      ...
    end
    hs = {status = "Progressing", message = "Waiting"}
    return hs
  # Rewrite upstream image names to the internal registry
  # (implemented via a config-management-plugin or a sidecar in this platform)
```

The standard way to rewrite images is a Config Management Plugin running as an Argo CD sidecar. It is a small plugin image that the repo-server executes. Because the offline environment cannot fetch the upstream image at deploy time, the plugin (or the Git repo itself) must reference the internal registry. The simplest and most auditable approach: the Git repo already contains the internal registry path, produced by the CI pipeline at build time. The plugin approach is used when the same Git repo must serve both connected and offline environments.

TLS trust for the internal CA in Argo CD:

```yaml
# In the repo-server Deployment
volumeMounts:
  - name: ca
    mountPath: /etc/ssl/certs/ca-certificates.crt
    subPath: ca-certificates.crt
volumes:
  - name: ca
    configMap:
      name: argocd-ca
      items:
        - key: ca-certificates.crt
          path: ca-certificates.crt
```

## F. OIDC / SSO

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: argocd-cm
  namespace: argocd
data:
  oidc.config: |
    name: Keycloak
    issuer: https://keycloak.internal/realms/platform
    clientID: argocd
    clientSecret: $oidc-keycloak:oidc.clientSecret
    requestedScopes: openid,profile,email,groups
    groupMappingEnabled: "true"
    groupsClaim: groups
    # Map Keycloak groups to Argo CD roles
    groupMapping:
      "platform-admins": role:admin
      "platform-operators": role:admin
      "developers": role:readonly
    scopes: |
      - group:platform-admins
      - group:platform-operators
```

The `clientSecret` is referenced as a Vault secret, not inline. Argo CD resolves `$namespace:key` references against secrets in the Argo CD namespace.

Argo CD's built-in RBAC is coarse (admin, edit, readonly). For per-project permissions, use the Argo CD RBAC ConfigMap with project-scoped policies, or the Keycloak group mapping above.

## G. Validation

```bash
# Application health
argocd app list
argocd app get payments-api
argocd app history payments-api

# Diff between Git and the cluster
argocd app diff payments-api

# Sync manually
argocd app sync payments-api

# From inside the cluster
kubectl -n argocd get applications
kubectl -n argocd describe application payments-api
```

Expected healthy state: `Sync Status: Synced`, `Health Status: Healthy`, no `OutOfSync` on a quiet system.

## H. Operations

| Task | Procedure |
|---|---|
| Promote a version | Merge to `main`; Argo CD syncs automatically |
| Roll back | `argocd app rollback <app> <history-id>` or revert the Git commit |
| Pause an app | `argocd app set <app> --sync-policy=none` — during an incident this prevents Argo CD from reverting a hotfix |
| Add a resource | Add it to Git; Argo CD adopts or creates it |
| Delete a resource | Remove it from Git; with `prune: true` Argo CD deletes it — confirm the resource is not stateful |
| Refresh a secret | `argocd app get <app> --refresh` |

## I. Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| `OutOfSync` with no diff | Resource modified outside Argo CD | With `selfHeal: true` it reverts; investigate the manual change |
| `ComparisonError` | Repo unreachable, or the CA is not trusted by the repo-server | Check repo-server logs and the CA mount |
| `Failed to load target state` | Wrong path, or the manifest is invalid | `argocd app get` shows the error |
| Sync fails with a webhook error | An admission controller is blocking the resource | See `troubleshooting/admission.md` |
| Image pull error after sync | The image name does not resolve internally | Rewrite rule or CI-side rewrite |
| Secret not populated | The ExternalSecret has not synced, or the Vault path is wrong | Check the ExternalSecret and the ClusterSecretStore |
| App stuck `Progressing` | A resource is healthy-checked as Progressing (a Deployment with a missing readiness probe) | Fix the health check in the app manifest |

## J. Best practices

Mandatory:
- `prune: true` and `selfHeal: true` for application workloads, and an explicit review for anything stateful.
- `AppProject` per team with a restricted destination and resource whitelist.
- `ServerSideApply=true` for large applications.
- Repository credentials from Vault via External Secrets, never in the Application manifest.
- Pin the Argo CD version and mirror the images.

Strongly recommended:
- The App-of-apps pattern: one root Application that creates the platform Applications, so the platform bootstraps itself.
- A sync window per project to avoid a fleet-wide sync at the same moment.
- Health checks customised per resource type in `argocd-cm`.
- Argo CD notifications for sync failures, wired to Alertmanager.
