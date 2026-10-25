# Plan: Professional guide + modular configuration sites

## Goal 1 — Professional step-by-step guide (docs/guide/) — DONE
Restructured docs into a numbered, interlinked from-scratch guide:
- 00-prerequisites → 10-backup-upgrade (see `docs/guide/`)
Each page: purpose, prerequisites, steps, validation, "next" / "prev" links, links to authoritative procedures.
- `docs/README.md` — guide landing + table of contents + authoritative procedure index

## Goal 2 — Modular configuration sites (site/modules/)
Each configuration step becomes its own self-contained site/module:
- `site/modules/ceph/` — Ceph cluster configurator (nodes, roles per node, pools) — DONE
- `site/modules/kubernetes/` — Kubespray cluster configurator (planned)
- `site/modules/traffic/` — Edge LB configurator (planned)
- `site/modules/os-baseline/` — OS baseline configurator (planned)

Each module:
- Self-contained HTML + ES5 JS (no let/const/arrow/template literals)
- Reads values from `catalog/catalog.json` (single source of truth)
- Client-side validation with inline error correction (prevent wrong configs)
- Generates a downloadable config file (YAML/JSON)
- Links back to the main guide docs

## Constraints (unchanged)
- ES5 only in site/app.js and module app.js
- Stdlib-only Python for any builder
- No network at deploy time; all from internal mirrors
- Catalog is single source of truth
- Secrets redacted as [REDACTED]

## Completed
- `docs/guide/` index.md + 00–10 step pages + `docs/README.md`
- `site/modules/ceph/index.html` + `app.js` + `styles.css`
- Main site `site/index.html` links to Ceph module
