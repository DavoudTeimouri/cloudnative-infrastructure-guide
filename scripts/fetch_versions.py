#!/usr/bin/env python3
"""Fetch selected upstream facts for the version matrix. Read-only network calls."""
import json
import re
import urllib.request

UA = {"User-Agent": "cloud-native-guide/version-matrix"}


def get(url, binary=False):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read()
    return data if binary else data.decode("utf-8", "replace")


def jget(url):
    return json.loads(get(url))


def show(label, value):
    print(f"{label} => {value}")


print("### Kubespray v2.32.0 supported kubernetes versions")
try:
    md = get("https://raw.githubusercontent.com/kubernetes-sigs/kubespray/release-2.32/README.md")
    m = re.search(r"supported kubernetes versions(.*?)(?:\n\n|\n#)", md, re.S | re.I)
    block = m.group(1) if m else ""
    vers = re.findall(r"v1\.\d+\.\d+", block)
    print("versions:", sorted(set(vers)))
except Exception as e:
    print("ERR", e)

print("\n### Rook v1.21.0 release notes -> ceph version")
try:
    rel = jget("https://api.github.com/repos/rook/rook/releases/tags/v1.21.0")
    body = rel.get("body", "")
    for line in body.splitlines():
        if "ceph" in line.lower() and ("v1" in line or "v2" in line):
            print("  ", line.strip()[:200])
except Exception as e:
    print("ERR", e)

print("\n### Helm chart versions (artifacthub)")
for pkg in [
    "cilium/cilium",
    "external-secrets/external-secrets",
    "argocd/argo-cd",
    "rancher/rancher",
    "open-policy-agent/gatekeeper",
    "hashicorp/vault-k8s",
    "prometheus-community/kube-prometheus-stack",
    "metallb/metallb",
    "ingress-nginx/ingress-nginx",
    "cert-manager/cert-manager",
    "kyverno/kyverno",
    "falcosecurity/falco",
    "vmware-tanzu/velero",
    "grafana/loki",
    "fluent/fluent-bit",
    "hashicorp/vault",
]:
    try:
        d = jget(f"https://artifacthub.io/api/v1/packages/helm/{pkg}")
        show(pkg, f"chart={d.get('version')} app={d.get('app_version')}")
    except Exception as e:
        show(pkg, f"ERR {e}")

print("\n### GitHub latest releases (remaining)")
for repo in [
    "ceph/ceph",
    "gitlabhq/gitlabhq",
    "haproxy/haproxy",
    "bitnami-labs/sealed-secrets",
    "prometheus-operator/kube-prometheus-stack",
    "vmware-tanzu/velero",
    "NVIDIA/gpu-operator",
    "NVIDIA/k8s-device-plugin",
    "NVIDIA/nvidia-container-toolkit",
    "vllm-project/vllm",
    "ggml-org/llama.cpp",
    "triton-inference-server/server",
    "hashicorp/vault",
    "openbao/openbao",
    "sigstore/cosign",
    "aquasecurity/trivy",
    "anchore/syft",
    "grafana/loki",
    "fluent/fluent-bit",
    "opensearch-project/OpenSearch",
    "kubernetes-sigs/gateway-api",
    "kubernetes/ingress-nginx",
    "traefik/traefik",
    "metallb/metallb",
    "open-policy-agent/gatekeeper",
    "kyverno/kyverno",
    "falcosecurity/falco",
    "argoproj/argo-cd",
    "rancher/rancher",
    "keycloak/keycloak",
    "goharbor/harbor",
    "sonatype/nexus-public",
    "cert-manager/cert-manager",
    "external-secrets/external-secrets",
    "rook/rook",
    "containerd/containerd",
    "kubernetes-sigs/kubespray",
    "kubernetes/kubernetes",
    "thanos-io/thanos",
    "grafana/grafana",
    "prometheus/alertmanager",
    "prometheus/node_exporter",
    "kubernetes/kube-state-metrics",
    "NVIDIA/nvidia-device-plugin",
]:
    try:
        d = jget(f"https://api.github.com/repos/{repo}/releases/latest")
        show(repo, d.get("tag_name"))
    except Exception as e:
        show(repo, f"ERR {e}")
