# Plan: Professional guide + modular configuration sites

## Goal 1 — Professional step-by-step guide (docs/guide/) — DONE
Restructured docs into a numbered, interlinked from-scratch guide:
- 00-prerequisites → 10-backup-upgrade (see `docs/guide/`)
Each page: purpose, prerequisites, steps, validation, "next" / "prev" links, links to authoritative procedures.
- `docs/README.md` — guide landing + table of contents + authoritative procedure index

## Goal 2 — Modular configuration sites (site/modules/) — DONE
Each configuration step is its own self-contained module site:
- `site/modules/00-prerequisites/` → `site/modules/10-backup-upgrade/` (11 modules)

Each module:
- Self-contained HTML + ES5 JS + CSS (no let/const/arrow/template literals)
- Step nav linking all 10 modules + main site (each module links to every other)
- Client-side validation with inline error correction (prevents wrong configs)
- Downloadable config JSON
- Verified ES5-compliant across all 11 app.js files

## Completed
- Goal #1: `docs/guide/` index.md + 00–10 step pages + `docs/README.md`
- Goal #2: `site/modules/00-10/` (11 self-contained module sites)
- Main site `site/index.html` links to all 10 modules
