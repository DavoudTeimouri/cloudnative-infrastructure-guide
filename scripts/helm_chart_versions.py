#!/usr/bin/env python3
"""Print the newest stable Helm chart version per chart from repo index.yaml files.

Usage: python3 scripts/helm_chart_versions.py
Requires PyYAML (pip install pyyaml). Read-only network access.
"""
import urllib.request

import yaml

UA = {"User-Agent": "cloud-native-guide/version-matrix"}

INDEXES = {
    "argo-cd": "https://argoproj.github.io/argo-helm/index.yaml",
    "argocd-applicationset": "https://argoproj.github.io/argo-helm/index.yaml",
    "rancher": "https://releases.rancher.com/server-charts/stable/index.yaml",
    "gatekeeper": "https://open-policy-agent.github.io/gatekeeper/charts/index.yaml",
    "vault": "https://helm.releases.hashicorp.com/index.yaml",
    "kube-prometheus-stack": "https://prometheus-community.github.io/helm-charts/index.yaml",
    "prometheus": "https://prometheus-community.github.io/helm-charts/index.yaml",
    "node-exporter": "https://prometheus-community.github.io/helm-charts/index.yaml",
    "cilium": "https://helm.cilium.io/index.yaml",
    "metallb": "https://metallb.github.io/metallb/charts/index.yaml",
    "ingress-nginx": "https://kubernetes.github.io/ingress-nginx/index.yaml",  # RETIRED March 2026
    "nginx-ingress": "https://nginx.github.io/helm-charts/index.yaml",
    "cert-manager": "https://charts.jetstack.io/index.yaml",
    "kyverno": "https://kyverno.github.io/kyverno/index.yaml",
    "velero": "https://vmware-tanzu.github.io/helm-charts/index.yaml",
    "loki": "https://grafana.github.io/helm-charts/index.yaml",
    "grafana": "https://grafana.github.io/helm-charts/index.yaml",
    "fluent-bit": "https://fluent.github.io/helm-charts/index.yaml",
    "external-secrets": "https://charts.external-secrets.io/index.yaml",
    "falco": "https://falcosecurity.github.io/charts/index.yaml",
    "thanos": "https://thanos-community.github.io/helm-charts/index.yaml",
    "postgresql": "https://bitnami-labs.github.io/sealed-secrets/index.yaml",
}


def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def is_stable(v):
    return not any(t in v.lower() for t in ("-alpha", "-beta", "-rc", "-pre", "-dev", "-snapshot"))


def semver_key(v):
    """Sort key for chart versions. Handles v-prefix, prerelease suffixes, and
    numeric segments so that 1.17.14 sorts above 1.9.9."""
    s = str(v).lstrip("v")
    core = s.split("+")[0]
    pre = ""
    if "-" in core:
        core, _, pre = core.partition("-")
    parts = []
    for seg in core.split("."):
        digits = "".join(c for c in seg if c.isdigit())
        parts.append(int(digits) if digits else 0)
    while len(parts) < 3:
        parts.append(0)
    # a release (no prerelease) outranks the same version with a prerelease
    return (parts[0], parts[1], parts[2], 0 if pre else 1, pre)


def main():
    for name, url in INDEXES.items():
        try:
            doc = yaml.safe_load(get(url))
            entries = (doc.get("entries") or {}).get(name) or []
            stable = [e for e in entries if is_stable(str(e.get("version", "")))]
            pool = stable or entries
            if not pool:
                print(f"{name:24s} => NOT FOUND")
                continue
            best = max(pool, key=lambda e: semver_key(e.get("version", "")))
            print(f"{name:24s} chart={best.get('version'):16s} app={best.get('appVersion')}")
        except Exception as e:
            print(f"{name:24s} => ERR {e}")


if __name__ == "__main__":
    main()
