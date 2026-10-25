var STEP = "05";
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

function readForm() {
  var form = document.getElementById("config-form");
  var data = {};
  var els = form.elements;
  var i;
  for (i = 0; i < els.length; i++) {
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
  if (!data.kubesprayRelease) {
    errors.push("Kubespray release is required.");
  }
  if (!data.imageRegistry) {
    errors.push("Container image registry is required.");
  }
  var cp = parseInt(data.cpNodes, 10);
  var etcd = parseInt(data.etcdNodes, 10);
  var workers = parseInt(data.workerNodes, 10);
  if (isNaN(cp) || cp < 1) { errors.push("Control plane nodes must be ≥ 1."); }
  if (cp % 2 === 0) { errors.push("Control plane count should be odd (1/3/5) for quorum."); }
  if (isNaN(etcd) || etcd < 1) { errors.push("etcd nodes must be ≥ 1."); }
  if (etcd % 2 === 0) { errors.push("etcd count should be odd (1/3/5) for quorum."); }
  if (etcd > cp) { errors.push("etcd nodes must not exceed control-plane nodes."); }
  if (isNaN(workers) || workers < 1) { errors.push("Worker nodes must be ≥ 1."); }
  if (!data.podCidr || !data.serviceCidr) {
    errors.push("Pod CIDR and Service CIDR are required.");
  }
  return errors;
}

function renderConfig(data) {
  var out = '{';
  out += '\n  "step": "05",';
  out += '\n  "kubesprayRelease": "' + data.kubesprayRelease + '",';
  out += '\n  "imageRegistry": "' + data.imageRegistry + '",';
  out += '\n  "containerManager": "' + data.containerManager + '",';
  out += '\n  "nodes": {';
  out += '\n    "controlPlane": ' + parseInt(data.cpNodes, 10) + ',';
  out += '\n    "workers": ' + parseInt(data.workerNodes, 10) + ',';
  out += '\n    "etcd": ' + parseInt(data.etcdNodes, 10) + '';
  out += '\n  },';
  out += '\n  "networking": {';
  out += '\n    "cilium": ' + (data.cilium === "true" || data.cilium === true) + ',';
  out += '\n    "metallb": ' + (data.metallb === "true" || data.metallb === true) + ',';
  out += '\n    "corednsForward": ' + (data.corednsForward === "true" || data.corednsForward === true) + ',';
  out += '\n    "podCidr": "' + data.podCidr + '",';
  out += '\n    "serviceCidr": "' + data.serviceCidr + '"';
  out += '\n  }';
  out += '\n}';
  return out;
}

function downloadConfig(data) {
  var blob = new Blob([renderConfig(data)], { type: "application/json" });
  var url = URL.createObjectURL(blob);
  var a = document.createElement('a');
  a.href = url;
  a.download = "step05-kubernetes-config.json";
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
      msg(["Configuration valid. Kubespray release, node counts, quorum parity and networking ready."], "ok");
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
