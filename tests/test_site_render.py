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

// Add-ons: the optional page must add steps, files and runbook rows.
__g.state.choices.certManager = "vault-pki";
__g.state.choices.metricsServer = "standalone";
__g.state.choices.vpa = "auto";
__g.state.choices.externalDns = "rfc2136";
__g.gotoPage(8);
var addonPage = __byId["page"].textContent;
__g.renderReview();
var addons = {
  files: filenames(),
  bodies: exportBodies().join("\n"),
  steps: __byId["steps"].children.length,
  runbook: __g.buildRunbook(),
  pageHasAddons: addonPage.indexOf("cert-manager") !== -1,
  pageCount: __byId["page-count"] ? __byId["page-count"].textContent : ""
};

// The + button adds a cluster with its own defaults; Remove takes it away.
function findAll(root, pred, out) {
  out = out || [];
  for (var i = 0; i < root.children.length; i++) {
    var k = root.children[i];
    if (pred(k)) out.push(k);
    findAll(k, pred, out);
  }
  return out;
}
__g.gotoPage(1);
var addBtn = findAll(__byId["page"], function (n) {
  return (n.tagName === "button" || n.tagName === "BUTTON") &&
    n.textContent.indexOf("Add application cluster") !== -1;
})[0];
var plus = { found: !!addBtn, count: 0, name: "", pod: "", svc: "", afterRemove: -1 };
if (addBtn) {
  addBtn.onclick();
  var ac = __g.state.values.appClusters || [];
  plus.count = ac.length;
  plus.name = ac[ac.length - 1].name;
  plus.pod = ac[ac.length - 1].pod;
  plus.svc = ac[ac.length - 1].svc;
  var rms = findAll(__byId["page"], function (n) {
    return (n.tagName === "button" || n.tagName === "BUTTON") && n.textContent === "Remove";
  });
  if (rms.length) { rms[rms.length - 1].onclick(); plus.afterRemove = (__g.state.values.appClusters || []).length; }
}

// Windows workers, extra clusters, management alternatives, reservations.
__g.state.choices.windowsNodes = "enabled";
__g.state.choices.management = "headlamp";
__g.state.choices.mgmtStorage = "rook";
var primary = __g.state.values.appClusters[0];
primary.windows = "2";
__g.state.values.appClusters = [primary, { name: "site-b", cp: "3", cpCpu: "8", cpMemGb: "16", cpDiskGb: "120",
                        workers: "4", workerCpu: "16", workerMemGb: "64", workerDiskGb: "200", workerDataDiskGb: "0",
                        windows: "0", windowsCpu: "8", windowsMemGb: "32", windowsDiskGb: "120",
                        pod: "10.130.0.0/16", svc: "10.132.0.0/16" }];
__g.state.values.kubesprayRelease = "release-2.29";
__g.gotoPage(1);
var p2 = __byId["page"].textContent;
__g.renderReview();
__g.gotoPage(3);
var p4 = __byId["page"].textContent;
__g.renderReview();
var v31 = {
  files: filenames(),
  bodies: exportBodies().join("\n"),
  steps: __byId["steps"].children.length,
  runbook: __g.buildRunbook(),
  derived: __g.derived(),
  p2HasWindows: p2.indexOf("Windows worker") !== -1,
  p2HasAddCluster: p2.indexOf("Add application cluster") !== -1,
  p4HasTabs: p4.indexOf("Per-role configuration") !== -1,
  p4HasMaster: p4.indexOf("Master (control plane)") !== -1,
  p4HasOsd: p4.indexOf("Ceph OSD") !== -1,
  p4HasOps: p4.indexOf("Operation server") !== -1,
  p4Json: JSON.stringify(p4 || "")
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
             hasCephHost: flipped.bodiesJoined.indexOf("ceph-mon-1") !== -1,
             hasIstio: flipped.bodiesJoined.indexOf("PeerAuthentication") !== -1,
             hasIdp: flipped.bodiesJoined.indexOf("Keycloak — LDAP/AD user federation") !== -1,
             engine: flipped.derived.cephEngine,
             gpuNodes: flipped.derived.gpuHostList },
  addons: { files: addons.files, steps: addons.steps, pageHasAddons: addons.pageHasAddons,
            pageCount: addons.pageCount,
            hasCert: addons.files.indexOf("cert-manager-values.yaml") !== -1,
            hasIssuer: addons.files.indexOf("cert-manager-issuer.yaml") !== -1,
            hasVpaAuto: addons.files.indexOf("vpa-auto-values.yaml") !== -1,
            hasExtDns: addons.files.indexOf("external-dns-values.yaml") !== -1,
            certInRunbook: addons.runbook.indexOf("cert-manager-values.yaml") !== -1,
            runbookLeftovers: (addons.runbook.match(/\{\{/g) || []).length },
  v31: { files: v31.files, steps: v31.steps, p2HasWindows: v31.p2HasWindows,
          p2HasAddCluster: v31.p2HasAddCluster,
          plus: plus,
          windowsGroup: v31.derived.windowsGroup, k8sVersion: v31.derived.k8sVersion,
          windowsHosts: v31.derived.windowsHosts,
          hasWindowsVars: v31.bodies.indexOf("windows_nodes: true") !== -1,
          hasExtraClusters: v31.bodies.indexOf("site-b") !== -1,
          hasArgocdSecret: v31.bodies.indexOf("argocd.argoproj.io/secret-type: cluster") !== -1,
          hasHeadlamp: v31.files.indexOf("headlamp-values.yaml") !== -1,
          hasMgmtRook: v31.files.indexOf("mgmt-rook-cluster.yaml") !== -1,
          hasReservation: v31.bodies.indexOf("system-reserved") !== -1,
          hasCorefile: v31.bodies.indexOf("forward . ") !== -1,
          hasStorageClass: v31.files.indexOf("storageclass.yaml") !== -1,
          runbookHasWindows: v31.runbook.indexOf("windows") !== -1,
          runbookLeftovers: (v31.runbook.match(/\{\{/g) || []).length,
          windowsCount: v31.derived.windowsCount,
          expectedK8s: DATA.clusterMethods[0].versions["release-2.29"].kubernetes,
          hostRolesYaml: v31.derived.hostRolesYaml,
          p4HasTabs: v31.p4HasTabs,
          p4HasMaster: v31.p4HasMaster,
          p4HasOsd: v31.p4HasOsd,
          p4HasOps: v31.p4HasOps,
          p4Json: JSON.stringify(v31.p4Json || "") },
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
    if "host-config.yaml" not in base["files"]:
        failures.append("host-config.yaml not rendered with default roles")

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

    addons = result["addons"]
    if addons["steps"] <= flipped["reviewSteps"]:
        failures.append("selecting add-ons did not add the add-on step")
    if not addons["pageHasAddons"]:
        failures.append("add-ons page does not render cert-manager")
    if addons["pageCount"] != f"9 / {len(data['pages'])}":
        failures.append(f"page counter wrong on the add-ons page: {addons['pageCount']}")
    for key, name in (("hasCert", "cert-manager-values.yaml"), ("hasIssuer", "cert-manager-issuer.yaml"),
                      ("hasVpaAuto", "vpa-auto-values.yaml"), ("hasExtDns", "external-dns-values.yaml")):
        if not addons[key]:
            failures.append(f"add-on selection did not render {name}")
    if not addons["certInRunbook"]:
        failures.append("runbook does not list the add-on values file")
    if addons["runbookLeftovers"]:
        failures.append(f"add-on runbook has {addons['runbookLeftovers']} unresolved placeholders")

    v31 = result["v31"]
    for wanted in ("windows-vars.yaml", "additional-clusters.yaml", "argocd-cluster-secrets.yaml",
                   "headlamp-values.yaml", "mgmt-rook-cluster.yaml", "storageclass.yaml",
                   "kubelet-reservation.yaml", "coredns-configmap.yaml"):
        if wanted not in v31["files"]:
            failures.append(f"windows/cluster selection did not reveal {wanted}")
    if not v31["hasWindowsVars"]:
        failures.append("windows group vars missing or wrong")
    if not v31["hasExtraClusters"]:
        failures.append("additional cluster record missing")
    if not v31["hasArgocdSecret"]:
        failures.append("argo cd cluster secret missing")
    if "[windows]" not in v31["windowsGroup"]:
        failures.append("windows inventory group missing")
    if v31["windowsCount"] != "2":
        failures.append(f"windows nodes: expected 2, got {v31['windowsCount']}")
    if not v31["runbookHasWindows"]:
        failures.append("runbook has no windows rows")
    if not v31["plus"]["found"]:
        failures.append("+ Add application cluster button not found")
    elif v31["plus"]["count"] != 2 or not v31["plus"]["name"]:
        failures.append(f"add button did not create a cluster: {v31['plus']}")
    elif v31["plus"]["pod"] == v31["plus"]["svc"]:
        failures.append("new cluster pod and service CIDRs are identical")
    elif v31["plus"]["afterRemove"] != 1:
        failures.append("Remove button did not delete the cluster")
    if not v31["p2HasAddCluster"]:
        failures.append("page 2 has no + Add application cluster button")
    if not v31["p2HasWindows"]:
        failures.append("page 2 does not show the windows sizing fields")
    if not v31["hasReservation"]:
        failures.append("kubelet reservation missing from exports")
    if not v31["hasCorefile"]:
        failures.append("coredns Corefile missing from exports")
    if v31["runbookLeftovers"]:
        failures.append(f"windows runbook has {v31['runbookLeftovers']} unresolved placeholders")
    if v31["k8sVersion"] != v31["expectedK8s"]:
        failures.append(f"k8s version {v31['k8sVersion']} does not match release-2.29 ({v31['expectedK8s']})")
    if not v31["p4HasTabs"]:
        failures.append("page 4 has no per-role tabs. p4 text: " + v31.get("p4Json","")[:400])
    if not v31["p4HasMaster"]:
        failures.append("master tab missing")
    if not v31["p4HasOsd"]:
        failures.append("ceph-osd tab missing")
    if not v31["p4HasOps"]:
        failures.append("operation-server tab missing")
    if not v31["hostRolesYaml"]:
        failures.append("host-config export missing roles yaml")
    elif "master:" not in v31["hostRolesYaml"] or "pidMax: 4194304" not in v31["hostRolesYaml"]:
        failures.append("host-config export missing master overrides")

    up = result["upgrade"]
    if up["runbookLeftovers"]:
        failures.append(f"upgrade runbook has {up['runbookLeftovers']} unresolved placeholders")
    if not up["k8sHasCommand"]:
        failures.append("kubernetes flow does not render its command")
    if not up["k8sHasGate"]:
        failures.append("kubernetes flow lost its gate marker")
    if not up["runbookHasRollback"]:
        failures.append("upgrade runbook has no rollback line")

    if failures:
        for f in failures:
            print("FAIL", f)
        return 1

    print(f"OK   base: {base['pages']} pages, {base['reviewSteps']} steps, "
          f"{len(base['files'])} files, {base['sizingRows'] - 2} sizing rows")
    print(f"OK   flipped: {len(flipped['files'])} files, engine {flipped['engine']}, "
          f"gpu {flipped['gpuNodes'] or 'none'}")
    print(f"OK   v31: {len(v31['files'])} files, {v31['steps']} steps, k8s {v31['k8sVersion']}, "
          f"windows {v31['windowsCount']}")
    print(f"OK   add-ons: {addons['steps'] - flipped['reviewSteps']} extra step(s), "
          f"{len(addons['files']) - len(flipped['files'])} extra file(s)")
    print(f"OK   upgrade: {len(data['upgrades'])} flows, first gate markers {up['firstSteps']}")
    print("All render checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
