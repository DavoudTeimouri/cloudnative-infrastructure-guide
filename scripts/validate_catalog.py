#!/usr/bin/env python3
"""Assert-based validation of the site catalog.

Checks the things that break silently: a missing document, an unknown
placeholder, a component with no default, a page pointing at a component that
does not exist, an export gated on an option that was renamed.

Usage: python3 scripts/validate_catalog.py
"""
import json
import os
import re
import subprocess
import sys
import tempfile

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG = os.path.join(BASE, "catalog", "catalog.json")
EXPORTS = os.path.join(BASE, "catalog", "exports.json")
UPGRADES = os.path.join(BASE, "catalog", "upgrades.json")
DATA = os.path.join(BASE, "site", "data.json")

FAILURES = []


def check(name, fn):
    try:
        fn()
        print(f"OK   {name}")
    except AssertionError as e:
        FAILURES.append(name)
        print(f"FAIL {name}: {e}")
    except Exception as e:  # noqa: BLE001
        FAILURES.append(name)
        print(f"ERROR {name}: {e!r}")


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def catalog():
    return load(CATALOG)


def exports():
    return load(EXPORTS)["exports"]


def upgrades():
    return load(UPGRADES)["flows"]


def test_catalog_shape():
    c = catalog()
    assert c.get("catalogVersion"), "catalogVersion missing"
    for key in ("methods", "clusterMethods", "components", "values", "pages", "steps"):
        assert c.get(key), f"catalog section {key} missing or empty"
    assert len(c["steps"]) >= 15, "expected at least 15 implementation steps"
    assert len(upgrades()) >= 6, "expected at least 6 upgrade flows"


def test_component_defaults():
    ids = set()
    for comp in catalog()["components"]:
        assert comp["id"] not in ids, f"duplicate component id {comp['id']}"
        ids.add(comp["id"])
        assert comp["options"], f"component {comp['id']} has no options"
        defaults = [o for o in comp["options"] if o.get("default")]
        if comp.get("multi"):
            assert len(defaults) >= 1, f"multi component {comp['id']} needs a default"
        else:
            assert len(defaults) == 1, \
                f"component {comp['id']} must have exactly one default, found {len(defaults)}"
        for opt in comp["options"]:
            assert opt.get("id"), f"option in {comp['id']} has no id"
            assert opt.get("title"), f"option {comp['id']}/{opt['id']} has no title"


def test_docs_exist():
    c = catalog()
    missing = []

    def want(ref):
        if ref and not os.path.exists(os.path.join(BASE, ref)):
            missing.append(ref)

    for comp in c["components"]:
        want(comp.get("doc"))
        for opt in comp["options"]:
            want(opt.get("doc"))
            want(opt.get("decisionDoc"))
    for step in c["steps"]:
        want(step.get("doc"))
        want(step.get("altDoc"))
        for r in step.get("extraDocs", []):
            want(r)
    for flow in upgrades():
        want(flow.get("doc"))
    assert not missing, f"references missing files: {sorted(set(missing))}"


def test_pages():
    c = catalog()
    comp_ids = {x["id"] for x in c["components"]}
    value_ids = {v["id"] for v in c["values"]}
    page_ids = set()
    for page in c["pages"]:
        assert page["id"] not in page_ids, f"duplicate page id {page['id']}"
        page_ids.add(page["id"])
        assert page.get("title"), f"page {page['id']} has no title"
        for cid in page.get("components", []):
            assert cid in comp_ids, f"page {page['id']}: unknown component {cid}"
        for fid in page.get("fields", []):
            assert fid in value_ids, f"page {page['id']}: unknown field {fid}"
    # Every component and every value must be reachable from some page.
    placed = set()
    fields = set()
    for page in c["pages"]:
        placed.update(page.get("components", []))
        fields.update(page.get("fields", []))
    assert comp_ids <= placed, f"components not on any page: {sorted(comp_ids - placed)}"
    assert value_ids <= fields, f"values not on any page: {sorted(value_ids - fields)}"


def test_exports():
    c = catalog()
    comp_map = {x["id"]: {o["id"] for o in x["options"]} for x in c["components"]}
    value_ids = {v["id"] for v in c["values"]}
    ex = exports()
    for e in ex:
        assert e.get("id"), "export without id"
        assert e.get("filename"), f"export {e['id']} has no filename"
        assert e.get("template"), f"export {e['id']} has no template"
        if e.get("when"):
            cid = e["when"]["component"]
            assert cid in comp_map, f"export {e['id']} when.component unknown: {cid}"
            for v in e["when"].get("values", []):
                assert v in comp_map[cid], f"export {e['id']} gates on unknown option {cid}={v}"
        if e.get("component") and e["component"] not in comp_map \
                and e["component"] not in ("clusterMethods", "steps"):
            raise AssertionError(f"export {e['id']} references unknown component {e['component']}")
        for ns, key in re.findall(r"\{\{\s*(value|choice|version)\.([a-zA-Z0-9_-]+)\s*\}\}", e["template"]):
            if ns == "value":
                assert key in value_ids, f"export {e['id']} uses unknown value.{key}"


def test_version_keys_resolve():
    if not os.path.exists(DATA):
        raise AssertionError("site/data.json missing; run scripts/build_site.py first")
    data = load(DATA)
    versions = set(data["versions"])
    ex = exports()
    for e in ex:
        for key in re.findall(r"\{\{\s*version\.([a-zA-Z0-9_-]+)\s*\}\}", e["template"]):
            assert key in versions, f"export {e['id']} uses unresolved version.{key}"
    for flow in data["upgrades"]:
        for key in re.findall(r"\{\{\s*version\.([a-zA-Z0-9_-]+)\s*\}\}", json.dumps(flow)):
            assert key in versions, f"flow {flow['id']} uses unresolved version.{key}"


def test_step_conditions():
    c = catalog()
    opts = {x["id"]: {o["id"] for o in x["options"]} for x in c["components"]}
    for step in c["steps"]:
        when = step.get("when") or {}
        for key, want in (when.get("component") or {}).items():
            assert key in opts, f"step {step['id']} gates on unknown component {key}"
            wanted = want if isinstance(want, list) else [want]
            for v in wanted:
                assert v in opts[key], f"step {step['id']} gates on unknown option {key}={v}"


# ---------------------------------------------------------------------------
# rendering mirror of site/app.js
# ---------------------------------------------------------------------------

def ip_add(ip, offset):
    parts = str(ip or "").split(".")
    if len(parts) != 4:
        return ""
    try:
        value = sum(int(p) << (8 * (3 - i)) for i, p in enumerate(parts))
    except ValueError:
        return ""
    value += offset
    return ".".join(str((value >> (8 * (3 - i))) & 255) for i in range(4))


def default_state(data):
    values = {v["id"]: str(v.get("default", "")) for v in data["values"]}
    choices = {}
    for comp in data["components"]:
        if comp.get("multi"):
            defs = [o["id"] for o in comp["options"] if o.get("default")]
            choices[comp["id"]] = defs or ["none"]
        else:
            defs = [o for o in comp["options"] if o.get("default")] or comp["options"]
            choices[comp["id"]] = defs[0]["id"]
    return values, choices


def num(values, key):
    try:
        return int(str(values.get(key, "0")).strip() or 0)
    except ValueError:
        return 0


def topology(values, choices):
    prefix = values.get("nodePrefix", "k8s")

    def role(role_id, count, start, offset):
        out = []
        for i in range(count):
            out.append({
                "name": f"{prefix}-{role_id}-{i + 1}",
                "ip": ip_add(start, offset + i),
            })
        return out

    cp = role("cp", num(values, "appCpCount"), values.get("appNodeIpStart", ""), 0)
    workers = role("w", num(values, "appWorkerCount"), values.get("appNodeIpStart", ""), len(cp))
    gpu_on = choices.get("gpu") in ("mig", "timeslicing")
    gpu = role("gpu", num(values, "gpuCount"), values.get("appNodeIpStart", ""), len(cp) + len(workers)) if gpu_on else []

    mgmt = [{"name": f"{prefix}-mgmt-{i + 1}", "ip": ip_add(values.get("mgmtIpStart", ""), i)}
            for i in range(num(values, "mgmtWorkerCount"))]

    storage = str(choices.get("storage", ""))
    ceph = []
    if storage.startswith("cephadm"):
        ceph = [{"name": f"ceph-{i + 1}", "ip": ip_add(values.get("cephIpStart", ""), i)}
                for i in range(num(values, "cephNodeCount"))]

    edge = [{"name": f"lb-{i + 1}", "ip": ip_add(values.get("edgeIpStart", ""), i)}
            for i in range(num(values, "edgeCount"))]

    return {"cp": cp, "w": workers, "gpu": gpu, "mgmt": mgmt, "ceph": ceph, "edge": edge}


def derived(data, values, choices, versions):
    t = topology(values, choices)

    def host_lines(lst):
        return "\n".join(f"{n['name']} ansible_host={n['ip']} ip={n['ip']}" for n in lst)

    gpu_group = ""
    if t["gpu"]:
        gpu_group = "\n[k8s-node:children]\ngpu-node\n\n[gpu-node]\n" + host_lines(t["gpu"])

    storage = str(choices.get("storage", ""))
    engine = "docker" if storage == "cephadm-docker" else "podman"

    idp_opts = []
    idp = choices.get("idpIntegration") or []
    comp = [c for c in data["components"] if c["id"] == "idpIntegration"]
    if comp and isinstance(idp, list):
        for o in comp[0]["options"]:
            if o["id"] in idp and o["id"] != "none":
                idp_opts.append(f"- **{o['title']}** → `{o['doc']}`")

    return {
        "appCpHosts": host_lines(t["cp"]),
        "appWorkerHosts": host_lines(t["w"]),
        "appCpCount": str(len(t["cp"])),
        "appWorkerCount": str(len(t["w"])),
        "gpuHosts": host_lines(t["gpu"]),
        "gpuHostList": ", ".join(n["ip"] for n in t["gpu"]),
        "gpuGroup": gpu_group,
        "gpuReplicas": "2" if len(t["gpu"]) > 1 else "1",
        "firstGpuNode": t["gpu"][0]["name"] if t["gpu"] else "",
        "mgmtHosts": host_lines(t["mgmt"]),
        "mgmtCount": str(len(t["mgmt"])),
        "cephHosts": host_lines(t["ceph"]),
        "cephHostList": ", ".join(f"{n['name']}={n['ip']}" for n in t["ceph"]),
        "cephOtherIps": " ".join(n["ip"] for n in t["ceph"][1:]),
        "cephMonIp": t["ceph"][0]["ip"] if t["ceph"] else "",
        "cephEngine": engine,
        "cephEngineFlag": "--docker" if engine == "docker" else "",
        "edgeHosts": host_lines(t["edge"]),
        "edgeHostList": ", ".join(f"{n['name']}={n['ip']}" for n in t["edge"]),
        "edgeL1": t["edge"][0]["ip"] if t["edge"] else "",
        "edgePeerList": "\n".join(f"        {n['ip']}" for n in t["edge"][1:]),
        "extraRegistryMirrors": "",
        "idpTargets": "\n".join(idp_opts) if idp_opts else "- none selected",
        "registryAuth": "",
        "vrrpAuthPass": "",
        "revision": str(versions.get("istio", "")).replace(".", "-"),
        "istioProfile": "ambient" if choices.get("serviceMesh") == "istio-ambient" else "default",
        "totalNodes": str(sum(len(v) for v in t.values())),
    }


def render_export(template, data):
    values, choices = default_state(data)
    versions = data["versions"]
    d = derived(data, values, choices, versions)
    cluster = data["clusterMethods"][0]["id"]

    def sub(m):
        ns, key = m.group(1), m.group(2)
        if ns == "value":
            return str(values.get(key, ""))
        if ns == "choice":
            v = choices.get(key)
            if v is None:
                return key if key == cluster else ""
            return ",".join(v) if isinstance(v, list) else str(v)
        if ns == "version":
            return str(versions.get(key, "UNVERIFIED"))
        return ""

    out = re.sub(r"\{\{\s*(value|choice|version)\.([a-zA-Z0-9_-]+)\s*\}\}", sub, template)
    out = re.sub(r"\{\{\s*([a-zA-Z0-9_-]+)\s*\}\}", lambda m: str(d.get(m.group(1), "")), out)
    return out


def test_exports_render_cleanly():
    if not os.path.exists(DATA):
        raise AssertionError("site/data.json missing; run scripts/build_site.py first")
    data = load(DATA)
    problems = []
    for exp in data["exports"]:
        body = render_export(exp["template"], data)
        left = re.findall(r"\{\{[^}]*\}\}", body)
        if left:
            problems.append(f"{exp['id']}: unresolved {left[:3]}")
        if exp["filename"].endswith((".yaml", ".yml")):
            try:
                import yaml  # optional in a minimal CI image
            except ImportError:
                continue
            try:
                list(yaml.safe_load_all(body))
            except Exception as e:  # noqa: BLE001
                problems.append(f"{exp['id']}: invalid YAML: {e}")
        if exp["filename"].endswith(".sh"):
            with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False) as fh:
                fh.write(body)
                tmp = fh.name
            res = subprocess.run(["bash", "-n", tmp], capture_output=True, text=True)
            os.unlink(tmp)
            if res.returncode != 0:
                problems.append(f"{exp['id']}: bash syntax: {res.stderr.strip()[:200]}")
    assert not problems, "; ".join(problems)


def test_inventory_groups():
    data = load(DATA)
    exp = [e for e in data["exports"] if e["id"] == "inventory"][0]
    body = render_export(exp["template"], data)
    for group in ("[control-plane]", "[etcd]", "[k8s-cluster:children]"):
        assert group in body, f"inventory missing {group}"
    cp = body.split("[control-plane]")[1].split("[etcd]")[0].strip().splitlines()
    assert len(cp) == 3, f"expected 3 control-plane hosts, got {len(cp)}"
    assert all("ansible_host=" in line for line in cp), "control-plane lines missing ansible_host"


def test_upgrade_flows():
    for flow in upgrades():
        for key in ("id", "title", "doc", "downtime", "rollback", "steps"):
            assert flow.get(key), f"flow {flow.get('id')} missing {key}"
        assert len(flow["steps"]) >= 4, f"flow {flow['id']} has too few steps"
        for step in flow["steps"]:
            assert step.get("title"), f"flow {flow['id']} step without title"
            assert step.get("actions"), f"flow {flow['id']} step {step['title']} has no actions"
            assert "phase" in step, f"flow {flow['id']} step {step['title']} has no phase"
        assert any(s.get("gate") for s in flow["steps"]), \
            f"flow {flow['id']} has no gate step"


def test_built_data_is_current():
    res = subprocess.run(
        [sys.executable, os.path.join(BASE, "scripts", "build_site.py"), "--check"],
        capture_output=True, text=True,
    )
    assert res.returncode == 0, f"site/data.json is stale:\n{res.stdout}{res.stderr}"


def main():
    tests = [
        ("catalog has the required sections", test_catalog_shape),
        ("components have one default, multi has one", test_component_defaults),
        ("every referenced document exists", test_docs_exist),
        ("pages cover every component and value", test_pages),
        ("export gates and placeholders are valid", test_exports),
        ("every version key resolves", test_version_keys_resolve),
        ("step conditions reference real options", test_step_conditions),
        ("export templates render without leftovers", test_exports_render_cleanly),
        ("generated inventory has the expected groups", test_inventory_groups),
        ("upgrade flows are complete and gated", test_upgrade_flows),
        ("site/data.json matches the sources", test_built_data_is_current),
    ]
    for name, fn in tests:
        check(name, fn)
    print()
    if FAILURES:
        print(f"{len(FAILURES)} check(s) failed")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
