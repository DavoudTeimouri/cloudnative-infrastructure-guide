# Kubernetes secret delivery

Four methods are supported. Each is used for a different case, and each has a different persistence and access profile.

## Comparison

| Method | Mechanism | Persisted in etcd | Refresh | App reload | Complexity | Use when |
|---|---|---|---|---|---|---|
| Vault Agent Injector | Sidecar writes a file, syncs on renewal | No (file only) | Agent renews and rewrites | App re-reads the file | Med | The app reads a file |
| Vault Agent templates | Agent renders a template to a file | No | Same | Same | Med | Config templating from many secrets |
| Secrets Store CSI Driver | Mounts a secret as a read-only file | No | Driver refreshes the mount | App re-reads | Med | The app wants a volume mount |
| External Secrets Operator | Syncs Vault into a K8s Secret | **Yes** | ESO refreshes on interval | App restart/reload | Low | The app needs a native K8s Secret |
| Direct app -> Vault | App calls the Vault API | No | App handles it | App-native | Varies | The app already integrates |
| K8s native Secret | Plain etcd secret | **Yes** | Manual | Yes | Low | Non-sensitive data only |

Explicit statement: **External Secrets Operator does not remove the etcd exposure.** It centralizes the source of truth and the rotation, but the synchronized value still lands in etcd and is readable by anyone with RBAC on that Secret in that namespace. The mitigation is namespace isolation, RBAC, and etcd encryption at rest — not the operator itself.

## Method 1 — Vault Agent Injector

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: app
spec:
  template:
    spec:
      serviceAccountName: app-vault-auth
      containers:
        - name: app
          image: harbor.internal/apps/app@sha256:...
          env:
            - name: VAULT_ADDR
              value: http://vault.vault.svc:8200
          volumeMounts:
            - name: secrets
              mountPath: /var/run/secrets/vault
      annotations:
        vault.hashicorp.com/agent-inject: "true"
        vault.hashicorp.com/agent-inject-secret-app-db: "app-db"
        vault.hashicorp.com/agent-inject-template-app-db: |
          {{- with secret "secret/apps/app/db" -}}
          DB_PASSWORD={{ .Data.data.password }}
          {{- end }}
        vault.hashicorp.com/role: "app"
        vault.hashicorp.com/auth-path: "kubernetes"
        vault.hashicorp.com/service-account: "app-vault-auth"
```

The pod runs as the app's service account, so the injector uses that token for the Vault Kubernetes auth. The Vault role bound to the service account determines what the pod can read.

Refresh: the agent renews the lease and rewrites the file. The application must re-read the file. Applications that read the file once at startup will use the old value until restarted. This is the single most common cause of "rotation did not work".

## Method 2 — External Secrets Operator

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ClusterSecretStore
metadata:
  name: vault-backend
spec:
  provider:
    vault:
      server: "https://vault.internal:8200"
      path: "secret"
      version: "v2"
      caProvider:
        type: ConfigMap
        name: vault-ca
        key: ca.crt
        namespace: external-secrets
      auth:
        kubernetes:
          mountPath: kubernetes
          role: external-secrets
          serviceAccountRef:
            name: external-secrets-vault
            namespace: external-secrets
```

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: app-db
  namespace: payments
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: vault-backend
    kind: ClusterSecretStore
  target:
    name: app-db
    creationPolicy: Owner
    template:
      type: Opaque
      data:
        password: "{{ .password }}"
  data:
    - secretKey: password
      remoteRef:
        key: apps/payments/db
        property: password
```

Refresh: `refreshInterval` controls how often ESO re-reads Vault. The change reaches the K8s Secret within that interval, but the application still needs to reload.

Rotation test: change the value in Vault, wait for `refreshInterval`, then confirm the K8s Secret changed and the application picked it up. If the application does not reload, use a `reloader`-style sidecar or a rolling restart triggered by the secret's `resourceVersion` hash in the pod spec.

## Method 3 — Secrets Store CSI Driver

```yaml
apiVersion: secrets-store.csi.x-k8s.io/v1
kind: SecretProviderClass
metadata:
  name: vault-provider
  namespace: payments
spec:
  provider: vault
  parameters:
    vaultAddress: "https://vault.internal:8200"
    roleName: "app"
    objects: |
      - objectName: "db-password"
        secretPath: "secret/apps/payments/db"
        secretKey: "password"
```

```yaml
volumes:
  - name: secrets
    csi:
      driver: secrets-store.csi.k8s.io
      readOnly: true
      volumeAttributes:
        secretProviderClass: vault-provider
```

The value is mounted as a file and is not stored in etcd. The driver refreshes the mount on the lease renewal interval.

## Method 4 — Direct application access

```python
# Example: the app authenticates to Vault itself
import hvac

client = hvac.Client(url=os.environ["VAULT_ADDR"])
client.auth.kubernetes.login(role="app", jwt=open("/var/run/secrets/kubernetes.io/serviceaccount/token").read())
secret = client.secrets.kv.v2.read_secret_version(path="secret/apps/payments/db", mount_point="secret")
password = secret["data"]["data"]["password"]
```

Use this when the application already has a Vault SDK integration. It gives the finest control over renewal and caching, at the cost of application work.

## Kubernetes auth in Vault

```bash
# Enable the method
vault auth enable kubernetes

vault write auth/kubernetes/config \
  kubernetes_host="https://kubernetes.default.svc:6443" \
  kubernetes_ca_cert=@ca.crt \
  token_reviewer_jwt=@reviewer.jwt \
  issuer="https://kubernetes.default.svc.cluster.local"
```

The token reviewer JWT must be a long-lived ServiceAccount token in the Vault namespace, with `system:auth-delegator` bound. The issuer must match the token's issuer claim.

```bash
# Role binding
vault write auth/kubernetes/role/app \
  bound_service_account_names=app-vault-auth \
  bound_service_account_namespaces=payments \
  policies=app-payments \
  ttl=1h
```

```bash
# Policy
vault policy write app-payments - <<EOF
path "secret/apps/payments/*" {
  capabilities = ["read"]
}
EOF
```

Scope policies to the namespace. A role that can read `secret/apps/*` from any namespace defeats the namespace isolation the External Secrets Operator created.

## etcd encryption at rest

Because some delivery methods persist into etcd, enable encryption at rest:

```bash
# On every control-plane node, in /etc/kubernetes/encryption-config.yaml
apiVersion: apiserver.config.k8s.io/v1
kind: EncryptionConfiguration
resources:
  - resources:
      - secrets
    providers:
      - aescbc:
          keys:
            - name: key1
              secret: <base64 32-byte key>
      - identity: {}
```

Then in the Kubespray group vars:

```yaml
encryption_provider: aescbc
```

The key must come from Vault, not from a file in the repository. In this platform the key is written to the node by Ansible from a Vault lookup during cluster deployment, and backed up in the Vault snapshot set.

## Choosing per component

| Component | Method | Reason |
|---|---|---|
| Application runtime secrets | External Secrets Operator | Applications expect native K8s Secrets; lowest application effort |
| Application config files | Vault Agent Injector | File-based, no etcd persistence |
| Database credentials | Vault DB engine + External Secrets or Agent | Dynamic credentials with a lease |
| Argo CD repository credentials | Argo CD repo secret, value from ESO | Argo CD reads its own secret |
| CI/CD credentials | GitLab protected variables or Vault OIDC | Not a Kubernetes concern |
| TLS certificates | cert-manager + Vault PKI | Renewal is the requirement |
| Ansible credentials | Vault lookup at execution time | Never in the inventory |
| Node-level secrets | Ansible from Vault | Written to disk with 0600 |

## Rotation verification

Rotation is only complete when the consumer has the new value. Test it:

```bash
# 1. Change the value in Vault
vault kv put secret/apps/payments/db password=NEWVALUE

# 2. Wait for the refresh interval, then check the K8s Secret
kubectl -n payments get secret app-db -o jsonpath='{.data.password}' | base64 -d

# 3. Confirm the application observed it
kubectl -n payments logs deploy/app --tail=20
```

A secret that changed in Vault but not in the application is a failed rotation, and the credential is now in two places with an unknown value.
