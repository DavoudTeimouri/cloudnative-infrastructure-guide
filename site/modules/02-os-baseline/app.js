var STEP = "02";
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
  if (data.os !== "oracle-linux-9" && data.os !== "ubuntu-2404") {
    errors.push("Select a supported OS (Oracle Linux 9 or Ubuntu 24.04).");
  }
  if (data.modBrNetfilter !== "true" && data.modBrNetfilter !== true) {
    errors.push("br_netfilter module is required.");
  }
  if (data.modNfConntrack !== "true" && data.modNfConntrack !== true) {
    errors.push("nf_conntrack module is required.");
  }
  if (data.xfsFtype !== "true" && data.xfsFtype !== true) {
    errors.push("XFS ftype=1 is required for Ceph BlueStore.");
  }
  if (data.noAdJoin !== "true" && data.noAdJoin !== true) {
    errors.push("Hosts must NOT be joined to AD/LDAP (ADR-0015).");
  }
  return errors;
}

function renderConfig(data) {
  var out = '{';
  out += '\n  "step": "02",';
  out += '\n  "os": "' + data.os + '",';
  out += '\n  "kernelModules": {';
  out += '\n    "br_netfilter": ' + (data.modBrNetfilter === "true" || data.modBrNetfilter === true) + ',';
  out += '\n    "nf_conntrack": ' + (data.modNfConntrack === "true" || data.modNfConntrack === true) + ',';
  out += '\n    "rbd": ' + (data.modRbd === "true" || data.modRbd === true) + '';
  out += '\n  },';
  out += '\n  "disks": {';
  out += '\n    "xfsFtype": ' + (data.xfsFtype === "true" || data.xfsFtype === true) + ',';
  out += '\n    "swapDisabled": ' + (data.swapDisabled === "true" || data.swapDisabled === true) + ',';
  out += '\n    "oneOsdPerDisk": ' + (data.oneOsdPerDisk === "true" || data.oneOsdPerDisk === true) + '';
  out += '\n  },';
  out += '\n  "security": {';
  out += '\n    "selinux": ' + (data.selinux === "true" || data.selinux === true) + ',';
  out += '\n    "sshNoPassword": ' + (data.sshNoPassword === "true" || data.sshNoPassword === true) + ',';
  out += '\n    "noAdJoin": ' + (data.noAdJoin === "true" || data.noAdJoin === true) + '';
  out += '\n  }';
  out += '\n}';
  return out;
}

function downloadConfig(data) {
  var blob = new Blob([renderConfig(data)], { type: "application/json" });
  var url = URL.createObjectURL(blob);
  var a = document.createElement('a');
  a.href = url;
  a.download = "step02-os-baseline-config.json";
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
      msg(["Configuration valid. OS baseline, kernel modules, disks and security ready."], "ok");
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
