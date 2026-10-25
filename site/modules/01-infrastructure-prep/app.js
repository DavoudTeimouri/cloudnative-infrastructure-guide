var STEP = "01";
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
  if (!/^\d{1,3}(\.\d{1,3}){3}$/.test(data.mgmtIp)) {
    errors.push("Management server IP must be a valid IPv4 address.");
  }
  if (!data.deployUser) {
    errors.push("Deploy user name is required.");
  }
  if (data.breakGlass !== "true" && data.breakGlass !== true) {
    errors.push("Break-glass key must be installed on all hosts before proceeding.");
  }
  if (!data.ntp1 || !data.ntp2) {
    errors.push("At least two internal NTP sources are required.");
  }
  return errors;
}

function renderConfig(data) {
  var out = '{';
  out += '\n  "step": "01",';
  out += '\n  "mgmtIp": "' + data.mgmtIp + '",';
  out += '\n  "deployUser": "' + data.deployUser + '",';
  out += '\n  "breakGlass": ' + (data.breakGlass === "true" || data.breakGlass === true) + ',';
  out += '\n  "ntp": ["' + data.ntp1 + '", "' + data.ntp2 + '", "' + (data.ntp3 || "") + '"],';
  out += '\n  "dnsMode": "' + data.dnsMode + '"';
  out += '\n}';
  return out;
}

function downloadConfig(data) {
  var blob = new Blob([renderConfig(data)], { type: "application/json" });
  var url = URL.createObjectURL(blob);
  var a = document.createElement('a');
  a.href = url;
  a.download = "step01-infrastructure-prep-config.json";
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
      msg(["Configuration valid. SSH, break-glass, chrony and name resolution ready."], "ok");
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
