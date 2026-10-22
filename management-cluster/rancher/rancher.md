# Rancher management cluster

## A. Purpose and architecture

Rancher manages the lifecycle of the Application Clusters and provides the operator view of the estate.

```
  admin workstation
        |
   Rancher VIP (DMZ)
        |
  Management Cluster (3 control-plane + 3 infra workers)
    rancher server x3
    cattle-cluster-agent (runs in each managed cluster)
    fleet agent (in each managed cluster)
```

## B. Deployment model

Rancher runs on its own dedicated cluster, not on an Application Cluster. Rationale: ADR-0010 and ADR-0011. If Rancher shares a cluster with workloads, a workload failure domain becomes a management failure domain.

The Rancher cluster is built with Kubespray, like every other cluster, so it is reproducible from the same inventory and the same OS baseline.

## C. Installation

Rancher is installed with the official Helm chart, applied by Argo CD into the Management Cluster.

```yaml
# values.yaml
hostname: rancher.internal
replicas: 3
ingress:
  enabled: true
  ingressClassName: nginx
  tls:
    source: letsEncrypt
privateRegistry: harbor.internal
rancherImage: harbor.internal/platform/rancher/rancher
systemDefaultRegistry: harbor.internal
useBundledSystemChart: true
bootstrapPassword: ""            # from External Secrets, not inline
```

```bash
helm repo add rancher-stable https://releases.rancher.com/server-charts/stable
helm install rancher rancher-stable/rancher \
  --namespace cattle-system --create-namespace \
  --values values.yaml
```

Bootstrap password:

```bash
kubectl -n cattle-system get secret rancher-bootstrap-password -o jsonpath='{.data.password}' | base64 -d
```

The password is changed on first login and the bootstrap secret is then deleted. In GitOps, the value comes from Vault via External Secrets and the rendered Secret is never committed.

## D. Cluster registration

Two registration models:

| Model | How | Use |
|---|---|---|
| In-cluster registration | The agent is deployed inside the target cluster by Rancher | The target cluster is reachable from Rancher |
| Out-of-cluster registration | Rancher deploys the agent using kubeconfig | Firewalls prevent Rancher from reaching the target cluster's API |

```bash
# In the Application Cluster
kubectl -n cattle-system create secret generic cattle-cluster-agent \
  -n cattle-system --from-literal="token=<token>" --dry-run=client -o yaml | kubectl apply -f -

kubectl apply -f https://releases.rancher.com/rancher-agent/v2.15/rke2-k3s.yaml   # for RKE2
```

For a Kubespray-built (kubeadm) cluster, use the `rke2` agent manifest only if the cluster is RKE2. For kubeadm clusters, Rancher supports the "import existing" flow with the agent applied by hand:

```bash
kubectl apply -f https://releases.rancher.com/rancher-agent/v2.15/agent.yaml
```

The exact manifest path must be confirmed against the pinned Rancher release before use.

## E. Identity

Rancher is configured against Keycloak with OIDC.

```yaml
# Rancher global setting (via the UI or the API)
oidc:
  issuer: https://keycloak.internal/realms/platform
  clientId: rancher
  clientSecret: <from vault>
  redirectUri: https://rancher.internal/oidc/authorize?client_id=rancher&redirect_uri=https://rancher.internal/oidc/auth
  scope: "openid profile email groups"
  userSearchBase: "ou=users,dc=example,dc=com"
  groupSearchBase: "ou=groups,dc=example,dc=com"
  uidField: "uid"
  groupsField: "memberOf"
  idpCert: <CA cert>
```

Keycloak client requirements:
- A dedicated client `rancher` with `client credentials` off and standard flow on.
- The `groups` claim must be present in the ID token. Add a protocol mapper in Keycloak:
  - Mapper type: `Group membership`
  - Claim name: `groups`
  - Full path: off
  - Add to ID token: on
- The `uid` claim must be present. Add a mapper for `uid` if the user attribute is not the default.

Group-to-role mapping in Rancher:

| Keycloak group | Rancher role |
|---|---|
| `platform-admins` | `admin` |
| `platform-operators` | `admin` (limited to the platform project) |
| `app-developers` | `project-member` in the team projects |

## F. Fleet (GitOps for downstream clusters)

Fleet manages cluster registration and baseline add-ons through Git. It is complementary to Argo CD:

| | Fleet | Argo CD |
|---|---|---|
| Scope | Clusters and the add-ons every cluster must have | Applications and their configuration |
| Repository | `mgmt-rancher` project | Per-team application projects |
| Sync model | Bundle-based | Application/ApplicationSet |
| Used here for | cluster registration, CNI baseline, node metadata | Everything else |

Fleet bundle:

```yaml
apiVersion: fleet.cattle.io/v1alpha1
kind: GitRepo
metadata:
  name: platform-baseline
  namespace: fleet-default
spec:
  repo: https://gitlab.internal/platform/fleet-baseline.git
  branch: main
  paths:
    - bundle.yaml
```

```yaml
apiVersion: fleet.cattle.io/v1alpha1
kind: Bundle
metadata:
  name: platform-baseline
  namespace: fleet-default
spec:
  targets:
    - clusterSelector:
        matchLabels:
          env: production
```

Rule: Fleet and Argo CD must never both own the same object. The ownership table in `automation/gitlab-ci/gitlab-ansible-design.md` is normative.

## G. Validation

```bash
# Rancher is up
kubectl -n cattle-system get pods
curl -k https://rancher.internal/v3/health

# The managed cluster is registered and its nodes are visible
# Rancher UI: Cluster Management -> the cluster -> Nodes
```

From the Rancher API:

```bash
curl -sk -u "$RANCHER_TOKEN:$RANCHER_TOKEN" \
  https://rancher.internal/v3/clusters | jq '.data[] | {name, state}'
```

Expected: `state: "active"` and the node count matching the cluster.

## H. Operations

| Task | Procedure |
|---|---|
| Add a cluster | Create the cluster with Kubespray, then import it into Rancher with the registration token |
| Remove a cluster | Delete in Rancher, then decommission the nodes |
| Upgrade Rancher | Helm upgrade via Argo CD. Check the release notes for the CRD changes first |
| Rotate the Rancher TLS certificate | cert-manager re-issues; the Rancher pod picks up the new secret |
| Rotate the OIDC client secret | Update in Keycloak and in the Rancher global setting; the order matters — update Rancher first if it re-reads at request time, Keycloak second |

Failure behaviour: Rancher loss does not affect running workloads or Argo CD sync inside each cluster. It removes cluster registration and the UI.

## I. Best practices

Mandatory:
- Rancher on its own dedicated cluster.
- OIDC via Keycloak, with a dedicated client and the `groups` and `uid` claims verified before go-live.
- The bootstrap password never in Git; the secret deleted after first login.
- A local break-glass admin path documented (Rancher supports a local admin password in addition to OIDC — confirm the exact mechanism for the pinned release).

Strongly recommended:
- Rancher limited to the platform project for operators, so an operator cannot manage unrelated clusters.
- Project-scoped RBAC for each application team.
- Alert on Rancher availability, and on the Rancher operator's own reconciliation errors.
