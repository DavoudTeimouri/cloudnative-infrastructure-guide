# Argo CD troubleshooting

## Symptoms

- An application is stuck `OutOfSync`.
- `ComparisonError` on an application.
- A sync fails with a webhook or admission error.
- `argocd app sync` reports "the application has not been modified".
- The repo-server cannot fetch from the internal GitLab.
- An image is pulled from the wrong registry.
- Secrets are not populated in the target namespace.

## Likely causes

| Cause | Discriminator |
|---|---|
| The Git repo has a change the cluster does not | `argocd app diff <app>` shows the difference |
| The repo-server cannot reach GitLab | The application shows `ComparisonError` |
| The CA is not trusted by the repo-server | The repo-server log shows an x509 error |
| The Git branch or path does not exist | `argocd app get <app>` shows the error |
| An admission controller rejects the resource | The sync error names the webhook |
| The image name points to the upstream registry | The pod fails with `ImagePullBackOff` |
| The ExternalSecret has not synced | `kubectl get externalsecret -A` shows `SecretSyncedError` |
| The application is paused | `argocd app get <app>` shows `paused` |
| Sync waves are blocking | `argocd app get <app> --show-operation` |

## Diagnostic commands

```bash
# Application state
argocd app list
argocd app get <app>
argocd app get <app> --show-operation
argocd app diff <app>
argocd app history <app>

# In-cluster
kubectl -n argocd get applications
kubectl -n argocd describe application <app>
kubectl -n argocd logs -l app.kubernetes.io/name=argocd-repo-server --tail=100
kubectl -n argocd logs -l app.kubernetes.io/name=argocd-application-controller --tail=100
kubectl -n argocd logs -l app.kubernetes.io/name=argocd-server --tail=100

# The target state
kubectl -n <target-ns> get deploy <name> -o yaml
kubectl -n <target-ns> get events --sort-by=.lastTimestamp | tail -20

# Secrets
kubectl get externalsecret -A
kubectl describe externalsecret <name> -n <ns>
kubectl -n external-secrets logs deploy/external-secrets --tail=100

# Admission
kubectl get validatingwebhookconfigurations
kubectl get mutatingwebhookconfigurations
```

## Expected healthy state

```
$ argocd app get payments-api
Name:           payments-api
Project:        team-payments
Server:         https://kubernetes.default.svc
Namespace:      payments
Sync Status:    Synced
Health Status:  Healthy
```

## Remediation

### ComparisonError

```bash
# The repo-server log names the cause
kubectl -n argocd logs -l app.kubernetes.io/name=argocd-repo-server --tail=200 | grep -i error
```

| Error in the log | Cause | Fix |
|---|---|---|
| `x509: certificate signed by unknown authority` | The internal CA is not trusted | Mount the CA into the repo-server pods and restart |
| `Could not resolve host` | DNS or network path to GitLab | Check DNS and the firewall matrix |
| `authentication required` | The repository credential is missing or expired | Update the Argo CD repository secret |
| `remote: HTTP Basic: Access denied` | The deploy key or token is invalid | Re-issue the credential in GitLab, update the Argo CD secret |

The Argo CD repository secret:

```bash
# The credential itself lives in Vault; ESO writes it into the argocd namespace
kubectl -n argocd get secret repo-payments -o jsonpath='{.data.url}' | base64 -d
kubectl -n argocd get secret repo-payments -o jsonpath='{.data.username}' | base64 -d
```

### Sync fails with an admission error

The error names the webhook and the constraint. Read the constraint:

```bash
kubectl get constraints -o yaml          # Gatekeeper
kubectl get clusterpolicy                 # Kyverno
kubectl get validatingwebhookconfigurations -o yaml | grep -A5 failurePolicy
```

Two distinct problems:
1. The resource genuinely violates a policy. Fix the manifest.
2. The webhook is unavailable. Check the webhook's pods and the `failurePolicy`. A `Fail` policy blocks all writes to that namespace when the webhook is down.

### The image pulls from the upstream registry

```bash
argocd app get <app> | grep -i image
kubectl -n <ns> get deploy <name> -o jsonpath='{.spec.template.spec.containers[*].image}'
```

Fix the source, not the symptom:
- If the Git repo contains upstream image names, add an Argo CD image rewrite rule in `argocd-cm`, or use a Config Management Plugin.
- If the CI pipeline builds the image, the pipeline should write the internal registry path into the manifest. That keeps one source of truth.

### Secrets not populated

```bash
kubectl describe externalsecret <name> -n <ns>
```

| Condition | Cause | Fix |
|---|---|---|
| `SecretSyncedError` | ESO cannot read Vault | Check the ClusterSecretStore, the Vault role, and the service account |
| `SecretSynced` but the target Secret is empty | A template mismatch | Check the `target.template` and the `remoteRef.property` |
| The Secret is synced but the app is unchanged | The app does not reload | Restart the app or use a reloader |

### The application is paused

```bash
argocd app set <app> --sync-policy=none     # pause
argocd app set <app> --sync-policy=automated # resume
```

An application is often paused during an incident so that Argo CD does not revert a hotfix. Resume it after the incident.

### Sync waves blocking

```bash
argocd app get <app> --show-operation
```

A wave waits for the previous wave's resources to be healthy. A resource with a failing readiness probe blocks every later wave. Find the unhealthy resource in the wave and fix it, or remove the wave annotation.

## Risks

- `argocd app sync --prune` with `prune: true` deletes resources removed from Git. A wrong path in Git can delete a StatefulSet or a PVC holder.
- Removing a `finalizer` from an application orphans the resources it manages.
- `argocd app delete --cascade=false` leaves the resources in the cluster but removes them from GitOps, which is a drift source.

## Verification after remediation

```bash
argocd app get <app>          # Synced + Healthy
kubectl -n <target-ns> get pods
kubectl -n <target-ns> get deploy <name> -o jsonpath='{.spec.template.spec.containers[*].image}'
```

Then re-run acceptance test P-03 (Argo CD syncs an application from Git).
