var STEP = "08";
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
  var edge = parseInt(data.edgeHosts, 10);
  if (isNaN(edge) || edge < 2) {
    errors.push("Edge hosts must be ≥ 2 for VIP failover.");
  }
  if (!data.vip || !/^\d{1,3}(\.\d{1,3}){3}$/.test(data.vip)) {
    errors.push("VIP must be a valid IPv4 address in the dmz segment.");
  }
  if (!data.ingressController) {
    errors.push("Ingress controller is required.");
  }
  if (!data.metallbPool) {
    errors.push("MetalLB address pool CIDR is required.");
  }
  return errors;
}

function renderConfig(data) {
  var out = '{';
  out += '\n  "step": "08",';
  out += '\n  "edge": {';
  out += '\n    "hosts": ' + parseInt(data.edgeHosts, 10) + ',';
  out += '\n    "vip": "' + data.vip + '"';
  out += '\n  },';
  out += '\n  "loadBalancer": {';
  out += '\n    "haproxy": ' + (data.haproxy === "true" || data.haproxy === true) + ',';
  out += '\n    "nginx": ' + (data.nginx === "true" || data.nginx === true) + ',';
  out += '\n    "keepalived": ' + (data.keepalived === "true" || data.keepalived === true) + '';
  out += '\n  },';
  out += '\n  "ingress": {';
  out += '\n    "controller": "' + data.ingressController + '",';
  out += '\n    "hostnameSuffix": "' + data.hostnameSuffix + '"';
  out += '\n  },';
  out += '\n  "metallb": {';
  out += '\n    "enabled": ' + (data.metallb === "true" || data.metallb === true) + ',';
  out += '\n    "poolCidr": "' + data.metallbPool + '"';
  out += '\n  }';
  out += '\n}';
  return out;
}

function downloadConfig(data) {
  var blob = new Blob([renderConfig(data)], { type: "application/json" });
  var url = URL.createObjectURL(blob);
  var a = document.createElement('a');
  a.href = url;
  a.download = "step08-traffic-edge-config.json";
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
      msg(["Configuration valid. Edge HA, VIP, ingress and MetalLB pool ready."], "ok");
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
