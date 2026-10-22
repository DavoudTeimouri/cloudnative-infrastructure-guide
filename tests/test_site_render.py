#!/usr/bin/env python3
"""Render site/app.js against a DOM stub and assert what the page shows.

A static asset check cannot catch a renderer that throws on load — that is how
the exports shape bug reached production once. This boots the real app.js in
dukpy (Duktape, ES5) with a minimal DOM and drives it through the wizard, the
review page and the upgrade walkthrough.

Skips with exit code 0 when dukpy is not installed. CI installs it.
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
  this.hidden = false;
  this.disabled = false;
  this.value = "";
  this.checked = false;
  var self = this;
  this.classList = {
    add: function (c) {
      if (self.className.indexOf(c) === -1) self.className = (self.className + " " + c).trim();
    },
    remove: function (c) {
      self.className = self.className.split(/\s+/).filter(function (x) { return x && x !== c; }).join(" ");
    },
    contains: function (c) { return self.className.split(/\s+/).indexOf(c) !== -1; }
  };
}
Node.prototype.appendChild = function (c) { this.children.push(c); return c; };
Node.prototype.removeChild = function (c) {
  var i = this.children.indexOf(c);
  if (i >= 0) this.children.splice(i, 1);
};
Node.prototype.setAttribute = function (k, v) { if (k === "value") this.value = v; };
Node.prototype.getAttribute = function (k) {
  return (k === "data-view" || k === "value") ? this[k] : "";
};
Node.prototype.addEventListener = function (ev, fn) {
  if (ev === "click") this.onclick = fn;
  if (ev === "change") this.onchange = fn;
  if (ev === "input") this.oninput = fn;
};
Node.prototype.select = function () {};
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
Object.defineProperty(Node.prototype, "childNodes", {
  get: function () { return this.children; }
});
Object.defineProperty(Node.prototype, "firstChild", {
  get: function () { return this.children.length ? this.children[0] : null; }
});
Object.defineProperty(Node.prototype, "textContent", {
  get: function () {
    var out = this._text;
    for (var i = 0; i < this.children.length; i++) out += this.children[i].textContent;
    return out;
  },
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
  querySelector: function (sel) { return __byId[sel] || new Node(sel); },
  querySelectorAll: function () { return []; },
  body: new Node("body"),
  documentElement: new Node("html")
};
var navigator = {};
var window = {
  location: { hash: "" },
  addEventListener: function () {},
  scrollTo: function () {}
};
/* The page's fetch bootstrap is replaced by an explicit boot() call below. */
function fetch() {
  var noop = { then: function () { return noop; }, "catch": function () { return noop; } };
  return noop;
}
function Blob() {}
function URL() {}
"""


def run(data):
    import dukpy

    app = open(APP, encoding="utf-8").read()
    js = DOM_SHIM + "var DATA = " + json.dumps(data) + ";\n" + app + r"""
var __g = window.__guide;
__g.boot(DATA);

function texts(list) {
  var out = [];
  for (var i = 0; i < list.length; i++) out.push(list[i].textContent);
  return out;
}
function filenames() {
  var out = [];
  var cards = __byId["exports"].children;
  for (var i = 0; i < cards.length; i++) {
    var kids = cards[i].children;
    for (var j = 0; j < kids.length; j++) {
      if (kids[j].className === "fname") out.push(kids[j].textContent);
    }
  }
  return out;
}
function exportBodies() {
  var out = [];
  var cards = __byId["exports"].children;
  for (var i = 0; i < cards.length; i++) {
    var kids = cards[i].children;
    for (var j = 0; j < kids.length; j++) {
      if (kids[j].tagName === "pre") out.push(kids[j].textContent);
    }
  }
  return out;
}

var page1 = __byId["page"].textContent;
__g.gotoPage(1);
var page2 = __byId["page"].textContent;
__g.gotoPage(7);
__g.renderReview();

var base = {
  pages: DATA.pages.length,
  page1HasMethod: page1.indexOf("Bare metal") !== -1,
  page2HasNodes: page2.indexOf("k8s-cp-1") !== -1 && page2.indexOf("10.20.0.11") !== -1,
  reviewSteps: __byId["steps"].children.length,
  reviewExports: __byId["exports"].children.length,
  files: filenames(),
  sizingRows: __byId["sizing"].querySelector("tbody").children.length,
  versions: __byId["versions"].querySelector("tbody").children.length,
  runbook: __g.buildRunbook()
};

// Flip the interesting selections and re-render.
__g.state.choices.gpu = "mig";
__g.state.choices.storage = "cephadm-docker";
__g.state.choices.serviceMesh = "istio-ambient";
__g.state.choices.idpIntegration = ["keycloak-federation", "harbor-oidc"];
__g.renderReview();

var flipped = {
  files: filenames(),
  reviewSteps: __byId["steps"].children.length,
  bodiesJoined: exportBodies().join("\n"),
  derived: __g.derived()
};

// Upgrade walkthrough.
__g.renderUpgrade();
var upFirst = __byId["upgrade-body"].textContent;
__g.state.upgrade.flow = "kubernetes";
__g.renderUpgrade();
var upK8s = __byId["upgrade-body"].textContent;
var upRunbook = __g.buildUpgradeRunbook();

JSON.stringify({
  base: { pages: base.pages, page1HasMethod: base.page1HasMethod, page2HasNodes: base.page2HasNodes,
          reviewSteps: base.reviewSteps, reviewExports: base.reviewExports, files: base.files,
          sizingRows: base.sizingRows, versions: base.versions,
          runbookLeftovers: (base.runbook.match(/\{\{/g) || []).length,
          runbookHasSizing: base.runbook.indexOf("## Sizing") !== -1 },
  flipped: { files: flipped.files, reviewSteps: flipped.reviewSteps,
             hasCephDocker: flipped.bodiesJoined.indexOf("--docker") !== -1,
             hasCephHost: flipped.bodiesJoined.indexOf("ceph-1") !== -1,
             hasIstio: flipped.bodiesJoined.indexOf("PeerAuthentication") !== -1,
             hasIdp: flipped.bodiesJoined.indexOf("Keycloak — LDAP/AD user federation") !== -1,
             engine: flipped.derived.cephEngine,
             gpuNodes: flipped.derived.gpuHostList },
  upgrade: { firstSteps: upFirst.split("gate").length - 1,
             k8sHasCommand: upK8s.indexOf("ansible-playbook") !== -1,
             k8sHasGate: upK8s.indexOf("gate") !== -1,
             runbookLeftovers: (upRunbook.match(/\{\{/g) || []).length,
             runbookHasRollback: upRunbook.indexOf("Rollback:") !== -1 }
});
"""

    raw = dukpy.evaljs(js)
    return json.loads(raw)


def main():
    try:
        import dukpy  # noqa: F401
    except ImportError:
        print("SKIP: dukpy not installed (pip install dukpy to run the render check)")
        return 0

    data = json.load(open(DATA, encoding="utf-8"))
    result = run(data)
    failures = []

    base = result["base"]
    expected_steps = len([s for s in data["steps"] if not s.get("when")])
    if base["pages"] != len(data["pages"]):
        failures.append(f"pages: expected {len(data['pages'])}, got {base['pages']}")
    if not base["page1HasMethod"]:
        failures.append("page 1 does not render the deployment methods")
    if not base["page2HasNodes"]:
        failures.append("page 2 does not render the generated node list")
    if base["reviewSteps"] != expected_steps:
        failures.append(f"default steps: expected {expected_steps}, got {base['reviewSteps']}")
    if not base["sizingRows"]:
        failures.append("sizing table is empty")
    if base["versions"] < 5:
        failures.append(f"version table too short: {base['versions']}")
    if base["runbookLeftovers"]:
        failures.append(f"runbook has {base['runbookLeftovers']} unresolved placeholders")
    if not base["runbookHasSizing"]:
        failures.append("runbook has no sizing section")
    if not base["files"]:
        failures.append("no export cards rendered")

    flipped = result["flipped"]
    for wanted in ("ceph-bootstrap.sh", "peer-authentication.yaml", "idp-integration.md"):
        if wanted not in flipped["files"]:
            failures.append(f"selection change did not reveal {wanted}")
    if flipped["engine"] != "docker":
        failures.append(f"ceph engine: expected docker, got {flipped['engine']}")
    if not flipped["hasCephDocker"]:
        failures.append("ceph bootstrap does not carry --docker")
    if not flipped["hasIstio"]:
        failures.append("istio policy body missing after selecting the mesh")
    if not flipped["hasIdp"]:
        failures.append("idp checklist does not list the selected integration")
    if flipped["reviewSteps"] <= base["reviewSteps"]:
        failures.append("selecting mesh/gpu/idp did not add steps")

    up = result["upgrade"]
    if up["runbookLeftovers"]:
        failures.append(f"upgrade runbook has {up['runbookLeftovers']} unresolved placeholders")
    if not up["k8sHasCommand"]:
        failures.append("kubernetes flow does not render its command")
    if not up["k8sHasGate"]:
        failures.append("kubernetes flow lost its gate marker")
    if not up["runbookHasRollback"]:
        failures.append("upgrade runbook has no rollback line")

    print(f"OK   base: {base['pages']} pages, {base['reviewSteps']} steps, "
          f"{len(base['files'])} files, {base['sizingRows'] - 2} sizing rows")
    print(f"OK   flipped: {len(flipped['files'])} files, engine {flipped['engine']}, "
          f"gpu {flipped['gpuNodes'] or 'none'}")
    print(f"OK   upgrade: {len(data['upgrades'])} flows, first gate markers {up['firstSteps']}")

    if failures:
        for f in failures:
            print("FAIL", f)
        return 1
    print("All render checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
