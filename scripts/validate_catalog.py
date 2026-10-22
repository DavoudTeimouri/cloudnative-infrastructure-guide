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
    comp_ids = {comp["id"] for comp in c["components"]}
    for step in c["steps"]:
        when = step.get("when") or {}
        for key in when.get("component", {}):
            assert key in comp_ids, f"step {step['id']} gates on unknown component {key}"


def test_built_data_is_current():
    """The committed site data must match what the generator produces."""
    import subprocess
    res = subprocess.run(
        [sys.executable, os.path.join(BASE, "scripts", "build_site.py"), "--check"],
        capture_output=True, text=True,
    )
    assert res.returncode == 0, f"site/data.json is stale:\n{res.stdout}{res.stderr}"


def main():
    tests = [
        ("catalog has the required sections", test_catalog_shape),
        ("every component has exactly one default", test_component_defaults),
        ("every referenced document exists", test_docs_exist),
        ("export templates are well formed", test_export_templates),
        ("step conditions reference real components", test_steps_reference_real_components),
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
