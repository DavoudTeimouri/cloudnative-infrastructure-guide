var STEP = "06";
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
  if (!data.rancher && !data.argocd && !data.keycloak && !data.vault) {
    errors.push("Enable at least one management component.");
  }
  var rancher = parseInt(data.rancherReplicas, 10);
  var vault = parseInt(data.vaultNodes, 10);
  var keycloak = parseInt(data.keycloakReplicas, 10);
  if (isNaN(rancher) || rancher < 1) { errors.push("Rancher replicas must be ≥ 1."); }
  if (rancher % 2 === 0) { errors.push("Rancher replicas should be odd (1/3/5) for HA."); }
  if (isNaN(vault) || vault < 1) { errors.push("Vault nodes must be ≥ 1."); }
  if (vault % 2 === 0) { errors.push("Vault nodes should be odd (1/3/5) for Raft quorum."); }
  if (isNaN(keycloak) || keycloak < 1) { errors.push("Keycloak replicas must be ≥ 1."); }
  if (data.unsealKeyOffline !== "true" && data.unsealKeyOffline !== true) {
    errors.push("Vault unseal key must be stored offline (break-glass).");
  }
  if (!data.keycloakRealm) {
    errors.push("Keycloak realm is required.");
  }
  return errors;
}

function renderConfig(data) {
  var out = '{';
  out += '\n  "step": "06",';
  out += '\n  "components": {';
  out += '\n    "rancher": ' + (data.rancher === "true" || data.rancher === true) + ',';
  out += '\n    "argocd": ' + (data.argocd === "true" || data.argocd === true) + ',';
  out += '\n    "keycloak": ' + (data.keycloak === "true" || data.keycloak === true) + ',';
  out += '\n    "vault": ' + (data.vault === "true" || data.vault === true) + '';
  out += '\n  },';
  out += '\n  "ha": {';
  out += '\n    "rancherReplicas": ' + parseInt(data.rancherReplicas, 10) + ',';
  out += '\n    "vaultNodes": ' + parseInt(data.vaultNodes, 10) + ',';
  out += '\n    "keycloakReplicas": ' + parseInt(data.keycloakReplicas, 10) + ',';
  out += '\n    "unsealKeyOffline": ' + (data.unsealKeyOffline === "true" || data.unsealKeyOffline === true) + '';
  out += '\n  },';
  out += '\n  "identity": {';
  out += '\n    "realm": "' + data.keycloakRealm + '",';
  out += '\n    "userFederation": "' + data.userFederation + '"';
  out += '\n  }';
  out += '\n}';
  return out;
}

function downloadConfig(data) {
  var blob = new Blob([renderConfig(data)], { type: "application/json" });
  var url = URL.createObjectURL(blob);
  var a = document.createElement('a');
  a.href = url;
  a.download = "step06-management-cluster-config.json";
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
      msg(["Configuration valid. Components, HA quorum parity and break-glass unseal key ready."], "ok");
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
