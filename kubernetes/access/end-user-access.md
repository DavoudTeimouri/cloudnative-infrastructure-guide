# End-user cluster access

How a developer or operator connects to the cluster from their own machine, on Linux or Windows.
This is the hand-over document: the platform team produces one kubeconfig per user or per group,
the user installs two tools and runs one command.

## What the user needs

| Tool | Why | Linux | Windows |
|---|---|---|---|
| `kubectl` | The API client | Package or a single binary from `dl.k8s.io` | `winget install -e --id Kubernetes.kubectl`, or the binary |
| `kubelogin` | OIDC token refresh (`exec` plugin in the kubeconfig) | `kubelogin` from the Azure/kubelogin releases | `winget install -e --id Azure.kubelogin` |
| `helm` (optional) | Only if the user deploys charts | Package or binary | `winget install -e --id Helm.Helm` |

Do not hand a user a kubeconfig that embeds a client certificate with cluster-admin rights. The
platform issues short-lived OIDC tokens; the kubeconfig only names the issuer and the client id.

## Linux

```bash
# kubectl, pinned to the cluster minor version
curl -fsSLO "https://dl.k8s.io/release/{{version.kubernetes}}/bin/linux/amd64/kubectl"
install -m 0755 kubectl ~/.local/bin/kubectl

# kubeconfig from the platform team, then merge, never overwrite
mkdir -p ~/.kube
cp ~/Downloads/{{value.clusterName}}-{{value.env}}.yaml ~/.kube/config.d/{{value.clusterName}}.yaml
chmod 600 ~/.kube/config.d/{{value.clusterName}}.yaml
export KUBECONFIG="$HOME/.kube/config:$HOME/.kube/config.d/{{value.clusterName}}.yaml"

kubectl config use-context {{value.clusterName}}
kubectl auth whoami
kubectl get nodes
```

If `KUBECONFIG` is set, `kubectl config view` shows the merged result. Merging is additive; copying
a new file over `~/.kube/config` deletes every other cluster the user had.

## Windows (PowerShell)

```powershell
winget install -e --id Kubernetes.kubectl
winget install -e --id Azure.kubelogin

# kubeconfig
$dir = "$env:USERPROFILE\.kube"
New-Item -ItemType Directory -Force -Path "$dir\config.d" | Out-Null
Copy-Item "$env:USERPROFILE\Downloads\{{value.clusterName}}-{{value.env}}.yaml" "$dir\config.d\{{value.clusterName}}.yaml"
$env:KUBECONFIG = "$dir\config;$dir\config.d\{{value.clusterName}}.yaml"

kubectl config use-context {{value.clusterName}}
kubectl auth whoami
```

`kubelogin` must be on `PATH`. If the kubeconfig's `exec` command is `kubelogin` and PowerShell cannot
find it, the error is `executable kubelogin not found` — reopen the terminal after `winget install`,
then check `Get-Command kubelogin`.

## OIDC login

The kubeconfig contains an `exec` block, not a token:

```yaml
users:
  - name: {{value.clusterName}}-oidc
    user:
      exec:
        apiVersion: client.authentication.k8s.io/v1
        command: kubelogin
        args: ["get-token", "--login", "devicecode", "--issuer-url", "{{value.keycloakHost}}/realms/platform", "--client-id", "kubectl", "--scopes", "openid,groups"]
```

The first command opens a browser and a device code. The token is cached under
`~/.kube/cache/oidc-login/`; it is refreshed silently until the refresh token expires. A revoked
user fails at the next refresh, not at the next command — that is the delay to explain to the user.

## Service account token, when a human is not in the loop

For CI and automation, do not copy a kubeconfig with a user's identity. Create a service account and
request a short-lived token:

```bash
kubectl -n {{value.appNamespace}} create serviceaccount ci-deploy
kubectl -n {{value.appNamespace}} create rolebinding ci-deploy \
  --clusterrole=edit --serviceaccount={{value.appNamespace}}:ci-deploy

# Short-lived token (1 hour), returned as JSON, never stored in Git
kubectl -n {{value.appNamespace}} create token ci-deploy --duration=1h
```

The token is a bearer credential. Put it in the CI secret store, never in a repository, never in a
shell history. For a long-lived integration, create a `Secret` of type
`kubernetes.io/service-account-token` only when the platform explicitly allows it — bound tokens are
the default for a reason.

## Export and import a token

```bash
# Export on the machine that has cluster-admin
kubectl -n {{value.appNamespace}} create token ci-deploy --duration=24h > /tmp/ci-token.json
scp /tmp/ci-token.json user@workstation:~/ci-token.json
shred -u /tmp/ci-token.json

# Import on the workstation
TOKEN=$(python3 -c 'import json,sys;print(json.load(open("ci-token.json"))["status"]["token"])')
kubectl --server="https://{{value.apiServerIp}}:6443" \
  --certificate-authority="$HOME/.kube/ca.crt" \
  --token="$TOKEN" get nodes
```

`--certificate-authority` needs the cluster CA. Export it from the admin machine:
`kubectl config view --raw -o jsonpath='{.clusters[0].cluster.certificate-authority-data}' | base64 -d > ca.crt`.

## Verify and troubleshoot

| Symptom | Cause | Fix |
|---|---|---|
| `x509: certificate signed by unknown authority` | The internal CA is not in the kubeconfig or the OS trust store | Use `certificate-authority-data` in the kubeconfig; install the CA in the OS store |
| `Unauthorized` | Token expired or the user was removed from the group | Re-run the login; check the group claim in Keycloak |
| `executable kubelogin not found` | Plugin not on `PATH` | Install it, reopen the terminal, `Get-Command kubelogin` |
| `connection refused` on the API VIP | The user is outside `adminCidr` or the edge does not forward 6443 | Check the network matrix; use the VPN |
| `Forbidden` on one namespace | RBAC, not authentication | `kubectl auth can-i --list -n <namespace>` |

The generated `user-access.md` fills this document with the plan's cluster name, API address and
issuer URL. The repository remains the authority for the procedure.
