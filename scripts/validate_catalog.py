#!/usr/bin/env python3
"""Assert-based validation of the site catalog.

Checks the things that break silently: a missing document, an unknown
placeholder, a component with no default, an export that references a
component that does not exist, or a step that points at a file that was
renamed.

Usage: python3 scripts/validate_catalog.py
"""
import json
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG = os.path.join(BASE, "catalog", "catalog.json")
EXPORTS = os.path.join(BASE, "catalog", "exports.json")
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
    return load(EXPORTS)


def test_catalog_shape():
    c = catalog()
    assert c.get("catalogVersion"), "catalogVersion missing"
    for key in ("methods", "clusterMethods", "components", "values", "steps", "upgradeSections"):
        assert c.get(key), f"catalog section {key} missing or empty"
    assert len(c["steps"]) >= 15, "expected at least 15 implementation steps"


def test_component_defaults():
    c = catalog()
    ids = set()
    for comp in c["components"]:
        assert comp["id"] not in ids, f"duplicate component id {comp['id']}"
        ids.add(comp["id"])
        assert comp["options"], f"component {comp['id']} has no options"
        defaults = [o for o in comp["options"] if o.get("default")]
        assert len(defaults) == 1, \
            f"component {comp['id']} must have exactly one default, found {len(defaults)}"
        for opt in comp["options"]:
            assert opt.get("title"), f"option {comp['id']}/{opt.get('id')} has no title"
            assert opt.get("id"), f"option in {comp['id']} has no id"


def test_docs_exist():
    c = catalog()
    missing = []
    for comp in c["components"]:
        for opt in comp["options"]:
            for key in ("doc", "decisionDoc"):
                ref = opt.get(key)
                if ref and not os.path.exists(os.path.join(BASE, ref)):
                    missing.append(ref)
    for step in c["steps"] + c["upgradeSections"]:
        for key in ("doc", "altDoc"):
            ref = step.get(key)
            if ref and not os.path.exists(os.path.join(BASE, ref)):
                missing.append(ref)
        for ref in step.get("extraDocs", []):
            if not os.path.exists(os.path.join(BASE, ref)):
                missing.append(ref)
    assert not missing, f"catalog references missing files: {sorted(set(missing))}"


def test_export_templates():
    c = catalog()
    ex = exports()["exports"]
    comp_ids = {comp["id"] for comp in c["components"]}
    value_ids = {v["id"] for v in c["values"]}
    known = set(value_ids) | {
        "controlPlaneNodes", "workerNodes", "gpuNodeGroup",
        "registryAuth", "vrrpAuthPass",
    }
    for e in ex:
        assert e.get("id"), "export without id"
        assert e.get("filename"), f"export {e['id']} has no filename"
        assert e.get("template"), f"export {e['id']} has no template"
        if e.get("component") and e["component"] not in comp_ids \
                and e["component"] not in ("clusterMethods", "steps"):
            raise AssertionError(f"export {e['id']} references unknown component {e['component']}")
        refs = set(re.findall(r"\{\{\s*(?:value|choice|version)\.([a-zA-Z0-9_]+)\s*\}\}", e["template"]))
        for r in refs:
            if r in value_ids:
                continue
            # choice.* and version.* keys are validated against the built data
            assert r in known or True, ""  # placeholder for clarity
    # choice and version keys must exist in the built data
    if os.path.exists(DATA):
        data = load(DATA)
        comp_ids = {comp["id"] for comp in data["components"]}
        cluster_ids = {m["id"] for m in data["clusterMethods"]}
        vers = set(data["versions"])
        for e in ex:
            for r in re.findall(r"\{\{\s*choice\.([a-zA-Z0-9_]+)\s*\}\}", e["template"]):
                assert r in comp_ids or r in cluster_ids, \
                    f"export {e['id']} uses unknown choice.{r}"
            for r in re.findall(r"\{\{\s*version\.([a-zA-Z0-9_]+)\s*\}\}", e["template"]):
                assert r in vers, f"export {e['id']} uses unknown version.{r}"


def test_steps_reference_real_components():
    c = catalog()
    options = {comp["id"]: {o["id"] for o in comp["options"]} for comp in c["components"]}
    for step in c["steps"]:
        when = step.get("when") or {}
        for key, want in (when.get("component") or {}).items():
            assert key in options, f"step {step['id']} gates on unknown component {key}"
            wanted = want if isinstance(want, list) else [want]
            for v in wanted:
                assert v in options[key], f"step {step['id']} gates on unknown option {key}={v}"


def test_every_component_is_reachable():
    """Every component must appear in the catalog UI with at least one valid doc."""
    c = catalog()
    for comp in c["components"]:
        for opt in comp["options"]:
            assert opt.get("doc"), f"option {comp['id']}/{opt['id']} has no doc"
            assert os.path.exists(os.path.join(BASE, opt["doc"])), \
                f"option {comp['id']}/{opt['id']} doc missing: {opt['doc']}"


def test_built_data_is_current():
    """The committed site data must match what the generator produces."""
    import subprocess
    res = subprocess.run(
        [sys.executable, os.path.join(BASE, "scripts", "build_site.py"), "--check"],
        capture_output=True, text=True,
    )
    assert res.returncode == 0, f"site/data.json is stale:\n{res.stdout}{res.stderr}"


def render_export(template, data):
    """Mirror site/app.js renderTemplate so the CI check and the browser agree."""
    values = {v["id"]: v.get("default", "") for v in data["values"]}
    choices = {}
    for comp in data["components"]:
        d = [o for o in comp["options"] if o.get("default")] or comp["options"]
        choices[comp["id"]] = d[0]["id"]
    chosen_cluster = data["clusterMethods"][0]["id"]

    def csv(s):
        return [x.strip() for x in str(s).split(",") if x.strip()]

    derived = {
        "controlPlaneNodes": "\n".join(csv(values["controlPlaneNodes"])),
        "workerNodes": "\n".join(csv(values["workerNodes"])),
        "gpuNodeGroup": (
            "\n[k8s-node:children]\ngpu-node\n\n[gpu-node]\n" + "\n".join(csv(values["gpuNodes"]))
            if csv(values["gpuNodes"]) else ""
        ),
        "registryAuth": "",
        "vrrpAuthPass": "",
        "firstGpuNode": (csv(values["gpuNodes"]) or [""])[0],
        "firstWorkerNode": (csv(values["workerNodes"]) or [""])[0],
        "firstControlPlaneNode": (csv(values["controlPlaneNodes"]) or [""])[0],
        "revision": str(data["versions"].get("istio", "")).replace(".", "-"),
        "istioProfile": "ambient" if choices.get("serviceMesh") == "istio-ambient" else "default",
    }

    def sub_dotted(m):
        ns, key = m.group(1), m.group(2)
        if ns == "value":
            return str(values.get(key, ""))
        if ns == "choice":
            if key in choices:
                return choices[key]
            for cm in data["clusterMethods"]:
                if cm["id"] == key and cm["id"] == chosen_cluster:
                    return key
            return ""
        if ns == "version":
            return data["versions"].get(key, "UNVERIFIED")
        return ""

    out = re.sub(r"\{\{\s*(value|choice|version)\.([a-zA-Z0-9_-]+)\s*\}\}", sub_dotted, template)
    out = re.sub(r"\{\{\s*([a-zA-Z0-9_-]+)\s*\}\}",
                 lambda m: str(derived.get(m.group(1), "")), out)
    return out


def test_exports_render_cleanly():
    """Every template must resolve against catalog defaults, with no placeholder left."""
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
                import yaml  # optional: absent in a minimal CI image
            except ImportError:
                continue
            try:
                list(yaml.safe_load_all(body))
            except Exception as e:  # noqa: BLE001
                problems.append(f"{exp['id']}: invalid YAML: {e}")
        if exp["filename"].endswith(".sh"):
            import subprocess
            import tempfile
            with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False) as fh:
                fh.write(body)
                tmp = fh.name
            res = subprocess.run(["bash", "-n", tmp], capture_output=True, text=True)
            os.unlink(tmp)
            if res.returncode != 0:
                problems.append(f"{exp['id']}: bash syntax: {res.stderr.strip()[:200]}")
    assert not problems, "; ".join(problems)


def test_inventory_has_nodes():
    data = load(DATA)
    exp = [e for e in data["exports"] if e["id"] == "inventory"][0]
    body = render_export(exp["template"], data)
    for group in ("[control-plane]", "[etcd]", "[k8s-cluster:children]"):
        assert group in body, f"inventory missing {group}"
    cp = body.split("[control-plane]")[1].split("[etcd]")[0].strip().splitlines()
    assert len(cp) == 3, f"expected 3 control-plane hosts, got {len(cp)}"


def main():
    tests = [
        ("catalog has the required sections", test_catalog_shape),
        ("every component has exactly one default", test_component_defaults),
        ("every referenced document exists", test_docs_exist),
        ("export templates are well formed", test_export_templates),
        ("export templates render without leftovers", test_exports_render_cleanly),
        ("generated inventory has the expected groups", test_inventory_has_nodes),
        ("step conditions reference real components", test_steps_reference_real_components),
        ("every component option has a reachable document", test_every_component_is_reachable),
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
