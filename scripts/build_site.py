#!/usr/bin/env python3
"""Build the static guide site from the catalog and the version matrix.

Single source of truth: the repository. The site is generated from it, never
edited by hand. A version bump in compatibility/version-matrix.md or a change
in catalog/*.json propagates on the next build.

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
UPGRADES = os.path.join(BASE, "catalog", "upgrades.json")
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
}


def parse_version_matrix(path):
    """Return {component_label: version} from every markdown table in the file.

    Looks at the 'Version' or 'Verified version' column. Only rows whose status
    says VERIFIED are taken, so UNVERIFIED entries never leak into the site as
    if they were confirmed.
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
            if si is not None and len(cells) > si and "VERIFIED" not in cells[si]:
                continue
            version = cells[vi].strip("`")
            if not version or version in ("n/a", "UNVERIFIED", "pin", "-"):
                continue
            out.setdefault(cells[ni].strip("`"), version)
    return out


def resolve_versions(matrix):
    resolved = {}
    for key, labels in VERSION_ALIASES.items():
        for label in labels:
            if label in matrix:
                resolved[key] = matrix[label]
                break
    return resolved


def collect_doc_refs(catalog, exports, upgrades):
    refs = []
    for method in catalog.get("methods", []):
        pass
    for comp in catalog["components"]:
        for key in ("doc",):
            if comp.get(key):
                refs.append(comp[key])
        for opt in comp["options"]:
            for key in ("doc", "decisionDoc"):
                if opt.get(key):
                    refs.append(opt[key])
    for page in catalog.get("pages", []):
        pass
    for step in catalog["steps"]:
        for key in ("doc", "altDoc"):
            if step.get(key):
                refs.append(step[key])
        refs.extend(step.get("extraDocs", []))
    for flow in upgrades:
        if flow.get("doc"):
            refs.append(flow["doc"])
    return refs


def main():
    check = "--check" in sys.argv

    catalog = json.load(open(CATALOG, encoding="utf-8"))
    exports = json.load(open(EXPORTS, encoding="utf-8"))["exports"]
    upgrades = json.load(open(UPGRADES, encoding="utf-8"))["flows"]
    matrix = parse_version_matrix(MATRIX)
    versions = resolve_versions(matrix)

    # The pinned release's component versions come from the catalog; the matrix
    # wins for anything it also defines.
    for release in catalog["clusterMethods"][0].get("versions", {}).values():
        for k, v in release.items():
            versions.setdefault(k, v)

    # Every doc the catalog points at must exist.
    missing = [r for r in collect_doc_refs(catalog, exports, upgrades)
               if r and not os.path.exists(os.path.join(BASE, r))]
    if missing:
        print("MISSING DOCS:")
        for m in sorted(set(missing)):
            print("  ", m)
        return 1

    # Every page field and component must exist.
    comp_ids = {c["id"] for c in catalog["components"]}
    value_ids = {v["id"] for v in catalog["values"]}
    problems = []
    for page in catalog.get("pages", []):
        for c in page.get("components", []):
            if c not in comp_ids:
                problems.append(f"page {page['id']}: unknown component {c}")
        for f in page.get("fields", []):
            if f not in value_ids:
                problems.append(f"page {page['id']}: unknown field {f}")
    if problems:
        print("PAGE ERRORS:")
        for p in problems:
            print("  ", p)
        return 1

    data = {
        "catalogVersion": catalog["catalogVersion"],
        "updated": catalog["updated"],
        "source": catalog["source"],
        "methods": catalog["methods"],
        "clusterMethods": catalog["clusterMethods"],
        "pages": catalog.get("pages", []),
        "components": catalog["components"],
        "values": catalog["values"],
        "steps": catalog["steps"],
        "upgrades": upgrades,
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
    print(f"wrote {OUT} ({len(payload)} bytes)")
    print(f"  {len(versions)} versions, {len(catalog['components'])} components, "
          f"{len(catalog['values'])} values, {len(catalog['pages'])} pages, "
          f"{len(catalog['steps'])} steps, {len(upgrades)} upgrade flows, {len(exports)} exports")
    return 0


if __name__ == "__main__":
    sys.exit(main())
