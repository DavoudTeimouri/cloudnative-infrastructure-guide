#!/usr/bin/env python3
"""Summarise and validate the acceptance-criteria table.

Rules enforced:
  - PASSED requires evidence path that exists, a date, and a tester.
  - FAILED requires an evidence path that exists (a failure without a log is a rumour).
  - Any other status is treated as not executed.

Never writes the table. Sign-off is a reviewed pull request; this script only
refuses to let an unsupported PASSED through.

Usage: python3 scripts/acceptance_status.py [--quiet]
"""
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TABLE = os.path.join(BASE, "requirements", "acceptance-criteria.md")
ROW = re.compile(r"^\|\s*([A-Z]-\d+)\s*\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|")


def rows():
    out = []
    for line in open(TABLE, encoding="utf-8"):
        m = ROW.match(line)
        if not m:
            continue
        out.append({
            "id": m.group(1).strip(),
            "test": m.group(2).strip(),
            "phase": m.group(3).strip(),
            "owner": m.group(4).strip(),
            "status": m.group(5).strip() or "NOT RUN",
            "evidence": m.group(6).strip(),
            "date": m.group(7).strip(),
            "tester": m.group(8).strip(),
        })
    return out


def problems_for(data, base=BASE):
    problems = []
    for r in data:
        if r["status"] == "PASSED":
            if not r["evidence"]:
                problems.append(f"{r['id']}: PASSED without an evidence path")
            else:
                path = os.path.join(base, r["evidence"].strip("`"))
                if not os.path.exists(path):
                    problems.append(f"{r['id']}: evidence path does not exist: {r['evidence']}")
            if not r["date"]:
                problems.append(f"{r['id']}: PASSED without a date")
            if not r["tester"]:
                problems.append(f"{r['id']}: PASSED without a tester")
        elif r["status"] == "FAILED" and not r["evidence"]:
            problems.append(f"{r['id']}: FAILED without an evidence path")
        elif r["status"] not in ("NOT RUN", "PASSED", "FAILED", "BLOCKED"):
            problems.append(f"{r['id']}: unknown status {r['status']!r}")
    return problems


def main():
    quiet = "--quiet" in sys.argv
    if "--self-test" in sys.argv:
        import tempfile
        tmp = tempfile.mkdtemp()
        os.makedirs(os.path.join(tmp, "tests", "acceptance", "X-02"))
        open(os.path.join(tmp, "tests", "acceptance", "X-02", "log.txt"), "w").write("evidence\n")
        fake = [
            {"id": "X-01", "status": "PASSED", "evidence": "", "date": "", "tester": ""},
            {"id": "X-02", "status": "PASSED", "evidence": "tests/acceptance/X-02/log.txt",
             "date": "2026-10-26", "tester": "t"},
            {"id": "X-03", "status": "FAILED", "evidence": "", "date": "", "tester": ""},
            {"id": "X-04", "status": "WHATEVER", "evidence": "", "date": "", "tester": ""},
        ]
        found = problems_for(fake, base=tmp)
        ids = {p.split(":")[0] for p in found}
        assert ids == {"X-01", "X-03", "X-04"}, found
        assert not any(p.startswith("X-02") for p in found), found
        print("self-test ok")
        return 0

    data = rows()
    if not data:
        print("no rows parsed from", TABLE)
        return 1

    problems = problems_for(data)
    phases = {}
    for r in data:
        p = phases.setdefault(r["phase"], {"total": 0, "PASSED": 0, "FAILED": 0, "NOT RUN": 0, "BLOCKED": 0})
        p["total"] += 1
        key = r["status"] if r["status"] in p else "NOT RUN"
        p[key] += 1

    if not quiet:
        print("| Phase | Tests | Passed | Failed | Blocked | Not run |")
        print("|---|---|---|---|---|---|")
        for phase in sorted(phases, key=lambda x: int(x) if x.isdigit() else 99):
            p = phases[phase]
            print(f"| {phase} | {p['total']} | {p['PASSED']} | {p['FAILED']} | {p['BLOCKED']} | {p['NOT RUN']} |")
        passed = sum(1 for r in data if r["status"] == "PASSED")
        print(f"\nGate: {passed}/{len(data)} passed")

    for p in problems:
        print("ERROR", p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
