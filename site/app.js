/* Cloud-native infrastructure guide site.
 *
 * Vanilla JS, no build step, no dependencies. The data comes from
 * site/data.json, which scripts/build_site.py generates from
 * catalog/catalog.json and compatibility/version-matrix.md.
 *
 * Everything runs in the browser. Nothing is transmitted.
 */
(function () {
  "use strict";

  var DATA = null;
  var state = { method: null, cluster: null, choices: {}, values: {} };

  /* ------------------------------------------------------------------ */
  /* helpers                                                             */
  /* ------------------------------------------------------------------ */

  function el(tag, attrs, children) {
    var node = document.createElement(tag);
    if (attrs) {
      Object.keys(attrs).forEach(function (k) {
        if (k === "class") node.className = attrs[k];
        else if (k === "text") node.textContent = attrs[k];
        else if (k === "html") node.innerHTML = attrs[k];
        else if (k.slice(0, 2) === "on") node.addEventListener(k.slice(2), attrs[k]);
        else if (attrs[k] !== null && attrs[k] !== undefined) node.setAttribute(k, attrs[k]);
      });
    }
    (children || []).forEach(function (c) {
      if (c === null || c === undefined) return;
      node.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
    });
    return node;
  }

  function $(id) { return document.getElementById(id); }

  function toast(msg) {
    var t = $("toast");
    t.textContent = msg;
    t.classList.add("show");
    clearTimeout(t._timer);
    t._timer = setTimeout(function () { t.classList.remove("show"); }, 2200);
  }

  function download(filename, text) {
    var blob = new Blob([text], { type: "text/plain;charset=utf-8" });
    var url = URL.createObjectURL(blob);
    var a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(function () { URL.revokeObjectURL(url); }, 500);
  }

  function csv(list) {
    return (list || "").split(",").map(function (s) { return s.trim(); }).filter(Boolean);
  }

  function optionOf(componentId) {
    var comp = DATA.components.filter(function (c) { return c.id === componentId; })[0];
    if (!comp) return null;
    var chosen = state.choices[componentId];
    return comp.options.filter(function (o) { return o.id === chosen; })[0] || null;
  }

  function optionTitle(componentId) {
    var o = optionOf(componentId);
    return o ? o.title : "—";
  }

  /* ------------------------------------------------------------------ */
  /* template rendering                                                   */
  /* ------------------------------------------------------------------ */

  function renderTemplate(tpl) {
    var ctx = {
      value: function (id) { return state.values[id] === undefined ? "" : state.values[id]; },
      choice: function (id) {
        if (state.choices[id]) return state.choices[id];
        // The cluster method is selected separately, so choice.kubespray
        // resolves to the active cluster method id.
        var cm = DATA.clusterMethods.filter(function (m) { return m.id === id; })[0];
        return cm && state.cluster === id ? id : "";
      },
      version: function (key) { return DATA.versions[key] || "UNVERIFIED"; },
      controlPlaneNodes: csv(state.values.controlPlaneNodes).join("\n"),
      workerNodes: csv(state.values.workerNodes).join("\n"),
      gpuNodeGroup: (function () {
        var gpus = csv(state.values.gpuNodes);
        if (!gpus.length) return "";
        return "\n[k8s-node:children]\ngpu-node\n\n[gpu-node]\n" + gpus.join("\n");
      })(),
      registryAuth: state.values.registryAuth || "",
      vrrpAuthPass: state.values.vrrpAuthPass || "",
      firstGpuNode: csv(state.values.gpuNodes)[0] || "",
      firstWorkerNode: csv(state.values.workerNodes)[0] || "",
      firstControlPlaneNode: csv(state.values.controlPlaneNodes)[0] || ""
    };

    return tpl.replace(/\{\{\s*([a-zA-Z]+)\.([a-zA-Z0-9_-]+)\s*\}\}/g, function (m, ns, key) {
      if (ctx[ns] && typeof ctx[ns] === "function") return ctx[ns](key);
      return "";
    }).replace(/\{\{\s*([a-zA-Z0-9_-]+)\s*\}\}/g, function (m, key) {
      return ctx[key] === undefined ? "" : String(ctx[key]);
    });
  }

  /* ------------------------------------------------------------------ */
  /* renderers                                                           */
  /* ------------------------------------------------------------------ */

  function renderMethods() {
    var box = $("method-picker");
    box.innerHTML = "";
    DATA.methods.forEach(function (m) {
      var on = state.method === m.id;
      box.appendChild(el("label", { class: "opt" + (on ? " on" : "") }, [
        el("input", {
          type: "radio", name: "method", value: m.id, checked: on ? "checked" : null,
          onchange: function () { state.method = m.id; render(); }
        }),
        el("div", { class: "opt-body" }, [
          el("div", { class: "opt-title", text: m.title }),
          el("div", { class: "opt-note", text: m.summary })
        ])
      ]));
    });

    var detail = $("method-detail");
    detail.innerHTML = "";
    var m = DATA.methods.filter(function (x) { return x.id === state.method; })[0];
    if (m) {
      detail.appendChild(el("div", { text: "Best for: " + m.bestFor }));
      detail.appendChild(el("ul", {}, m.requirements.map(function (r) { return el("li", { text: r }); })));
    }
  }

  function renderCluster() {
    var box = $("cluster-picker");
    box.innerHTML = "";
    DATA.clusterMethods.forEach(function (m) {
      var on = state.cluster === m.id;
      box.appendChild(el("label", { class: "opt" + (on ? " on" : "") }, [
        el("input", {
          type: "radio", name: "cluster", value: m.id, checked: on ? "checked" : null,
          onchange: function () { state.cluster = m.id; render(); }
        }),
        el("div", { class: "opt-body" }, [
          el("div", { class: "opt-title", text: m.title }),
          el("div", { class: "opt-note", text: m.summary })
        ])
      ]));
    });

    var detail = $("cluster-detail");
    detail.innerHTML = "";
    var cm = DATA.clusterMethods.filter(function (x) { return x.id === state.cluster; })[0];
    if (!cm) return;
    var rel = cm.versions || {};
    var rows = el("ul", {});
    Object.keys(rel).forEach(function (k) {
      var r = rel[k];
      rows.appendChild(el("li", {
        text: k + ": Kubernetes " + r.kubernetes + ", etcd " + r.etcd +
          ", containerd " + r.containerd + ", Cilium " + r.cilium +
          ", Ansible " + r.ansible + " / Python " + r.python
      }));
    });
    detail.appendChild(el("div", { text: "Supported releases:" }));
    detail.appendChild(rows);
  }

  function renderComponents() {
    var box = $("components");
    box.innerHTML = "";
    DATA.components.forEach(function (c) {
      var wrap = el("div", { class: "comp" }, [
        el("h4", {}, [
          el("span", { text: c.title }),
          el("span", { class: "req", text: c.required ? "required" : "optional" })
        ])
      ]);
      var opts = el("div", { class: "options" });
      c.options.forEach(function (o) {
        var on = state.choices[c.id] === o.id;
        opts.appendChild(el("label", { class: "opt" + (on ? " on" : "") }, [
          el("input", {
            type: "radio", name: "c-" + c.id, value: o.id, checked: on ? "checked" : null,
            onchange: function () { state.choices[c.id] = o.id; render(); }
          }),
          el("div", { class: "opt-body" }, [
            el("div", { class: "opt-title", text: o.title }),
            o.versionKey && DATA.versions[o.versionKey]
              ? el("div", { class: "opt-note", text: DATA.versions[o.versionKey] })
              : null,
            o.note ? el("div", { class: "opt-note", text: o.note }) : null,
            o.warning ? el("div", { class: "opt-warn", text: "Warning: " + o.warning }) : null
          ])
        ]));
      });
      wrap.appendChild(opts);
      box.appendChild(wrap);
    });
  }

  function renderValues() {
    var box = $("values");
    box.innerHTML = "";
    DATA.values.forEach(function (v) {
      var input;
      if (v.type === "select") {
        input = el("select", {
          onchange: function () { state.values[v.id] = input.value; render(); }
        });
        v.options.forEach(function (o) {
          input.appendChild(el("option", { value: o, text: o, selected: o === state.values[v.id] ? "selected" : null }));
        });
      } else {
        input = el("input", {
          type: v.secret ? "password" : "text",
          value: state.values[v.id] === undefined ? "" : state.values[v.id],
          placeholder: v.required ? "required" : "optional",
          oninput: function () { state.values[v.id] = input.value; }
        });
      }
      box.appendChild(el("div", { class: "field" + (v.secret ? " secret" : "") }, [
        el("label", { text: v.label }),
        input,
        v.hint ? el("div", { class: "hint", text: v.hint }) : null
      ]));
    });
  }

  function activeSteps() {
    return DATA.steps.filter(function (s) {
      if (!s.when) return true;
      if (s.when.component) {
        for (var k in s.when.component) {
          if (state.choices[k] !== s.when.component[k]) return false;
        }
      }
      return true;
    });
  }

  function renderPlan() {
    var method = DATA.methods.filter(function (x) { return x.id === state.method; })[0];
    var chosen = DATA.components.map(function (c) {
      return { label: c.title, choice: optionTitle(c.id) };
    });

    $("plan-summary").textContent =
      (method ? method.title : "—") + " · " +
      (state.cluster || "—") + " · " +
      chosen.length + " components";

    $("plan-note").textContent =
      "Steps shown are filtered by your selection. The plan is a reading order, not a script: every step links to the document that is the authority.";

    var tb = $("versions").querySelector("tbody");
    tb.innerHTML = "";
    var cm = DATA.clusterMethods.filter(function (x) { return x.id === state.cluster; })[0];
    var rows = [];
    if (cm) {
      var rel = cm.versions || {};
      Object.keys(rel).forEach(function (k) {
        if (k === "kubernetes") return;
        rows.push([k, rel[k]]);
      });
    }
    DATA.components.forEach(function (c) {
      var o = optionOf(c.id);
      if (o && o.versionKey && DATA.versions[o.versionKey]) {
        rows.push([c.title, DATA.versions[o.versionKey]]);
      }
    });
    rows.forEach(function (r) {
      tb.appendChild(el("tr", {}, [
        el("td", { text: r[0] }),
        el("td", { text: r[1] })
      ]));
    });

    var list = $("steps");
    list.innerHTML = "";
    activeSteps().forEach(function (s) {
      var item = el("li", {}, [
        el("div", { class: "step-phase", text: s.phase }),
        el("div", { class: "step-title", text: s.title })
      ]);
      var acts = el("ul", { class: "step-actions" });
      (s.actions || []).forEach(function (a) { acts.appendChild(el("li", { text: a })); });
      item.appendChild(acts);
      var refs = el("div", { class: "step-ref" }, [el("code", { text: s.doc })]);
      (s.extraDocs || []).forEach(function (d) {
        refs.appendChild(el("br"));
        refs.appendChild(el("code", { text: d }));
      });
      item.appendChild(refs);
      list.appendChild(item);
    });
  }

  function exportApplies(exp) {
    if (!exp.component) return true;
    if (exp.component === "clusterMethods") return state.cluster === "kubespray";
    // Hide the file when the component is switched off ("none").
    var chosen = state.choices[exp.component];
    return !!chosen && chosen !== "none";
  }

  function renderExports() {
    var box = $("exports");
    box.innerHTML = "";
    DATA.exports.forEach(function (exp) {
      var card = el("div", { class: "export" + (exportApplies(exp) ? "" : " hidden") }, [
        el("h4", { text: exp.name }),
        el("p", { text: exp.description }),
        el("div", { class: "fname", text: exp.filename })
      ]);
      var body = renderTemplate(exp.template);
      card.appendChild(el("pre", { text: body }));
      card.appendChild(el("div", { class: "row" }, [
        el("button", {
          class: "btn primary",
          text: "Download",
          onclick: function () { download(exp.filename, body); }
        }),
        el("button", {
          class: "btn",
          text: "Copy",
          onclick: function () {
            copy(body);
            toast("Copied " + exp.filename);
          }
        })
      ]));
      box.appendChild(card);
    });
  }

  function renderUpgrades() {
    var box = $("upgrades");
    box.innerHTML = "";
    DATA.upgradeSections.forEach(function (u) {
      var card = el("div", { class: "upg" }, [el("h4", { text: u.title })]);
      var ul = el("ul", {});
      (u.actions || []).forEach(function (a) { ul.appendChild(el("li", { text: a })); });
      card.appendChild(ul);
      card.appendChild(el("div", { class: "step-ref" }, [el("code", { text: u.doc })]));
      box.appendChild(card);
    });
  }

  function copy(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text);
      return;
    }
    var ta = el("textarea", { text: text });
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand("copy"); } catch (e) { /* clipboard unavailable */ }
    document.body.removeChild(ta);
  }

  function buildRunbook() {
    var method = DATA.methods.filter(function (x) { return x.id === state.method; })[0];
    var cm = DATA.clusterMethods.filter(function (x) { return x.id === state.cluster; })[0];
    var out = [];
    out.push("# Runbook — " + state.values.clusterName + " (" + state.values.env + ")");
    out.push("");
    out.push("Generated by the cloud-native guide site on " + new Date().toISOString().slice(0, 10) + ".");
    out.push("");
    out.push("| Setting | Value |");
    out.push("|---|---|");
    out.push("| Deployment method | " + (method ? method.title : "-") + " |");
    out.push("| Cluster method | " + (cm ? cm.title : "-") + " |");
    DATA.components.forEach(function (c) {
      out.push("| " + c.title + " | " + optionTitle(c.id) + " |");
    });
    out.push("");
    out.push("## Versions");
    out.push("");
    out.push("| Component | Version |");
    out.push("|---|---|");
    if (cm) {
      Object.keys(cm.versions || {}).forEach(function (k) {
        out.push("| " + k + " | " + cm.versions[k] + " |");
      });
    }
    DATA.components.forEach(function (c) {
      var o = optionOf(c.id);
      if (o && o.versionKey && DATA.versions[o.versionKey]) {
        out.push("| " + c.title + " | " + DATA.versions[o.versionKey] + " |");
      }
    });
    out.push("");
    out.push("## Implementation steps");
    activeSteps().forEach(function (s) {
      out.push("");
      out.push("### " + s.phase + " — " + s.title);
      out.push("");
      (s.actions || []).forEach(function (a) { out.push("- " + a); });
      out.push("");
      out.push("Reference: `" + s.doc + "`");
      (s.extraDocs || []).forEach(function (d) { out.push("- `" + d + "`"); });
    });
    out.push("");
    out.push("## Upgrades and updates");
    DATA.upgradeSections.forEach(function (u) {
      out.push("");
      out.push("### " + u.title);
      out.push("");
      (u.actions || []).forEach(function (a) { out.push("- " + a); });
      out.push("");
      out.push("Reference: `" + u.doc + "`");
    });
    out.push("");
    out.push("---");
    out.push("");
    out.push("The repository is the authority. Review every document before running a step.");
    return out.join("\n");
  }

  /* ------------------------------------------------------------------ */
  /* boot                                                                */
  /* ------------------------------------------------------------------ */

  function initDefaults() {
    DATA.methods.forEach(function (m, i) { if (i === 0) state.method = m.id; });
    DATA.clusterMethods.forEach(function (m, i) { if (i === 0) state.cluster = m.id; });
    DATA.components.forEach(function (c) {
      var def = c.options.filter(function (o) { return o.default; })[0] || c.options[0];
      state.choices[c.id] = def.id;
    });
    DATA.values.forEach(function (v) {
      state.values[v.id] = v.default === undefined ? "" : v.default;
    });
  }

  function render() {
    renderMethods();
    renderCluster();
    renderComponents();
    renderValues();
    renderPlan();
    renderExports();
    renderUpgrades();
  }

  function boot(data) {
    DATA = data;
    initDefaults();

    $("catalog-version").textContent = "catalog " + data.catalogVersion;
    $("catalog-updated").textContent = "updated " + data.updated;
    $("version-count").textContent = Object.keys(data.versions).length + " versions resolved";
    $("source-note").textContent = data.source.docs;

    $("download-runbook").addEventListener("click", function () {
      download("RUNBOOK-" + state.values.clusterName + "-" + state.values.env + ".md", buildRunbook());
      toast("Runbook downloaded");
    });
    $("copy-plan").addEventListener("click", function () {
      copy(buildRunbook());
      toast("Plan copied");
    });

    render();
  }

  fetch("data.json")
    .then(function (r) {
      if (!r.ok) throw new Error("data.json " + r.status);
      return r.json();
    })
    .then(boot)
    .catch(function (err) {
      document.querySelector("main").insertBefore(
        el("div", { class: "card" }, [
          el("h3", { text: "The site data could not be loaded." }),
          el("p", { text: String(err) }),
          el("p", { class: "hint", text: "Run: python3 scripts/build_site.py, then reload." })
        ]),
        document.querySelector("main").firstChild.nextSibling
      );
    });
})();
