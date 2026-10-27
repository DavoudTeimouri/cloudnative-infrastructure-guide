# Acceptance evidence

`requirements/acceptance-criteria.md` is the gate. This directory stores the
evidence that a gate item was actually executed.

## Layout

```
tests/acceptance/<test-id>/
├── command.txt      # the exact command(s) run
├── output.txt       # raw output, unedited
└── notes.md         # environment, time, deviations, operator
```

One directory per test ID (`F-01`, `B-05`, `D-01`, ...). The path recorded in the
**Evidence** column of `requirements/acceptance-criteria.md` must point at the
directory, and the directory must exist in Git.

## Status rules

| Status | Requirement |
|---|---|
| `NOT RUN` | Default. No evidence expected. |
| `PASSED` | Evidence directory exists, plus a date and a named tester. |
| `FAILED` | Evidence directory exists. A failure without a log is a rumour. |
| `BLOCKED` | Evidence explains the blocker (ticket, missing hardware, dependency). |

Enforcement is automated in two places:

```bash
python3 scripts/acceptance_status.py          # phase table + gate count, exits 1 on bad sign-off
python3 tests/test_repo_tools.py              # same rule inside the repository self-check
```

`scripts/acceptance_status.py --self-test` proves the validator rejects an
unsupported `PASSED`.

## How to execute a test

1. Read its row in `requirements/acceptance-criteria.md` (procedure, expected
   result, evidence, pass/fail, context).
2. Run it in the stated context — staging unless the row says otherwise.
3. Capture raw output, unedited, into `tests/acceptance/<test-id>/output.txt`.
4. Open a pull request that adds the evidence and updates the row: status, evidence
   path, date (`YYYY-MM-DD`), tester.
5. Review requires a second person who did not run the test.

## Order

Phases are ordered by dependency, and the acceptance table inherits that order:
offline operation (2) → infrastructure (3) → storage (6) → Kubernetes (7) →
workloads and policy (8–10) → observability (11) → GPU (12) → pipeline (13) →
failure and recovery (14).

Items in phase 14 (D-*, B-12, B-13, B-14) destroy or rebuild parts of the
platform. Run them only in staging or an approved window, and always after the
phase 2–13 items they depend on have passed.

## What is deliberately not automated

The 48 criteria describe work on real hardware: pulling power from a node,
removing an OSD, revoking a certificate, scanning an image with a CRITICAL CVE.
A script that claimed to check them without the hardware would be a false
assurance, which is the one thing this repository refuses to produce. The
validator therefore enforces evidence, not execution.
