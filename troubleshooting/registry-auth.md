# Registry and repository authentication troubleshooting

## Symptoms

- `crictl pull` fails with `unauthorized: authentication required`.
- `ImagePullBackOff` on a pod.
- `helm install` fails with a 401 or 403 from the chart repository.
- `apt-get update` fails with `NO_PUBKEY` or `The repository ... is not signed`.
- `dnf install` fails with `GPG check FAILED`.
- `pip install` fails with a TLS verification error.
- A push to Harbor fails with `denied: requested access to the resource is denied`.

## Likely causes

| Cause | Discriminator |
|---|---|
| The registry credentials are not in the containerd configuration | `/etc/containerd/certs.d/<registry>/hosts.toml` has no `Authorization` header |
| The CA is not in the containerd trust store | The error mentions an unknown authority or certificate |
| The Harbor project does not exist | `curl -k -u user:pass https://harbor/api/v2.0/projects/<name>` returns 404 |
| The robot account lacks the pull or push permission | The push returns 403 with a policy message |
| The image path does not exist in the internal registry | The pull returns `manifest unknown` |
| The image was mirrored to a different repository path | The pull returns `repository not found` |
| The package repository's GPG key is missing | `NO_PUBKEY` or `GPG check FAILED` |
| The repository's `Release` file is not signed correctly | apt reports the repository is not signed |
| The Nexus/Harbor URL is wrong or the path layout differs | 404 on the repository path |

## Diagnostic commands

```bash
# containerd
crictl pull harbor.internal/platform/app:1.0.0
crictl images | head
ctr -n k8s.io images ls | head

# The containerd registry config
cat /etc/containerd/certs.d/harbor.internal/hosts.toml
systemctl status containerd
journalctl -u containerd --since "5 min ago" | tail -30

# Harbor API
curl -sk -u "$ROBO_USER:$ROBO_PASS" https://harbor.internal/api/v2.0/projects | jq '.[].name'
curl -sk -u "$ROBO_USER:$ROBO_PASS" \
  "https://harbor.internal/v2/platform/app/tags/list" | jq .

# Nexus
curl -sk -u "$NEXUS_USER:$NEXUS_PASS" https://nexus.internal/service/rest/v1/status
curl -skI https://nexus.internal/repository/deb-ubuntu/dists/noble/InRelease

# apt
apt-get update -o Debug::Acquire::http=true
apt-cache policy <package>

# dnf
dnf repolist --enabled
dnf install --downloadonly --downloaddir=/tmp/dnf-test <package>
rpm -qa gpg-pubkey --qf '%{name}-%{version} %{summary}\n'

# pip
pip config list
pip download --no-deps --dest /tmp/piptest requests
```

## Expected healthy state

```bash
$ crictl pull harbor.internal/platform/app:1.0.0
1f2e3d4c5b6a@sha256:abc123...
```

```bash
$ apt-get update
Hit:1 https://nexus.internal/repository/deb-ubuntu noble InRelease
```

## Remediation

### containerd cannot pull from the internal registry

The `hosts.toml` for the registry must contain the CA path, the credentials, and the mirror endpoint:

```toml
# /etc/containerd/certs.d/harbor.internal/hosts.toml
server = "https://harbor.internal"

[host."https://harbor.internal"]
  capabilities = ["pull", "resolve"]
  ca = "/etc/containerd/certs.d/harbor.internal/ca.crt"
  skip_verify = false
  [host."https://harbor.internal".header]
    Authorization = "Basic <base64 user:password>"
```

Then restart containerd:

```bash
systemctl restart containerd
```

Credentials in this file are a secret. In this platform the file is written by Ansible from a Vault lookup, and the robot account secret is rotated on a schedule.

### Harbor project missing or the permission is wrong

```bash
curl -sk -u "$ADMIN_USER:$ADMIN_PASS" -X POST \
  https://harbor.internal/api/v2.0/projects \
  -H 'Content-Type: application/json' \
  -d '{"project_name":"platform","public":false,"registry_id":0}'
```

Robot account permissions are set on the project. A pull-only robot account cannot push; the push failure says `denied: requested access to the resource is denied`.

### The image was mirrored to the wrong path

The rule that avoids this: mirror with the **same repository path as upstream**. `ghcr.io/owner/app` becomes `harbor.internal/owner/app`, not `harbor.internal/platform/app`. When the paths match, no manifest rewrite is needed anywhere and the image list is mechanical.

If the paths genuinely differ, every consumer needs a rewrite rule — Argo CD image rewrite, Kubespray `*_image_repo` overrides, and the Dockerfile FROM lines. That is why the matching-path rule exists.

### apt/dnf GPG failure

```bash
# Import the internal repository key
curl -fsSL https://nexus.internal/repository/deb-ubuntu/keys/internal.gpg \
  | gpg --dearmor -o /usr/share/keyrings/internal-nexus.gpg
apt-get update
```

```bash
rpm --import https://nexus.internal/repository/rpm-oraclelinux/keys/ol9.key
dnf makecache
```

### The CA is not trusted by containerd

containerd does not use the system trust store for registry TLS by default when `certs.d` is in use. The `ca` key in `hosts.toml` points at the CA file. If `ca` is omitted, containerd falls back to the system store.

```bash
cp internal-ca.crt /etc/containerd/certs.d/harbor.internal/ca.crt
systemctl restart containerd
```

### pip TLS failure

```bash
# /etc/pip.conf or the venv pip.conf
[global]
index-url = https://nexus.internal/repository/pypi/simple
extra-index-url =
trusted-host =
cert = /etc/pki/ca-trust/source/anchors/internal-ca.crt
```

Never set `trusted-host` as a workaround for a certificate error. That disables verification for that host.

## Risks

- `skip_verify = true` in the containerd registry config disables TLS verification for that registry. Use it only temporarily to isolate a CA distribution problem.
- Deleting and recreating a Harbor project deletes the images in it.
- Rotating a robot account secret requires updating containerd on every node and restarting containerd. During that window, image pulls fail on the restarted nodes. Rotate in a controlled rolling fashion.

## Verification after remediation

```bash
# On every node
crictl pull harbor.internal/platform/app:1.0.0
# Offline environment
kubectl run pulltest --rm -it --restart=Never \
  --image=harbor.internal/platform/busybox:1.36 -- echo pull-ok
```

Then re-run acceptance tests F-01 (offline package install) and F-02 (offline image pull).
