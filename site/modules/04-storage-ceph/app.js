var STEP = "04";
var TOTAL = 10;
var STEPS = [
  { id: "00", name: "Prerequisites", dir: "00-prerequisites" },
  { id: "01", name: "Infrastructure prep", dir: "01-infrastructure-prep" },
  { id: "02", name: "OS baseline", dir: "02-os-baseline" },
  { id: "03", name: "Container engine", dir: "03-container-engine" },
  { id: "04", name: "Storage — Ceph", dir: "04-storage-ceph" },
  { id: "05", name: "Kubernetes", dir: "05-kubernetes" },
  { id: "06", name: "Management cluster", dir: "06-management-cluster" },
  { id: "07", name: "Application cluster", dir: "07-application-cluster" },
  { id: "08", name: "Traffic edge", dir: "08-traffic-edge" },
  { id: "09", name: "Platform services", dir: "09-platform-services" },
  { id: "10", name: "Backup & upgrade", dir: "10-backup-upgrade" }
];

var ROLES = ["mon", "mgr", "osd", "mds", "rgw"];
var nodes = [
  { name: "ceph-mon-1", roles: ["mon", "mgr"] },
  { name: "ceph-mon-2", roles: ["mon"] },
  { name: "ceph-mon-3", roles: ["mon"] },
  { name: "ceph-osd-1", roles: ["osd"] },
  { name: "ceph-osd-2", roles: ["osd"] },
  { name: "ceph-osd-3", roles: ["osd"] }
];
var pools = [
  { name: "kube-rbd", type: "replicated", replica: 3, pg: 64, app: "rbd" },
  { name: "ec-bulk", type: "erasure", replica: 0, pg: 128, app: "" }
];

function buildNav() {
  var html = '<span class="nav-title">Steps</span>';
  var i;
  for (i = 0; i < STEPS.length; i++) {
    var s = STEPS[i];
    var cls = (s.id === STEP) ? ' class="current"' : '';
    html += '<a href="' + s.dir + '/index.html"' + cls + '>' + s.id + '. ' + s.name + '</a>';
  }
  html += '<a href="../../index.html" class="nav-main">Main site</a>';
  return html;
}

function el(tag, attrs, children) {
  var e = document.createElement(tag);
  var k;
  for (k in attrs) {
    if (attrs.hasOwnProperty(k)) {
      if (attrs[k] === false) { continue; }
      e.setAttribute(k, String(attrs[k]));
    }
  }
  if (children) { e.innerHTML = children; }
  return e;
}

function msg(text, type) {
  var box = document.getElementById("validation");
  box.innerHTML = '';
  box.className = 'msg-box ' + type;
  if (Array.isArray(text)) {
    var ul = document.createElement('ul');
    var i;
    for (i = 0; i < text.length; i++) {
      var li = document.createElement('li');
      li.textContent = text[i];
      ul.appendChild(li);
    }
    box.appendChild(ul);
  } else {
    box.textContent = text;
  }
}

function escapeHtml(t) {
  return String(t).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function roleCheckboxes(selected) {
  var html = '';
  var i;
  var s = selected || [];
  for (i = 0; i < ROLES.length; i++) {
    var r = ROLES[i];
    var checked = (s.indexOf(r) !== -1) ? ' checked' : '';
    html += '<label style="margin-right:10px;font-size:12px;"><input type="checkbox" name="role" value="' + r + '"' + checked + '> ' + r + '</label>';
  }
  return html;
}

function renderNodes() {
  var container = document.getElementById("node-list");
  container.innerHTML = '';
  var i;
  for (i = 0; i < nodes.length; i++) {
    var n = nodes[i];
    var row = el('div', { 'class': 'node-row' });
    var nameInput = el('input', { type: 'text', value: n.name, placeholder: 'Host name' });
    nameInput.style.flex = '1';
    nameInput.style.minWidth = '150px';
    var rolesDiv = el('div', { 'class': 'roles' });
    rolesDiv.innerHTML = roleCheckboxes(n.roles);
    var btn = el('button', { type: 'button', 'class': 'remove-node' }, '×');
    btn.onclick = (function(idx) { return function() { removeNode(idx); }; })(i);
    row.appendChild(nameInput);
    row.appendChild(rolesDiv);
    row.appendChild(btn);
    container.appendChild(row);
  }
}

function renderPools() {
  var container = document.getElementById("pool-list");
  container.innerHTML = '';
  var i;
  for (i = 0; i < pools.length; i++) {
    var p = pools[i];
    var row = el('div', { 'class': 'node-row' });
    var nameInput = el('input', { type: 'text', value: p.name, placeholder: 'Pool name' });
    nameInput.style.flex = '1';
    nameInput.style.minWidth = '120px';
    var typeSelect = el('select', { });
    var opt1 = el('option', { value: 'replicated' }, 'Replicated');
    var opt2 = el('option', { value: 'erasure' }, 'Erasure');
    typeSelect.appendChild(opt1);
    typeSelect.appendChild(opt2);
    typeSelect.value = p.type;
    typeSelect.style.minWidth = '110px';
    var repInput = el('input', { type: 'number', value: p.replica, min: '1' });
    repInput.style.minWidth = '70px';
    var pgInput = el('input', { type: 'number', value: p.pg, min: '1' });
    pgInput.style.minWidth = '70px';
    var btn = el('button', { type: 'button', 'class': 'remove-node' }, '×');
    btn.onclick = (function(idx) { return function() { removePool(idx); }; })(i);
    row.appendChild(nameInput);
    row.appendChild(el('span', {}, ' type:'));
    row.appendChild(typeSelect);
    row.appendChild(el('span', {}, ' replica:'));
    row.appendChild(repInput);
    row.appendChild(el('span', {}, ' PG:'));
    row.appendChild(pgInput);
    row.appendChild(btn);
    container.appendChild(row);
  }
}

function addNode() {
  nodes.push({ name: "ceph-node-" + (nodes.length + 1), roles: [] });
  renderNodes();
}

function removeNode(idx) {
  nodes.splice(idx, 1);
  renderNodes();
}

function addPool() {
  pools.push({ name: "pool-" + (pools.length + 1), type: "replicated", replica: 3, pg: 64, app: "" });
  renderPools();
}

function removePool(idx) {
  pools.splice(idx, 1);
  renderPools();
}

function nextPow2(n) {
  var p = 1;
  while (p < n) { p = p * 2; }
  return p;
}

function validate() {
  var errors = [];
  var engineEls = document.getElementsByName("engine");
  var engine = "";
  var i;
  for (i = 0; i < engineEls.length; i++) {
    if (engineEls[i].checked) { engine = engineEls[i].value; }
  }
  if (engine !== "docker" && engine !== "podman") {
    errors.push("Select a container engine (Docker or Podman).");
  }

  // Re-read nodes from DOM
  var rows = document.querySelectorAll("#node-list .node-row");
  var newNodes = [];
  var monCount = 0;
  var osdHosts = 0;
  var allRoles = {};
  var i;
  for (i = 0; i < rows.length; i++) {
    var row = rows[i];
    var nameInput = row.querySelector('input[type="text"]');
    var roleInputs = row.querySelectorAll('input[name="role"]');
    var roles = [];
    var j;
    for (j = 0; j < roleInputs.length; j++) {
      if (roleInputs[j].checked) { roles.push(roleInputs[j].value); }
    }
    newNodes.push({ name: nameInput.value, roles: roles });
    if (roles.indexOf("mon") !== -1) { monCount++; }
    if (roles.indexOf("osd") !== -1) { osdHosts++; }
    for (j = 0; j < roles.length; j++) {
      if (!allRoles[roles[j]]) { allRoles[roles[j]] = 0; }
      allRoles[roles[j]]++;
    }
  }
  nodes = newNodes;

  if (nodes.length === 0) {
    errors.push("Add at least one Ceph node.");
  }
  if (monCount === 0) {
    errors.push("At least one MON role is required.");
  }
  if (monCount % 2 === 0) {
    errors.push("MON count must be odd (1/3/5) for quorum.");
  }
  if (monCount > 0 && monCount < 3) {
    errors.push("Use 3 MONs for production quorum.");
  }
  if (osdHosts < 3) {
    errors.push("At least 3 OSD hosts are required for a 3-replica pool.");
  }
  if (allRoles.mon && allRoles.mon > 1 && allRoles.mon === nodes.length) {
    errors.push("Do not place all MONs on every host; spread MONs across separate hosts.");
  }

  // Re-read pools from DOM
  var prow = document.querySelectorAll("#pool-list .node-row");
  var newPools = [];
  var totalPg = 0;
  for (i = 0; i < prow.length; i++) {
    var r = prow[i];
    var inputs = r.querySelectorAll('input, select');
    var pName = inputs[0].value;
    var pType = inputs[1].value;
    var pRep = parseInt(inputs[2].value, 10) || 1;
    var pPg = parseInt(inputs[3].value, 10) || 64;
    newPools.push({ name: pName, type: pType, replica: pRep, pg: pPg });
    totalPg += pPg;
  }
  pools = newPools;

  if (pools.length === 0) {
    errors.push("Define at least one Ceph pool.");
  }
  var replicated = 0;
  for (i = 0; i < pools.length; i++) {
    if (pools[i].type === "replicated") { replicated++; }
    var expectedPg = nextPow2(Math.ceil((osdHosts * 100) / (pools[i].replica || 1)));
    if (pools[i].pg < expectedPg) {
      errors.push("Pool '" + pools[i].name + "' PGs (" + pools[i].pg + ") below recommended " + expectedPg + " for " + osdHosts + " OSDs at " + pools[i].replica + "-replica.");
    }
  }
  if (replicated === 0 && osdHosts > 0) {
    errors.push("Add at least one replicated pool (e.g. kube-rbd) for Kubernetes block storage.");
  }

  if (errors.length) {
    msg(errors, "error");
    return false;
  }
  msg(["Configuration valid. Roles, quorum, OSD count and PGs checked."], "ok");
  return true;
}

function renderConfig() {
  var out = '{';
  var engineEls = document.getElementsByName("engine");
  var engine = "";
  var i;
  for (i = 0; i < engineEls.length; i++) {
    if (engineEls[i].checked) { engine = engineEls[i].value; }
  }
  out += '\n  "step": "04",';
  out += '\n  "engine": "' + engine + '",';
  out += '\n  "nodes": [';
  for (i = 0; i < nodes.length; i++) {
    var n = nodes[i];
    out += '\n    { "name": "' + escapeHtml(n.name) + '", "roles": [';
    var j;
    for (j = 0; j < n.roles.length; j++) {
      out += '"' + n.roles[j] + '"';
      if (j < n.roles.length - 1) { out += ', '; }
    }
    out += '] }';
    if (i < nodes.length - 1) { out += ','; }
  }
  out += '\n  ],';
  out += '\n  "pools": [';
  for (i = 0; i < pools.length; i++) {
    var p = pools[i];
    out += '\n    { "name": "' + escapeHtml(p.name) + '", "type": "' + p.type + '", "replica": ' + p.replica + ', "pg": ' + p.pg + ' }';
    if (i < pools.length - 1) { out += ','; }
  }
  out += '\n  ]';
  out += '\n}';
  return out;
}

function downloadConfig() {
  if (!validate()) { return; }
  var blob = new Blob([renderConfig()], { type: "application/json" });
  var url = URL.createObjectURL(blob);
  var a = document.createElement('a');
  a.href = url;
  a.download = "step04-storage-ceph-config.json";
  a.click();
  URL.revokeObjectURL(url);
}

window.onload = function() {
  document.getElementById("step-nav").innerHTML = buildNav();
  renderNodes();
  renderPools();
  document.getElementById("addNode").onclick = addNode;
  document.getElementById("addPool").onclick = addPool;
  document.getElementById("validate").onclick = validate;
  document.getElementById("download").onclick = downloadConfig;
};
