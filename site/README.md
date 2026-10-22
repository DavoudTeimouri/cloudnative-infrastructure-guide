# Interactive guide site

A static site, published from this repository, that turns the documents into a step-by-step
build plan for one specific cluster.

- **Live:** <https://davoudteimouri.github.io/cloudnative-infrastructure-guide/>
- **Source:** `site/` (markup, style, renderer) + `site/data.json` (generated)
- **Builder:** `scripts/build_site.py`
- **Validator:** `scripts/validate_catalog.py`
- **CI:** `.github/workflows/site.yml`

## What it does

| Function | Behavior |
|---|---|
| Deployment method | Bare metal or virtual machines. Selecting one shows its requirements and failure-domain caveats |
| Cluster method and release | Kubespray, five releases in parallel; the release list and the pinned Kubernetes/etcd/containerd/Ansible versions come from the catalog and the version matrix |
| Components | Every component has a fixed option set. Selecting an option changes the plan, the version table and the exports |
| Site values | CIDRs, hostnames, node names, endpoints. Rendered locally. Nothing is transmitted |
| Plan | Ordered steps, filtered by the selection, each linking to the authoritative document |
| Resolved versions | Only rows marked `VERIFIED` in `compatibility/version-matrix.md` |
| Exports | Kubespray inventory, group vars, offline group vars, MetalLB pool, Keepalived config, edge Compose stack, Vault policy, GPU labels, vLLM Deployment, runbook |
| Upgrades | A separate section, ordered per component, with the rollback limitation stated where one exists |

Two rules make the output honest:

1. The site carries **no independent knowledge**. Every statement comes from a document, the
   catalog, or the version matrix.
2. A step is a **reading order**, not a script. The linked document is the authority, and the
   generated files are starting points that must be reviewed.

## How it stays current

```
catalog/catalog.json            components, options, steps, values, upgrade sections
catalog/exports.json            export templates with {{placeholders}}
compatibility/version-matrix.md pinned versions, VERIFIED rows only
                │
                ▼
      scripts/build_site.py
                │
                ▼
        site/data.json   ──►  site/app.js renders it in the browser
```

| Change | What you edit | What updates |
|---|---|---|
| A version bump | `compatibility/version-matrix.md` | Every place the site shows that version, on the next build. No catalog edit |
| A new component or option | `catalog/catalog.json` | The form, the plan, the version table |
| A new step or phase | `catalog/catalog.json` | The plan and the runbook export |
| A renamed document | `catalog/catalog.json` **and** the file | The build fails until both agree — `validate_catalog.py` checks that every referenced path exists |
| A new exportable file | `catalog/exports.json` | A new card in the export section, downloadable immediately |
| A document rewrite | nothing on the site | The site links to the document; the text lives in one place only |

The build is deterministic. `build_site.py --check` fails when `site/data.json` no longer
matches the sources, so a stale site cannot be merged.

## Step by step: use the site

1. Open the live URL.
2. Pick the **deployment method**. Read the requirements before continuing: the VM option lists
   the caveats that change the failure domain.
3. Pick the **cluster method and release**. Confirm the pinned Kubernetes version is the one you
   intend to run; the other releases stay visible for comparison.
4. Walk the **components**. Required components have no "none" option. Options that carry a
   warning show it inline — read it before selecting.
5. Fill the **site values**. Leave the two secret fields empty if you prefer to set them on the
   target host; they are never transmitted.
6. Read the **plan** top to bottom. Open each referenced document. The plan does not replace the
   document.
7. Download the **exports** you need. Review every file: image tags, paths, interface names and
   the registry host are placeholders resolved from your input, not validated against your site.
8. Download the **runbook** and attach it to the change record.
9. Before any version change, read the **upgrades** section. Kubernetes and Ceph have no
   rollback; the backup is the rollback.

## Step by step: change the site

```bash
# 1. Edit the catalog, the export templates or the version matrix.
# 2. Regenerate the data.
python3 scripts/build_site.py

# 3. Validate: missing documents, unknown placeholders, stale data.
python3 scripts/validate_catalog.py

# 4. Preview locally.
python3 -m http.server 8080 --directory site
#    http://localhost:8080

# 5. Commit both the source and the generated data.
git add catalog/ compatibility/version-matrix.md site/data.json
git commit -m "site: <what changed>"
```

The CI job runs the same two scripts and fails when `site/data.json` is stale.

## Adding a component

Add one entry to `catalog/catalog.json`:

```json
{
  "id": "backup",
  "title": "Backup",
  "required": true,
  "options": [
    { "id": "velero", "title": "Velero with CSI snapshots", "default": true,
      "versionKey": "velero", "doc": "lifecycle/backup/backup-and-dr.md" }
  ]
}
```

Rules the validator enforces:

- exactly one option carries `"default": true`
- every `doc` path exists
- every `versionKey` resolves to a `VERIFIED` row in the version matrix
- every `when.component` condition names a real component id

## Adding an export

Add one entry to `catalog/exports.json`. Placeholders:

| Placeholder | Source |
|---|---|
| `{{value.<id>}}` | a field in `catalog.json` → `values` |
| `{{choice.<component>}}` | the selected option id of that component |
| `{{version.<key>}}` | the resolved version matrix |
| `{{controlPlaneNodes}}`, `{{workerNodes}}`, `{{gpuNodeGroup}}` | derived from the node-name fields |
| `{{registryAuth}}`, `{{vrrpAuthPass}}` | the two secret fields, rendered locally only |

Keep templates flat. Loops and conditionals belong in the renderer (`site/app.js`), not in the
template, because a static JSON file cannot be tested as code.

## Design constraints

- **No build toolchain.** The site is plain HTML, CSS and JavaScript. It works from a file
  system, from Pages, and from an internal mirror with no network.
- **No dependency on a CDN.** No fonts, no analytics, no third-party scripts. It must render in
  an air-gapped environment.
- **No server.** No API, no telemetry, no storage. Values stay in the browser tab.
- **One source of truth.** The site never holds a fact the repository does not hold.
