# Management plane: Rancher and its alternatives

Rancher is the default management plane in this platform: it registers clusters, projects and users,
and it is the one place an operator sees every cluster. It is not the only option, and it is not
required for a cluster to work. This document states when each alternative is the right answer.

## The comparison

| Option | What it is | Strength | Cost |
|---|---|---|---|
| **Rancher** | Cluster manager + UI + auth proxy + Fleet GitOps | One console for many clusters, mature RBAC, works with the existing Keycloak | A control plane of its own, a large API surface, its own upgrade cadence |
| **Headlamp + Argo CD** | CNCF UI for one cluster + GitOps | Small, no cluster registry, RBAC stays in Kubernetes | No multi-cluster console; each cluster is opened separately |
| **KubeSphere** | Full platform UI with multi-cluster | Integrated observability and DevOps UI | Heavy, opinionated, duplicates Prometheus/Argo CD |
| **No UI (kubectl + Argo CD)** | CLI and Git only | Least to operate, least to secure | Every read is a command; no shared console for an audit view |

## When to choose what

- **Rancher** — more than three clusters, a platform team, and a requirement for one console with
  per-user cluster access. The default in the configurator.
- **Headlamp + Argo CD** — one or two clusters, a small team, and a policy that the UI must not hold
  the only copy of cluster state. The configurator option `headlamp` renders this.
- **KubeSphere** — already standardized on it, or a requirement for a built-in DevOps console.
- **No UI** — a regulated environment where the console itself is an attack surface. Helm and Argo CD
  still work.

## What does not change

The management cluster is separate from the application clusters in every option. Identity stays at
the application layer (ADR-0015): Rancher, Headlamp and Argo CD all federate with Keycloak; no Linux
node joins the directory. The management cluster still runs Keycloak, Harbor, GitLab, Argo CD and
Vault, whichever UI is chosen.

## Headlamp deployment shape

Headlamp runs as a Deployment in the management cluster with a ServiceAccount and a
`ClusterRoleBinding` to `cluster-admin` only if the deployment is single-tenant. For multi-user use,
run it with OIDC and let each user bring their own token:

```yaml
config:
  oidc:
    clientID: headlamp
    issuerURL: {{value.keycloakHost}}/realms/platform
    scopes: "openid profile email groups"
  inCluster: false
serviceAccount:
  create: false
```

Generated as `headlamp-values.yaml` when the option is selected. It is a UI, not a control plane: if
it is down, `kubectl` and Argo CD continue.

## Migration between options

Rancher → Headlamp: register nothing; install Headlamp in the management cluster, keep Argo CD, and
remove Rancher only after every user has a kubeconfig path that does not go through Rancher. The
Rancher-generated kubeconfig embeds a proxy URL; once Rancher is gone, that file stops working.

Rancher → none: keep the clusters registered in Argo CD, hand out OIDC kubeconfigs, and document the
`kubectl` path as the primary interface. This is the lowest-dependency end state.
