#!/usr/bin/env python3
"""Scaffold a service module from the golden path.

Reads platform/golden-paths/cloudnative-service.json, validates the name and
team against the spec, then writes site/modules/<name>/.

Usage:
  python3 scripts/golden_path.py create my-service --team platform
  python3 scripts/golden_path.py create my-service --team platform --dry-run
"""
import argparse
import json
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPEC = os.path.join(BASE, "platform", "golden-paths", "cloudnative-service.json")

INDEX = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__NAME__ · Cloud-Native Configurator</title>
<link rel="stylesheet" href="../../styles.css?v=3.4.0">
<link rel="stylesheet" href="../module.css?v=3.4.0">
</head>
<body>
<header>
  <h1>__NAME__</h1>
  <p class="meta">Owner: __TEAM__ · Generated from the cloud-native-service golden path</p>
  <nav><a href="../../index.html">Main site</a></nav>
</header>
<main id="app"></main>
<script src="app.js"></script>
</body>
</html>
"""

APP = """var SERVICE = "__NAME__";
var OWNER = "__TEAM__";

function render() {
  var el = document.getElementById("app");
  if (!el) { return; }
  el.innerHTML = "<p>Module scaffolded. Replace this file with the step form.</p>" +
    "<p>Service: " + SERVICE + " · Owner: " + OWNER + "</p>";
}

window.onload = render;
"""


def main():
    ap = argparse.ArgumentParser(description="Scaffold a service module from the golden path")
    sub = ap.add_subparsers(dest="cmd", required=True)
    create = sub.add_parser("create", help="create site/modules/<name>/")
    create.add_argument("name")
    create.add_argument("--team", required=True)
    create.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    spec = json.load(open(SPEC, encoding="utf-8"))
    params = {p["name"]: p for p in spec["spec"]["parameters"]}

    for field, value in (("service_name", args.name), ("owner_team", args.team)):
        rx = params[field].get("validation")
        if rx and not re.match(rx, value):
            sys.exit(f"invalid {field}: {value!r} does not match {rx}")

    out = os.path.join(BASE, "site", "modules", args.name)
    files = {
        "index.html": INDEX.replace("__NAME__", args.name).replace("__TEAM__", args.team),
        "app.js": APP.replace("__NAME__", args.name).replace("__TEAM__", args.team),
    }

    if args.dry_run:
        for f in files:
            print(f"would write {os.path.relpath(os.path.join(out, f), BASE)}")
        return

    if os.path.exists(out):
        sys.exit(f"already exists: {os.path.relpath(out, BASE)}")
    os.makedirs(out)
    for fname, content in files.items():
        with open(os.path.join(out, fname), "w", encoding="utf-8") as fh:
            fh.write(content)
    print(f"created {os.path.relpath(out, BASE)} ({len(files)} files)")


if __name__ == "__main__":
    main()
