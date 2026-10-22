# L7 ingress — F5 NGINX Ingress Controller and Gateway API

**Check date: 2026-10-17.**

## Why this is not the ingress-nginx you may know

The community project `kubernetes/ingress-nginx` was retired in March 2026. SIG Network and the Security Response Committee announced the retirement on 2025-11-11, and the Kubernetes Steering Committee followed with a statement on 2026-01-29. After the retirement there are no further releases, no bug fixes, and no security updates; the repositories are read-only and remain available for reference. Existing deployments keep running and the artifacts remain available, but a new deployment on that controller starts with no security support.

The replacement in this platform is F5's **NGINX Ingress Controller** (`nginx/kubernetes-ingress`). It is a different project from the retired one: same NGINX dataplane, different codebase, different maintainer (F5), different chart, different admission model.

Verified compatibility (F5 technical specifications, check date 2026-10-17):

| NIC version | Kubernetes tested | Helm chart | Operator | NGINX / NGINX Plus |
|---|---|---|---|---|
| 5.7.0 | 1.30 - 1.37 | 2.8.0 | 3.8.0 | 1.31.7 / R37.2.0.1 |
| 5.6.3 | 1.30 - 1.37 | 2.7.3 | 3.7.3 | 1.31.6 / R37.1.1.2 |
| 5.5.4 | 1.29 - 1.36 | 2.6.4 | 3.6.5 | 1.31.3 / R37.0.3.1 |

F5 supports the most recent release, and provides support to customers for any version released within two years of the current release.

F5's other product, **NGINX Gateway Fabric**, is the Gateway API-native path: version 2.8.0 is conformant with Gateway API 1.6.3 and requires Kubernetes 1.32+. It is the vendor's forward direction, and the platform moves to it when Gateway API is the only API in use across the estate (ADR-0007).

## Architecture

```
  external client
        |
  DMZ load balancer (keepalived/HAProxy) --VIP--> nginx-ingress service
        |                                                   |
  TLS termination at the controller                      MetalLB VIP
        |
  HTTPRoute / Ingress -> Service -> pods
```

Two exposure models:

| Model | Description | Use |
|---|---|---|
| Inside the cluster | The controller's Service is `type: LoadBalancer`; MetalLB assigns a VIP | The cluster edge is behind the site load balancer |
| Outside the cluster | The controller runs in hostNetwork or with a static `loadBalancerIP` and the site load balancer forwards to it | Where the site load balancer owns the VIP and health checks |

Pick one per cluster and document it. Running both means two ingress paths and two sets of certificates.

## Installation

```bash
helm repo add nginx-ingress https://nginx.github.io/helm-charts
helm repo update
helm install nic nginx-ingress/nginx-ingress \
  --version 2.8.0 \
  --namespace ingress-nginx --create-namespace \
  --set controller.image.repository=harbor.internal/platform/nginx-ingress/controller \
  --set controller.admissionWebhooks.enabled=true \
  --set controller.admissionWebhooks.patch.image.repository=harbor.internal/platform/nginx-ingress/admission-webhook \
  --set controller.admissionWebhooks.patch.image.digest="" \
  --set controller.service.type=LoadBalancer \
  --set controller.config.ingress-class=nginx \
  --set controller.metrics.enabled=true \
  --set controller.metrics.serviceMonitor.enabled=true
```

Offline: the chart and all three images (controller, admission webhook, and any sidecar) must be mirrored into the internal registry. The chart pulls the image repository from values, so the internal path is set explicitly rather than relying on a mirror.

### Gateway API

Gateway API CRDs are client-side and versioned separately from the controller:

```bash
kubectl apply -f https://github.com/kubernetes-sigs/gateway-api/releases/download/v1.6.3/standard-install.yaml
```

Install the `standard` channel, not `experimental`, unless a specific experimental feature is required. The experimental channel installs CRDs with a shorter support commitment.

The controller needs to be told to watch Gateway API resources:

```yaml
controller:
  config:
    enable-gateway-api: "true"
    gateway-class: nginx
```

## Configuration model hardening

The retired project was explicitly criticised for the `snippets` annotation, which allowed arbitrary NGINX directives to be injected through an Ingress annotation — a direct configuration-injection path. The replacement must not reintroduce that surface.

Mandatory:
- `snippets` annotation support disabled. Confirm the controller version's default and pin the value explicitly.
- `server-snippet`, `stream-snippet`, and `lua-shared-dicts` disabled unless a documented, reviewed use case exists.
- The admission webhook validates and mutates Ingress, HTTPRoute, and VirtualServer resources. Its failure policy must be `Fail` for application namespaces.
- The controller runs as a non-root user with a read-only root filesystem where the version supports it.
- The controller's ConfigMap is owned by the platform team. Application teams do not edit it.

```yaml
controller:
  config:
    enable-snippets: "false"
    enable-server-snippets: "false"
    enable-stream-snippets: "false"
    allow-snippet-annotations: "false"
```

Confirm the exact key names for the pinned version before relying on them.

## TLS

```yaml
# cert-manager + Vault PKI issuer
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: internal-ca
spec:
  ca:
    secretName: internal-ca-key-pair
```

The CA key pair comes from Vault PKI via External Secrets, so it is never in Git. The controller serves the certificate from a Secret in its namespace or from a `Secret` in the application namespace, depending on the mode.

## Validation

```bash
kubectl -n ingress-nginx get pods
kubectl -n ingress-nginx get svc
kubectl get gatewayclass
kubectl get gateway,httproute -A

# From outside
curl -vk https://<ingress-vip>/ -H 'Host: app.internal'

# Certificate
openssl s_client -connect <ingress-vip>:443 -servername app.internal </dev/null
```

Expected: the controller pods are Ready, the Service has a VIP, and the certificate chain validates against the internal CA.

## Migration from the retired ingress-nginx

For an estate that already runs the retired controller:

1. Inventory: `kubectl get ingress -A` and list the annotations in use. The retired controller's annotation set is large; each one needs an equivalent or a deliberate decision to drop it.
2. Convert to Gateway API with the SIG Network tool:

```bash
ingress2gateway print --providers=nginx --input-file=ingress.yaml > gateway-api-resources.yaml
```

The tool is a conversion utility, not an end-to-end migration. Review every converted resource and test it. It covers the common annotations, not all of them.
3. Run the new controller alongside the old one on a different address, as the Gateway API migration guide recommends, and validate before switching traffic.
4. Switch the DNS record or the load balancer target.
5. Remove the old controller only after the new one has served production traffic for a full business cycle.

The Kubernetes project published a specific warning about this migration: "a seemingly correct translation can still cause outages if it does not consider Ingress-NGINX's quirks." The five surprising behaviours are described in `https://kubernetes.io/blog/2026/02/27/ingress-nginx-before-you-migrate/`. Read that document before converting anything.

## Known traps

1. **The two projects share a name and nothing else.** `kubernetes/ingress-nginx` (retired) and `nginx/kubernetes-ingress` (F5, active) have different chart names (`ingress-nginx` vs `nginx-ingress`), different namespaces, different admission webhooks, and different image paths. A copy-paste from an old playbook will install the retired one.
2. **The admission webhook is a cluster-wide dependency.** If it is unavailable and its failure policy is `Fail`, every Ingress mutation is blocked. Confirm the failure policy per namespace group.
3. **Gateway API CRDs are a separate upgrade.** Updating the controller does not update the CRDs. A controller that expects a newer CRD version fails at reconciliation.
4. **`enable-snippets` defaults change between versions.** Pin it explicitly; do not rely on the default.
5. **The NGINX Plus variants are a different product.** The OSS build is what this platform uses. NGINX Plus features (JWT, WAF, active health checks) are licensed and not available in the OSS image.
6. **Retiring the old controller changes the certificate story.** If the old controller managed certificates through cert-manager in a shared namespace, the migration must move that ownership.

## Best practices

Mandatory:
- The F5 controller (`nginx/kubernetes-ingress`), never the retired community project. Verify the chart source before every install.
- `snippets` and the related annotation-driven configuration surfaces disabled.
- The admission webhook with `failurePolicy: Fail` for application namespaces, `Ignore` for the platform's own namespaces.
- Certificates from cert-manager with the CA in Vault.
- The controller pinned to an exact chart version, with the image digest pinned in the offline registry.

Strongly recommended:
- Gateway API for all new applications, Ingress only for what still needs it.
- A dedicated `ingress-nginx` namespace owned by the platform team; application namespaces only get `IngressClass` and policy.
- The controller's Service as `type: LoadBalancer` with a static `loadBalancerIP` from the MetalLB pool for the platform endpoints (Rancher, Argo CD, Keycloak, Grafana).
- Prometheus scraping of the controller's metrics endpoint, with an alert on the admission webhook's rejection rate.
- A migration plan toward NGINX Gateway Fabric written down before the Gateway API migration starts.
