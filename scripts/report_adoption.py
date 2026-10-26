#!/usr/bin/env python3
"""Print adoption metrics as Markdown.

Counts only what the repository can prove: module directories and their
creation dates in Git history. Anything not measured is marked as such —
no invented survey numbers.

Usage: python3 scripts/report_adoption.py > site/adoption.md
"""
import datetime
import os
import subprocess

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODULES = os.path.join(BASE, "site", "modules")


def git(*args):
    res = subprocess.run(["git", "-C", BASE] + list(args), capture_output=True, text=True)
    return res.stdout if res.returncode == 0 else ""


def added_modules(since):
    out = git("log", f"--since={since}", "--diff-filter=A", "--name-only", "--pretty=format:", "--", "site/modules")
    names = [l.strip() for l in out.splitlines() if l.strip()]
    return sorted({n.split("/")[2] for n in names if n.startswith("site/modules/") and n.count("/") > 2})


def main():
    modules = sorted(d for d in os.listdir(MODULES) if os.path.isdir(os.path.join(MODULES, d))) if os.path.isdir(MODULES) else []
    last30 = [m for m in added_modules("30 days ago") if m in modules]
    last90 = [m for m in added_modules("90 days ago") if m in modules]
    commits = len([l for l in git("log", "--since=30 days ago", "--oneline").splitlines() if l.strip()])
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")

    print("# Adoption metrics")
    print()
    print(f"Generated {today} by `scripts/report_adoption.py` from Git history.")
    print()
    print("## Modules")
    print()
    print("| Metric | Value |")
    print("|---|---|")
    print(f"| Module directories | {len(modules)} |")
    print(f"| Added in last 30 days (still present) | {len(last30)} |")
    print(f"| Added in last 90 days (still present) | {len(last90)} |")
    print(f"| Commits in last 30 days | {commits} |")
    print()
    print("## Not measured")
    print()
    print("| Metric | Reason |")
    print("|---|---|")
    print("| Deploy-bundle dry-run results | no bundle runner in CI |")
    print("| Golden-path service creations | `scripts/golden_path.py` writes local files only |")
    print("| User satisfaction (dNPS) | no survey instrument |")


if __name__ == "__main__":
    main()
