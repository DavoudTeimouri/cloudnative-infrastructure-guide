/* Ceph cluster configurator — ES5 only (no let/const/arrow/template literals) */

(function () {
  "use strict";

  var ROLES = ["mon", "mgr", "osd", "mds", "rgw"];
  var ROLE_LABEL = {
    mon: "MON (monitor)",
    mgr: "MGR (manager)",
    osd: "OSD (storage)",
    mds: "MDS (CephFS)",
    rgw: "RGW (S3)"
  };

  var state = {
    nodes: [],   // array of {name, ip, roles: {...}}
    pools: []    // array of {name, type, replicas, pg, app}
  };

  var el = function (tag, attrs, children) {
    var e = document.createElement(tag);
    var k;
    for (k in attrs) {
      if (attrs.hasOwnProperty(k)) {
        if (attrs[k] === false) continue;
        e.setAttribute(k, String(attrs[k]));
      }
    }
    if (children) {
      var i;
      for (i = 0; i < children.length; i++) {
        if (typeof children[i] === "string") {
          e.appendChild(document.createTextNode(children[i]));
        } else {
          e.appendChild(children[i]);
        }
      }
    }
    return e;
  };

  var byId = function (id) {
    return document.getElementById(id);
  };

  var clear = function (e) {
    while (e.firstChild) e.removeChild(e.firstChild);
  };

  var escapeHtml = function (s) {
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  };

  /* ---------- validation ---------- */

  var validate = function () {
    var errors = [];
    var i, j, r, node, roleCount, monCount, osdHosts, mgrCount, hasRole;

    // every node needs a name and at least one role
    for (i = 0; i < state.nodes.length; i++) {
      node = state.nodes[i];
      if (!node.name || node.name.replace(/\s/g, "").length === 0) {
        errors.push("Node #" + (i + 1) + " needs a name.");
      }
      hasRole = false;
      for (r in ROLES) {
        if (ROLES.hasOwnProperty(r)) {
          if (node.roles[ROLES[r]]) hasRole = true;
        }
      }
      if (!hasRole) {
        errors.push("Node '" + escapeHtml(node.name) + "' needs at least one role.");
      }
      // co-location: MON + OSD on same host only allowed when >= 3 hosts exist
      if (node.roles.mon && node.roles.osd && state.nodes.length < 3) {
        errors.push("Node '" + escapeHtml(node.name) + "': MON and OSD on the same host requires at least 3 hosts.");
      }
    }

    // role counts
    monCount = 0;
    osdHosts = 0;
    mgrCount = 0;
    for (i = 0; i < state.nodes.length; i++) {
      node = state.nodes[i];
      if (node.roles.mon) monCount++;
      if (node.roles.osd) osdHosts++;
      if (node.roles.mgr) mgrCount++;
    }

    if (monCount > 0 && monCount % 2 === 0) {
      errors.push("MON count must be odd (3, 5, ...). Current: " + monCount + ".");
    }
    if (monCount > 0 && monCount < 3) {
      errors.push("MON count must be at least 3 for quorum. Current: " + monCount + ".");
    }
    if (osdHosts > 0 && osdHosts < 3) {
      errors.push("At least 3 OSD hosts are required for a 3-replica pool. Current OSD hosts: " + osdHosts + ".");
    }
    if (mgrCount < 1) {
      errors.push("At least 1 MGR host is required.");
    }

    // duplicate names
    var names = {};
    for (i = 0; i < state.nodes.length; i++) {
      names[state.nodes[i].name] = (names[state.nodes[i].name] || 0) + 1;
    }
    for (r in names) {
      if (names.hasOwnProperty(r) && names[r] > 1) {
        errors.push("Duplicate node name: '" + escapeHtml(r) + "'.");
      }
    }

    return errors;
  };

  var renderValidation = function (errors) {
    var box = byId("validation");
    var dl = byId("download-config");
    if (errors.length === 0) {
      box.innerHTML = '<p class="ok">Configuration is valid.</p>';
      dl.disabled = false;
      return true;
    }
    var html = '<ul>';
    var i;
    for (i = 0; i < errors.length; i++) {
      html += '<li>' + escapeHtml(errors[i]) + '</li>';
    }
    html += '</ul>';
    box.innerHTML = html;
    dl.disabled = true;
    return false;
  };

  /* ---------- node editor ---------- */

  var roleCheckboxHtml = function (roles) {
    var html = [];
    var r;
    for (r = 0; r < ROLES.length; r++) {
      var role = ROLES[r];
      var checked = roles[role] ? ' checked="checked"' : '';
      html.push('<label style="margin-right:10px;"><input type="checkbox" class="role-chk" data-role="' + role + '"' + checked + '> ' + ROLE_LABEL[role] + '</label>');
    }
    return html.join('');
  };

  var renderNodeEditor = function () {
    var container = byId("node-list");
    clear(container);
    var i, node, row, nameInput, ipInput, rolesCell, removeBtn;

    for (i = 0; i < state.nodes.length; i++) {
      node = state.nodes[i];
      row = el("div", {class: "node-row"});

      nameInput = el("input", {type: "text", value: node.name, placeholder: "ceph-mon-1"});
      nameInput.setAttribute("data-index", String(i));
      nameInput.onchange = (function (idx) {
        return function () {
          state.nodes[idx].name = this.value;
          renderNodeEditor();
          validateAndRender();
        };
      })(i);

      ipInput = el("input", {type: "text", value: node.ip || "", placeholder: "10.40.0.11"});
      ipInput.setAttribute("data-index", String(i));
      ipInput.onchange = (function (idx) {
        return function () {
          state.nodes[idx].ip = this.value;
          renderNodeEditor();
          validateAndRender();
        };
      })(i);

      rolesCell = el("div", {class: "roles"});
      rolesCell.innerHTML = roleCheckboxHtml(node.roles);
      var r;
      for (r = 0; r < ROLES.length; r++) {
        (function (idx, role) {
          var cbs = rolesCell.querySelectorAll('input[data-role="' + role + '"]');
          var k;
          for (k = 0; k < cbs.length; k++) {
            cbs[k].onchange = (function (i2, r2) {
              return function () {
                state.nodes[i2].roles[r2] = this.checked;
                validateAndRender();
              };
            })(idx, role);
          }
        })(i, ROLES[r]);
      }

      removeBtn = el("button", {type: "button", class: "remove-node", "data-index": String(i)}, ["×"]);
      removeBtn.onclick = (function (idx) {
        return function () {
          state.nodes.splice(idx, 1);
          renderNodeEditor();
          validateAndRender();
        };
      })(i);

      row.appendChild(el("label", {}, ["Name"]));
      row.appendChild(nameInput);
      row.appendChild(el("label", {}, ["IP"]));
      row.appendChild(ipInput);
      row.appendChild(el("label", {}, ["Roles"]));
      row.appendChild(rolesCell);
      row.appendChild(removeBtn);
      container.appendChild(row);
    }

    var btnAdd = byId("add-node");
    var btnRem = byId("remove-node");
    btnRem.disabled = state.nodes.length === 0;
  };

  var addNode = function () {
    var name = "ceph-node-" + (state.nodes.length + 1);
    var roles = {};
    var r;
    for (r = 0; r < ROLES.length; r++) {
      roles[ROLES[r]] = false;
    }
    state.nodes.push({name: name, ip: "", roles: roles});
    renderNodeEditor();
    validateAndRender();
  };

  var removeLastNode = function () {
    if (state.nodes.length > 0) {
      state.nodes.pop();
      renderNodeEditor();
      validateAndRender();
    }
  };

  /* ---------- pools ---------- */

  var renderPools = function () {
    var tbody = byId("pool-list");
    clear(tbody);
    var i, p, row, cells = ["name", "type", "replicas", "pg", "app"], c;

    for (i = 0; i < state.pools.length; i++) {
      p = state.pools[i];
      row = el("tr", {});
      var ci;
      for (ci = 0; ci < cells.length; ci++) {
        var cell = el("td", {});
        var field = cells[ci];
        var inp;
        if (field === "type") {
          inp = el("select", {});
          var optRep = el("option", {value: "replicated"}, ["replicated"]);
          var optEc = el("option", {value: "erasure"}, ["erasure"]);
          inp.appendChild(optRep);
          inp.appendChild(optEc);
          inp.value = p.type || "replicated";
          inp.onchange = (function (idx, f) {
            return function () {
              state.pools[idx][f] = this.value;
              validateAndRender();
            };
          })(i, field);
        } else {
          inp = el("input", {type: "text", value: p[field] || ""});
          inp.onchange = (function (idx, f) {
            return function () {
              state.pools[idx][f] = this.value;
              validateAndRender();
            };
          })(i, field);
        }
        cell.appendChild(inp);
        row.appendChild(cell);
      }
      var rmCell = el("td", {});
      var rmBtn = el("button", {type: "button", "data-index": String(i)}, ["×"]);
      rmBtn.onclick = (function (idx) {
        return function () {
          state.pools.splice(idx, 1);
          renderPools();
          validateAndRender();
        };
      })(i);
      rmCell.appendChild(rmBtn);
      row.appendChild(rmCell);
      tbody.appendChild(row);
    }

    var btnAdd = byId("add-pool");
    var btnRem = byId("remove-pool");
    btnRem.disabled = state.pools.length <= 1;
  };

  var addPool = function () {
    state.pools.push({name: "pool-" + (state.pools.length + 1), type: "replicated", replicas: "3", pg: "512", app: "rbd"});
    renderPools();
    validateAndRender();
  };

  var removeLastPool = function () {
    if (state.pools.length > 1) {
      state.pools.pop();
      renderPools();
      validateAndRender();
    }
  };

  /* ---------- config generation ---------- */

  var generateConfig = function () {
    var config = {
      catalogVersion: "3.3.0",
      cluster: {
        name: "ceph",
        fsid: "[REDACTED]"
      },
      nodes: [],
      pools: [],
      engine: "podman",
      registry: "harbor.internal",
      generated: new Date().toISOString()
    };
    var i, n;
    for (i = 0; i < state.nodes.length; i++) {
      n = state.nodes[i];
      var nodeRoles = [];
      var r;
      for (r = 0; r < ROLES.length; r++) {
        if (n.roles[ROLES[r]]) nodeRoles.push(ROLES[r]);
      }
      config.nodes.push({
        name: n.name,
        ip: n.ip,
        roles: nodeRoles
      });
    }
    for (i = 0; i < state.pools.length; i++) {
      var p = state.pools[i];
      config.pools.push({
        name: p.name,
        type: p.type,
        replicas: p.type === "replicated" ? parseInt(p.replicas, 10) || 3 : null,
        erasure: p.type === "erasure" ? p.replicas : null,
        pg: parseInt(p.pg, 10) || 512,
        application: p.app || "rbd"
      });
    }
    return JSON.stringify(config, null, 2);
  };

  var renderConfigOutput = function () {
    var ta = byId("config-output");
    ta.value = generateConfig();
  };

  var validateAndRender = function () {
    var errors = validate();
    renderValidation(errors);
    renderConfigOutput();
  };

  /* ---------- download / copy ---------- */

  var downloadConfig = function () {
    var config = generateConfig();
    var blob = new Blob([config], {type: "application/json"});
    var url = URL.createObjectURL(blob);
    var a = document.createElement("a");
    a.href = url;
    a.download = "ceph-config.json";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  var copyConfig = function () {
    var ta = byId("config-output");
    ta.select();
    try {
      document.execCommand("copy");
    } catch (e) {
      // fallback: nothing
    }
  };

  /* ---------- init ---------- */

  var init = function () {
    // default state: 3 MON + 3 OSD + 1 MGR on separate hosts
    state.nodes = [
      {name: "ceph-mon-1", ip: "10.40.0.11", roles: {mon: true, mgr: false, osd: false, mds: false, rgw: false}},
      {name: "ceph-mon-2", ip: "10.40.0.12", roles: {mon: true, mgr: false, osd: false, mds: false, rgw: false}},
      {name: "ceph-mon-3", ip: "10.40.0.13", roles: {mon: true, mgr: true, osd: false, mds: false, rgw: false}},
      {name: "ceph-osd-1", ip: "10.40.0.14", roles: {mon: false, mgr: false, osd: true, mds: false, rgw: false}},
      {name: "ceph-osd-2", ip: "10.40.0.15", roles: {mon: false, mgr: false, osd: true, mds: false, rgw: false}},
      {name: "ceph-osd-3", ip: "10.40.0.16", roles: {mon: false, mgr: false, osd: true, mds: false, rgw: false}}
    ];
    state.pools = [
      {name: "kube-rbd", type: "replicated", replicas: "3", pg: "512", app: "rbd"}
    ];

    byId("add-node").onclick = addNode;
    byId("remove-node").onclick = removeLastNode;
    byId("add-pool").onclick = addPool;
    byId("remove-pool").onclick = removeLastPool;
    byId("download-config").onclick = downloadConfig;
    byId("copy-config").onclick = copyConfig;

    renderNodeEditor();
    renderPools();
    validateAndRender();
  };

  init();

})();
