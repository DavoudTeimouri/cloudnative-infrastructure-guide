#!/usr/bin/env python3
"""Build the static guide site from the catalog and the version matrix.

Single source of truth: the repository. The site is generated from it, never
edited by hand. A version bump in compatibility/version-matrix.md or a change
in catalog/catalog.json propagates on the next build.

Stdlib only. No network. No build dependencies.

Usage:
  python3 scripts/build_site.py            # write site/data.json
  python3 scripts/build_site.py --check    # fail if site/data.json is stale
"""
import json
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG = os.path.join(BASE, "catalog", "catalog.json")
EXPORTS = os.path.join(BASE, "catalog", "exports.json")
MATRIX = os.path.join(BASE, "compatibility", "version-matrix.md")
OUT = os.path.join(BASE, "site", "data.json")

# component id in the catalog -> label used in the version matrix
VERSION_ALIASES = {
    "cilium": ["Cilium"],
    "calico": ["Calico"],
    "rook": ["Rook"],
    "ceph": ["Ceph (upstream latest release)", "Ceph Tentacle (active)"],
    "haproxy": ["HAProxy"],
    "nginx": ["Nginx (OSS)"],
    "nic": ["NGINX Ingress Controller (F5)"],
    "ngf": ["NGINX Gateway Fabric"],
    "envoy": ["Envoy Gateway"],
    "metallb": ["MetalLB"],
    "rancher": ["Rancher"],
    "argocd": ["Argo CD"],
    "vault": ["HashiCorp Vault"],
    "openbao": ["OpenBao"],
    "keycloak": ["Keycloak"],
    "kube-prometheus-stack": ["kube-prometheus-stack"],
    "thanos": ["Thanos"],
    "loki": ["Loki"],
    "opensearch": ["OpenSearch"],
    "gatekeeper": ["OPA Gatekeeper"],
    "falco": ["Falco"],
    "velero": ["Velero"],
    "gpu-operator": ["NVIDIA GPU Operator"],
    "istio": ["Istio"],
    "kubespray": ["Kubespray"],
    "keepalived": ["Keepalived"],
    "vllm": ["vLLM"],
    "ngf": ["NGINX Gateway Fabric"],
    "envoy": ["Envoy Gateway"],
}


def parse_version_matrix(path):
    """Return {component_label: version} from every markdown table in the file.

    Looks at the 'Version' or 'Verified version' column. Only rows whose
    status column says VERIFIED are taken, so UNVERIFIED entries never leak
    into the site as if they were confirmed.
    """
    out = {}
    text = open(path, encoding="utf-8").read()
    for block in re.findall(r"(?:^\|.*\n)+", text, re.M):
        rows = [r for r in block.strip().splitlines() if r.strip().startswith("|")]
        if len(rows) < 2:
            continue
        header = [c.strip() for c in rows[0].strip("|").split("|")]
        if "Version" in header:
            vi = header.index("Version")
        elif "Verified version" in header:
            vi = header.index("Verified version")
        else:
            continue
        si = header.index("Status") if "Status" in header else None
        ni = header.index("Component") if "Component" in header else 0
        for row in rows[2:]:
            cells = [c.strip() for c in row.strip("|").split("|")]
            if len(cells) <= max(vi, ni):
                continue
            if si is not None and len(cells) > si:
                if "VERIFIED" not in cells[si]:
                    continue
            version = cells[vi].strip("`")
            if not version or version in ("n/a", "UNVERIFIED", "pin", "-"):
                continue
            label = cells[ni].strip("`")
            out.setdefault(label, version)
    return out


def resolve_versions(matrix):
    resolved = {}
    for key, labels in VERSION_ALIASES.items():
        for label in labels:
            if label in matrix:
                resolved[key] = matrix[label]
                break
    return resolved


def main():
    check = "--check" in sys.argv

    catalog = json.load(open(CATALOG, encoding="utf-8"))
    exports = json.load(open(EXPORTS, encoding="utf-8"))
    matrix = parse_version_matrix(MATRIX)
    versions = resolve_versions(matrix)

    # Kubespray release data lives in the catalog, but the pinned release's
    # component versions come from the matrix and the multi-version guide.
    kubespray_versions = {}
    for release in catalog["clusterMethods"][0].get("versions", {}).values():
        for k, v in release.items():
            kubespray_versions.setdefault(k, v)
    versions.update({k: v for k, v in kubespray_versions.items() if k not in versions})

    # Every doc the catalog points at must exist.
    missing = []
    for comp in catalog["components"]:
        for opt in comp["options"]:
            for key in ("doc", "decisionDoc"):
                ref = opt.get(key)
                if ref and not os.path.exists(os.path.join(BASE, ref)):
                    missing.append(ref)
    for step in catalog["steps"] + catalog["upgradeSections"]:
        for key in ("doc", "altDoc"):
            ref = step.get(key)
            if ref and not os.path.exists(os.path.join(BASE, ref)):
                missing.append(ref)
        for ref in step.get("extraDocs", []):
            if not os.path.exists(os.path.join(BASE, ref)):
                missing.append(ref)
    for method in catalog["methods"]:
        pass
    if missing:
        print("MISSING DOCS:")
        for m in sorted(set(missing)):
            print("  ", m)
        return 1

    data = {
        "catalogVersion": catalog["catalogVersion"],
        "updated": catalog["updated"],
        "source": catalog["source"],
        "methods": catalog["methods"],
        "clusterMethods": catalog["clusterMethods"],
        "components": catalog["components"],
        "values": catalog["values"],
        "steps": catalog["steps"],
        "upgradeSections": catalog["upgradeSections"],
        "exports": exports,
        "versions": versions,
    }

    payload = json.dumps(data, indent=2, sort_keys=False) + "\n"

    if check:
        current = open(OUT, encoding="utf-8").read() if os.path.exists(OUT) else ""
        if current != payload:
            print("STALE: site/data.json does not match the catalog and version matrix.")
            print("Run: python3 scripts/build_site.py")
            return 1
        print("OK: site/data.json is up to date.")
        return 0

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(payload)
    print(f"wrote {OUT} ({len(payload)} bytes, {len(versions)} resolved versions)")
    for k in sorted(versions):
        print(f"  {k} = {versions[k]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
