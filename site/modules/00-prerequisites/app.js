var STEP = "00";
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

function buildNav() {
  var html = '<span class="nav-title">Steps</span>';
  for (var i = 0; i < STEPS.length; i++) {
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
    for (var i = 0; i < text.length; i++) {
      var li = document.createElement('li');
      li.textContent = text[i];
      ul.appendChild(li);
    }
    box.appendChild(ul);
  } else {
    box.textContent = text;
  }
}

function readForm() {
  var form = document.getElementById("config-form");
  var data = {};
  var els = form.elements;
  for (var i = 0; i < els.length; i++) {
    var f = els[i];
    if (!f.name) { continue; }
    if (f.type === "radio") {
      if (f.checked) { data[f.name] = f.value; }
    } else if (f.type === "checkbox") {
      data[f.name] = f.checked;
    } else {
      data[f.name] = f.value;
    }
  }
  return data;
}

function validate(data) {
  var errors = [];
  if (parseInt(data.cephOsdHosts, 10) < 3) {
    errors.push("Ceph OSD hosts must be ≥ 3 for a 3-replica pool.");
  }
  if (parseInt(data.mgmtCpHosts, 10) % 2 === 0) {
    errors.push("Management control-plane count should be odd (1/3/5) for quorum.");
  }
  if (parseInt(data.appCpHosts, 10) % 2 === 0) {
    errors.push("Application control-plane count should be odd (1/3/5) for quorum.");
  }
  if (parseInt(data.edgeHosts, 10) < 2) {
    errors.push("Edge load balancer needs ≥ 2 hosts for VIP failover.");
  }
  return errors;
}

function renderConfig(data) {
  var out = '{';
  out += '\n  "step": "00",';
  out += '\n  "deploymentModel": "' + data.deploymentModel + '",';
  out += '\n  "hosts": {';
  out += '\n    "automation": ' + parseInt(data.automationHosts, 10) + ',';
  out += '\n    "mgmtControlPlane": ' + parseInt(data.mgmtCpHosts, 10) + ',';
  out += '\n    "appControlPlane": ' + parseInt(data.appCpHosts, 10) + ',';
  out += '\n    "appWorkers": ' + parseInt(data.appWorkers, 10) + ',';
  out += '\n    "cephOsd": ' + parseInt(data.cephOsdHosts, 10) + ',';
  out += '\n    "artifact": ' + parseInt(data.artifactHosts, 10) + ',';
  out += '\n    "edge": ' + parseInt(data.edgeHosts, 10) + '';
  out += '\n  },';
  out += '\n  "network": {';
  out += '\n    "mgmt": "' + data.cidrMgmt + '",';
  out += '\n    "controlPlane": "' + data.cidrCp + '",';
  out += '\n    "storagePublic": "' + data.cidrStoragePublic + '",';
  out += '\n    "storageCluster": "' + data.cidrStorageCluster + '",';
  out += '\n    "dmz": "' + data.cidrDmz + '"';
  out += '\n  },';
  out += '\n  "airGap": ' + (data.airGap === "true" || data.airGap === true) + '';
  out += '\n}';
  return out;
}

function downloadConfig(data) {
  var blob = new Blob([renderConfig(data)], { type: "application/json" });
  var url = URL.createObjectURL(blob);
  var a = document.createElement('a');
  a.href = url;
  a.download = "step00-prerequisites-config.json";
  a.click();
  URL.revokeObjectURL(url);
}

window.onload = function() {
  document.getElementById("step-nav").innerHTML = buildNav();
  document.getElementById("validate").onclick = function() {
    var data = readForm();
    var errors = validate(data);
    if (errors.length) {
      msg(errors, "error");
    } else {
      msg(["Configuration valid. Host counts, quorum parity, and edge HA checked."], "ok");
      document.getElementById("config-output").textContent = renderConfig(data);
    }
  };
  document.getElementById("download").onclick = function() {
    var data = readForm();
    var errors = validate(data);
    if (errors.length) {
      msg(errors, "error");
      return;
    }
    downloadConfig(data);
  };
};
