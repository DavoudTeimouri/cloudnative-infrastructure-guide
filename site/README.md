# Interactive guide site

A static site, published from this repository, that turns the documents into a configurable build
plan and a per-component upgrade walkthrough.

- **Live:** <https://davoudteimouri.github.io/cloudnative-infrastructure-guide/>
- **Source:** `site/index.html`, `site/app.js`, `site/styles.css` (hand-written) and `site/data.json` (generated)
- **Data model:** `catalog/catalog.json`, `catalog/exports.json`, `catalog/upgrades.json`
- **Builder:** `scripts/build_site.py`
- **Validators:** `scripts/validate_catalog.py`, `tests/test_site_render.py`
- **CI:** `.github/workflows/site.yml`

## What it does

The configurator is a wizard. One page per group, then a review page, then a separate upgrade
walkthrough. The Back and Next buttons are pinned to the bottom of the page, below the content,
with the page counter between them.

| Page | Inputs |
|---|---|
| 1. Deployment | Bare metal or VM, cluster name, environment, domain, deployment method, Kubespray release, component versions |
| 2. Application cluster | One or more application clusters as a table: per cluster — name, control-plane count/size/disk, worker count/size/disk, Windows workers, pod and service CIDRs. The first cluster is the primary; each additional one yields its own `additional-clusters.yaml` record and Argo CD cluster Secret. |
| 3. Management cluster | Its own worker count and sizes, Rancher, Keycloak, directory integrations (multi-select) |
| 4. Operating system | Oracle Linux 9/8, Ubuntu 24.04/22.04, admin user, SSH port and policy, sudo, timezone, locale, NTP, DNS, search domain, kernel arguments, swap, THP, max pods, file descriptors, SELinux, firewall, audit retention, unattended updates, CA bundle. One tab per selected role; every tab shows the common baseline plus that role's overrides. |
| 5. Storage | Rook in-cluster (OSD workers, device filter, StorageClasses), or one or more Ceph clusters as a table (`sdsClusters`): per cluster — name, mode, IP start, CPU/RAM/system disk, MON/MGR/OSD/MDS/RGW host counts, OSD data and DB disk sizes |
| 6. Traffic | Edge count and VIP, MetalLB pool, DMZ CIDR, VRRP pass phrase, ingress controller |
| 7. Network and offline | Seven CIDRs, API VIP, registry and file mirror, extra registries and repos |
| 8. Platform services | GitOps, secrets, observability, logging, policy, runtime detection, backup, mesh, GPU |
| 9. Add-ons | cert-manager, Metrics Server, VPA, Descheduler, external-dns, Trivy Operator, OpenTelemetry Collector |

Everything else is derived. Node names and addresses come from the prefix, the counts and the first
address (`<prefix>-cp-N`, `<prefix>-w-N`, `<prefix>-gpu-N`, `<prefix>-mgmt-N`,
`<ceph prefix>-mon-N`, `-mgr-N`, `-osd-N`, `-mds-N`, `-rgw-N`, `lb-N`), so the inventories, the
Keepalived peers, the Ceph per-role placement and the sizing table cannot disagree with the counts.

| Output | Where it appears |
|---|---|
| Sizing totals | Review page, and the runbook |
| Resolved versions | Review page (VERIFIED rows only) and every export |
| Filtered implementation steps | Review page, links to the authoritative document |
| Generated files | Review page: both inventories, Kubespray group vars, cephadm bootstrap and per-role spec, MetalLB, Keepalived, edge Compose, bootstrap scripts, Istio manifests, Vault policy, GPU manifests, directory checklist, add-on values files, deployment bundle |
| Deployment bundle | `deploy.sh`, `nodes.tsv`, `00-preflight.sh` … `50-verify.sh`: a phased, idempotent run with a stop at the first failure |
| Add-on values | One file per selected option: cert-manager values and issuer, VPA recommendation or auto, Descheduler dry-run or eviction, external-dns RFC2136 or CoreDNS etcd, Trivy, OpenTelemetry |
| Runbook | Download button, full plan plus sizing and upgrade summary |
| Upgrade walkthrough | Upgrade view: gates, commands rendered against your values, downtime, rollback |

## How it stays current

```
catalog/catalog.json            pages, components, options, values, steps
catalog/exports.json            export templates and their gates
catalog/upgrades.json           upgrade flows, gates, commands, rollback
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
| A version bump | `compatibility/version-matrix.md` | Every place that version appears, on the next build |
| A new page, component or option | `catalog/catalog.json` | The wizard, the review, the exports |
| A new exportable file | `catalog/exports.json` | A new card, downloadable immediately |
| An upgrade step or gate | `catalog/upgrades.json` | The walkthrough and its runbook |
| A renamed document | the catalog **and** the file | The build fails until both agree |
| A document rewrite | nothing | The site links to the document; text lives in one place |

`build_site.py --check` fails when `site/data.json` no longer matches the sources, so a stale site
cannot be merged.

## Data contract

### Component

```json
{
  "id": "storage",
  "title": "Storage",
  "required": true,
  "options": [
    { "id": "rook", "title": "Rook-Ceph inside the cluster", "default": true,
      "versionKey": "rook", "doc": "storage/rook-ceph/rook-ceph.md" },
    { "id": "cephadm-podman", "title": "cephadm on dedicated hosts — Podman",
      "versionKey": "ceph", "doc": "storage/ceph/cephadm-deployment.md" }
  ]
}
```

- exactly one option carries `"default": true` (`multi: true` components need at least one)
- `versionKey` must resolve in the version matrix, otherwise the version is absent from the page
- `doc` must exist, or the build fails
- `warning` renders inline; `note` renders below the title

### Value

`type` is `text`, `number`, `select`, `bool` (checkbox, rendered as `true`/`false`) or `lines`
(textarea, one entry per line). `secret: true`
renders a password field and is only ever written into the file the operator downloads.

### Page

```json
{ "id": "p5", "title": "Storage", "subtitle": "…",
  "components": ["storage"],
  "fields": ["cephMonCount", "cephMonIpStart", "cephMgrCount", "cephMgrIpStart",
             "cephOsdCount", "cephOsdIpStart", "cephCpu", "cephMemGb",
             "cephSystemDiskGb", "cephOsdDataDiskGb", "cephOsdDbDiskGb"] }
```

Every component and every value must appear on exactly one page — the validator enforces coverage,
so a value cannot be added and then silently dropped from the UI.

### Export

```json
{
  "id": "ceph-bootstrap",
  "component": "storage",
  "when": { "component": "storage", "values": ["cephadm-podman", "cephadm-docker"] },
  "filename": "ceph-bootstrap.sh",
  "template": "… {{cephHostList}} … {{cephEngineFlag}} …"
}
```

`when` gates the card on selected option ids (any of them). Without `when`, `component` gates on
"not `none`".

### Upgrade flow

```json
{
  "id": "kubernetes",
  "title": "Kubernetes and Kubespray",
  "doc": "lifecycle/upgrades/upgrade-procedures.md",
  "versionSource": "kubespray",
  "downtime": "…", "rollback": "None. The restore path is the backup.",
  "steps": [
    { "phase": "1. Gate", "title": "…", "gate": true,
      "actions": ["…"], "command": "ansible-playbook … -e kube_version={{version.kubernetes}}" }
  ]
}
```

Every flow needs at least one `gate`. The validator enforces that, because a flow without a gate
invites an upgrade with no verification point.

## Placeholders

| Placeholder | Source |
|---|---|
| `{{value.<id>}}` | a field in `catalog.json` → `values` |
| `{{choice.<component>}}` | the selected option id (a comma list for multi-select) |
| `{{version.<key>}}` | the resolved version matrix |
| `{{appCpHosts}}`, `{{appWorkerHosts}}`, `{{gpuHosts}}`, `{{gpuGroup}}` | generated from the counts |
| `{{mgmtHosts}}`, `{{cephHosts}}`, `{{cephHostList}}`, `{{cephMonIp}}`, `{{cephOtherIps}}` | generated |
| `{{edgeHosts}}`, `{{edgeHostList}}`, `{{edgeL1}}`, `{{edgePeerList}}` | generated |
| `{{cephEngine}}`, `{{cephEngineFlag}}` | `podman` / `docker` and `''` / `--docker` |
| `{{idpTargets}}` | one bullet per selected directory integration |
| `{{extraRegistryMirrors}}` | YAML block from the extra-registries field |
| `{{revision}}`, `{{istioProfile}}` | Istio revision (`1.31.3` → `1-31-3`) and ambient/default |
| `{{registryAuth}}`, `{{vrrpAuthPass}}` | the two secret fields, rendered locally only |

Keep templates flat. Loops and conditionals belong in `site/app.js`, because a JSON string cannot
be tested as code.

## Adding an upgrade flow

1. Add the section to `lifecycle/upgrades/upgrade-procedures.md` — that document is the authority.
2. Add the flow to `catalog/upgrades.json` with the same order, the same gates, and the true
   rollback statement.
3. `python3 scripts/build_site.py && python3 scripts/validate_catalog.py && python3 tests/test_site_render.py`
4. Commit the catalog and `site/data.json`.

## Design constraints

- **ES5 only.** `tests/test_site_render.py` runs `app.js` in Duktape: no `let`/`const`, no arrow
  functions, no template literals.
- **No build toolchain, no CDN, no server.** Plain HTML/CSS/JS, works from the file system and from
  an internal mirror with no network.
- **No telemetry, no storage.** Values stay in the browser tab.
- **One source of truth.** The site never holds a fact the repository does not hold.

## Verify

```bash
python3 scripts/build_site.py
python3 scripts/validate_catalog.py      # docs exist, placeholders resolve, pages cover everything
python3 tests/test_site_render.py        # boots app.js, walks the wizard, flips selections, renders upgrades
python3 -m http.server 8080 --directory site
```
