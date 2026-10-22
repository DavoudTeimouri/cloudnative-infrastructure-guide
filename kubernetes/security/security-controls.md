# Kubernetes security controls

## A. Purpose and scope

Layered controls for the cluster and the workloads on it: admission, runtime detection, image provenance, host baseline, network policy, and audit.

## B. Control layers

| Layer | Tool | Enforcement point | Failure mode |
|---|---|---|---|
| Image supply chain | Trivy, Syft, Cosign | CI pipeline and admission (Kyverno verifyImages) | Unsigned image slips in |
| Admission | Pod Security Standards, OPA Gatekeeper, Kyverno | kube-apiserver webhook | Webhook down blocks writes (or is ignored) |
| Runtime | Falco | Node kernel | Sensor crash loses detection |
| Secrets | Vault, External Secrets | Workload startup and renewal | Secret rotation stalls |
| Network | CiliumNetworkPolicy, Cilium L7 policy | CNI datapath | Policy gap = lateral movement |
| Host | CIS baseline, SELinux/AppArmor, hardened SSH | Node | Compromise of the node |
| Audit | Kubernetes audit log, auditd | apiserver + node | Log loss = no evidence |

## C. Pod Security Standards

Three profiles: `privileged`, `baseline`, `restricted`. Apply at namespace level.

```bash
# Cluster-wide defaults
kubectl label --overwrite ns default pod-security.kubernetes.io/enforce=restricted
kubectl label --overwrite ns kube-system pod-security.kubernetes.io/enforce=privileged
kubectl label --overwrite ns kube-public pod-security.kubernetes.io/enforce=privileged
```

The `kube-system` and `kube-public` namespaces stay at `privileged` because CNI and control-plane components require it. Every other namespace is `restricted`. Workloads needing less are in their own namespace with the correct label, not with a cluster-wide exemption.

Enforce the `restricted` profile meaning:
- `allowPrivilegeEscalation: false`
- `runAsNonRoot: true`
- `seccompProfile.type: RuntimeDefault` or `Localhost`
- `capabilities.drop: ["ALL"]`
- no hostPath, no hostNetwork, no hostPID, no privileged

Enforce with an admission policy, not just the label — the label is only an audit signal by itself.

## D. OPA Gatekeeper

Two constraint templates are used: one blocking privileged pods, one restricting image registries. Both are deployed in audit mode first, then switched to enforce.

```yaml
apiVersion: constraints.gatekeeper.sh/v1beta1
kind: K8sPSPPrivilegedContainer
metadata:
  name: block-privileged
spec:
  enforcementAction: deny
  match:
    kinds:
      - apiGroups: [""]
        kinds: ["Pod"]
  parameters:
    exemptNamespaces: ["kube-system", "gatekeeper-system"]
```

```yaml
apiVersion: constraints.gatekeeper.sh/v1beta1
kind: K8sAllowedRepos
metadata:
  name: allowed-repos
spec:
  enforcementAction: deny
  match:
    kinds:
      - apiGroups: [""]
        kinds: ["Pod"]
  parameters:
    repos:
      - "harbor.internal/*"
      - "!harbor.internal/library/*"
```

Gatekeeper values that must be set deliberately:

```yaml
# Helm values
replicas: 3
audit:
  replicas: 2
  auditInterval: 60
constraintTemplates:
  replicaCount: 3
validatingWebhookFailurePolicy: Fail        # for security namespaces
```

`validatingWebhookFailurePolicy` is the critical setting: `Fail` blocks writes when Gatekeeper is down, `Ignore` lets writes through. The recommendation is `Fail` for application namespaces and `Ignore` for the platform's own namespaces, with the exception process documented.

Verification that the failure policy is scoped per namespace uses the `namespaceSelector` in the webhook configuration, not a global value.

## E. Kyverno

Kyverno covers the policies teams write themselves. Use it for image verification and resource mutation.

```yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: require-image-digest
spec:
  validationFailureAction: Enforce
  rules:
    - name: require-digest
      match:
        any:
          - resources:
              kinds: ["Pod"]
      validate:
        message: "Images must be pinned by digest and come from harbor.internal"
        pattern:
          spec:
            containers:
              - image: "harbor.internal/*@sha256:*"
```

## F. Falco

Falco watches kernel events. Default rules are noisy; ship a tuned ruleset.

```yaml
# values.yaml (relevant parts)
driver: modern_ebpf
tty: false
auditLog: true
priority: notice
falcoctl:
  enabled: true
  config:
    rules:
      - custom-rules.yaml
```

Tuning rules to keep: writes to `/etc`, `/usr/bin`, `/var/lib/ceph`; shell spawned inside a container; unexpected `setuid`; Kubernetes API token reads from a container; outbound connection to a known-bad address. Remove the noisy default rules that fire on every package manager or container start.

A test rule:

```yaml
- rule: Test file write to /etc
  desc: Write to /etc in any container
  condition: container and evt.type=open and open.flags=O_WRONLY and fd.name startswith /etc
  output: "Suspicious file write in container (user=%user.name container=%container.name file=%fd.name)"
  priority: WARNING
  tags: [test]
```

## G. Image supply chain

| Stage | Tool | Command |
|---|---|---|
| Scan | Trivy | `trivy image --severity HIGH,CRITICAL <image>` |
| SBOM | Syft | `syft <image> -o cyclonedx-json > sbom.json` |
| Sign | Cosign | `cosign sign --key cosign.key <image>@sha256:...` |
| Verify | Cosign | `cosign verify --key cosign.pub <image>@sha256:...` |

Pipeline order: build -> scan -> SBOM -> sign -> push to Harbor -> deploy by digest.

Deploy by digest, not by tag. A tag can be repointed; a digest cannot.

```yaml
spec:
  containers:
    - name: app
      image: harbor.internal/platform/app@sha256:abc123...
```

## H. Host baseline

CIS benchmark scripts are available for both distributions. Run them in audit mode first, then remediate.

```bash
# Oracle Linux
dnf install -y aqua-sec-cis 2>/dev/null || true   # or use the CIS-CAT tarball from the internal repo

# Ubuntu
apt install -y cis 2>/dev/null || true
```

The scoring baseline is recorded in `security/host-baseline.md` together with the deviations that are accepted and why (for example, password authentication on the console for the break-glass account, which is an accepted, monitored deviation).

## I. Audit

Kubernetes audit policy — `Metadata` level by default:

```yaml
apiVersion: audit.k8s.io/v1
kind: Policy
omitStages:
  - RequestReceived
rules:
  - level: None
    users: ["system:kube-proxy", "system:node:agent"]
    verbs: ["watch"]
    resources: ["endpoints", "services", "endpointslices"]
  - level: None
    users: ["system:serviceaccount:kube-system:generic-garbage-collector"]
    verbs: ["get"]
  - level: RequestResponse
    resources:
      - group: "" 
        resources: ["secrets"]
  - level: Metadata
    resources:
      - group: ""
        resources: ["pods", "pods/log", "configmaps"]
  - level: Metadata
    resources:
      - group: "authentication.k8s.io"
        resources: ["tokenreviews"]
```

`RequestResponse` on secrets is included only if there is a strong requirement to audit secret access, and it means secret values land in the audit log. Treat that as a secret-at-rest decision: encrypt the audit log, restrict access, and consider the `omitStages` option.

Audit log destination: write to a local file, ship off-host quickly, and keep it out of the cluster's own failure domain.

## J. Validation

See `requirements/validation-strategy.md` family C. The mandatory subset: privileged pod denied, Gatekeeper constraint enforced, Falco test alert raised, CRITICAL image blocked in CI, Cosign verification passes for signed and fails for unsigned, no secrets found in Git, TLS scan clean, break-glass login works with the IdP down.

## K. Best practices

Mandatory:
- Admission controllers in audit mode before enforce, with the violation report reviewed.
- Explicit `validatingWebhookFailurePolicy` per namespace group, and a documented exception path.
- Images deployed by digest.
- Namespaces labelled for Pod Security Standards, with `kube-system` exempted explicitly and narrowly.
- Secrets never in Git, images, or logs.

Strongly recommended:
- Separate namespaces per team, with quotas and network policies per team.
- Restrict `pods/exec` and `pods/portforward` via RBAC; they are equivalent to shell on the node.
- Alert on audit-log pipeline failure, not only on audit-log content.
- Quarterly re-run of the CIS scan and a re-review of accepted deviations.
