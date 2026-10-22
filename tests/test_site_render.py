#!/usr/bin/env python3
"""Render site/app.js against a DOM stub and assert what the page shows.

A static asset check cannot catch a renderer that throws on load — that is how
the exports object shape bug reached production once. This runs the real
app.js in an embedded JS engine (dukpy) with a minimal DOM, then asserts the
step list and the export cards.

Skips with exit code 0 when dukpy is not installed, so the repository stays
usable without it. CI installs it.
"""
import json
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "site", "data.json")
APP = os.path.join(BASE, "site", "app.js")

DOM_SHIM = r"""
function Node(tag) {
  this.tagName = tag;
  this.children = [];
  this.style = {};
  this._text = "";
  this._html = "";
  this.className = "";
  var self = this;
  this.classList = {
    add: function (c) { if (self.className.indexOf(c) === -1) self.className = (self.className + " " + c).trim(); },
    remove: function (c) { self.className = self.className.split(/\s+/).filter(function (x) { return x && x !== c; }).join(" "); },
    contains: function (c) { return self.className.split(/\s+/).indexOf(c) !== -1; }
  };
}
Node.prototype.appendChild = function (c) { this.children.push(c); return c; };
Node.prototype.removeChild = function (c) {
  var i = this.children.indexOf(c);
  if (i >= 0) this.children.splice(i, 1);
};
Node.prototype.setAttribute = function () {};
Node.prototype.addEventListener = function () {};
Node.prototype.querySelector = function (sel) {
  var found = null;
  (function walk(n) {
    for (var i = 0; i < n.children.length && !found; i++) {
      if (n.children[i].tagName === sel) { found = n.children[i]; return; }
      walk(n.children[i]);
    }
  })(this);
  if (!found) { found = new Node(sel); this.appendChild(found); }
  return found;
};
Object.defineProperty(Node.prototype, "textContent", {
  get: function () { return this._text; },
  set: function (v) { this._text = String(v); }
});
Object.defineProperty(Node.prototype, "innerHTML", {
  get: function () { return this._html; },
  set: function (v) { this._html = String(v); this.children = []; }
});

var __byId = {};
var document = {
  createElement: function (t) { return new Node(t); },
  createTextNode: function (t) { var n = new Node("#text"); n.textContent = t; return n; },
  getElementById: function (id) {
    if (!__byId[id]) __byId[id] = new Node("div#" + id);
    return __byId[id];
  },
  querySelector: function (sel) { return new Node(sel); },
  body: new Node("body"),
  documentElement: new Node("html")
};
var navigator = {};
"""

HARNESS_TAIL = r"""
function countSteps() { return __byId["steps"].children.length; }
function stepTitles() {
  return __byId["steps"].children.map(function (li) {
    var t = "";
    li.children.forEach(function (c) { if (c.className === "step-title") t = c.textContent; });
    return t;
  });
}
function visibleExports() {
  return __byId["exports"].children.filter(function (c) {
    return c.className.indexOf("hidden") === -1;
  }).map(function (c) {
    var name = "", file = "";
    c.children.forEach(function (x) {
      if (x.tagName === "h4" && !name) name = x.textContent;
      if (x.className === "fname" && !file) file = x.textContent;
    });
    return { name: name, file: file };
  });
}
function exportBody(id) {
  var found = null;
  __byId["exports"].children.forEach(function (c) {
    if (c.className.indexOf("hidden") === -1 && !found) {
      c.children.forEach(function (x) {
        if (x.tagName === "pre" && !found) found = x.textContent;
      });
    }
  });
  return found || "";
}
function versionsCount() { return __byId["versions"].querySelector("tbody").children.length; }

__boot(DATA);

var result = {
  steps: countSteps(),
  titles: stepTitles(),
  exports: visibleExports(),
  versions: versionsCount(),
  summary: __byId["plan-summary"].textContent,
  unresolved: (exportBody() .match(/\{\{/g) || []).length
};
"""


def run(data):
    import dukpy

    app = open(APP, encoding="utf-8").read()
    marker = '  fetch("data.json")'
    idx = app.find(marker)
    if idx == -1:
        raise AssertionError("app.js no longer ends with the fetch bootstrap; update the test")
    app = app[:idx] + "  __boot = boot;\n})();\n"

    js = (
        DOM_SHIM
        + "var DATA = " + json.dumps(data) + ";\n"
        + "var __boot = null;\n"
        + app
        + HARNESS_TAIL
        + "JSON.stringify(result);"
    )
    return json.loads(dukpy.evaljs(js))


def main():
    try:
        import dukpy  # noqa: F401
    except ImportError:
        print("SKIP: dukpy not installed (pip install dukpy to run the render check)")
        return 0

    data = json.load(open(DATA, encoding="utf-8"))
    failures = []

    base = run(data)
    expected_steps = len([s for s in data["steps"] if not s.get("when")])
    if base["steps"] != expected_steps:
        failures.append(f"default steps: expected {expected_steps}, got {base['steps']}")
    if any("Istio" in t for t in base["titles"]):
        failures.append("mesh step visible with the default (no mesh) selection")
    if base["unresolved"]:
        failures.append("unresolved template placeholders in the first visible export")
    if base["versions"] < 5:
        failures.append(f"version table too short: {base['versions']}")
    print(f"OK   default render: {base['steps']} steps, {len(base['exports'])} exports, {base['versions']} versions")

    # Switch the mesh on by making it the default option, then boot again.
    mesh_data = json.loads(json.dumps(data))
    for comp in mesh_data["components"]:
        if comp["id"] == "serviceMesh":
            for opt in comp["options"]:
                opt["default"] = opt["id"] == "istio-ambient"
    mesh = run(mesh_data)
    if not any("Istio" in t for t in mesh["titles"]):
        failures.append("mesh step missing when the mesh is selected")
    files = {e["file"] for e in mesh["exports"]}
    for wanted in ("istio-operator.yaml", "peer-authentication.yaml", "istio-gateway.yaml"):
        if wanted not in files:
            failures.append(f"mesh export missing: {wanted}")
    print(f"OK   mesh render: {mesh['steps']} steps, {len(mesh['exports'])} exports")

    # No mesh: the Istio cards must be absent.
    if any(e["file"].startswith("istio") or e["file"] == "peer-authentication.yaml"
           for e in base["exports"]):
        failures.append("Istio exports visible while the mesh is off")

    if failures:
        for f in failures:
            print("FAIL", f)
        return 1
    print("All render checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
