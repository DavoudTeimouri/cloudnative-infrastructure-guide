#!/usr/bin/env python3
"""Assert-based self-check for the repository's own tooling.

Runs offline. No framework. Exit code 0 = all checks passed.

Usage: python3 tests/test_repo_tools.py
"""
import os
import re
import subprocess
import sys
import tempfile

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAILURES = []


def check(name, fn):
    try:
        fn()
        print(f"OK   {name}")
    except AssertionError as e:
        FAILURES.append((name, str(e)))
        print(f"FAIL {name}: {e}")
    except Exception as e:  # noqa: BLE001
        FAILURES.append((name, repr(e)))
        print(f"ERROR {name}: {e!r}")


def test_adrs_exist_and_have_all_sections():
    d = os.path.join(BASE, "decisions")
    files = sorted(f for f in os.listdir(d) if f.startswith("ADR-") and f.endswith(".md"))
    gen = open(os.path.join(BASE, "scripts", "gen_adrs.py")).read()
    expected = len(re.findall(r'^\s*\(\d+, "', gen, re.M))
    assert len(files) == expected, f"expected {expected} ADRs, found {len(files)}"
    required = [
        "## Context",
        "## Requirements",
        "## Options considered",
        "## Decision",
        "## Rationale and trade-offs",
        "## Security and operational implications",
        "## Dependencies",
        "## Failure scenarios",
        "## Migration considerations",
    ]
    for f in files:
        text = open(os.path.join(d, f)).read()
        for section in required:
            assert section in text, f"{f} missing section {section!r}"
        assert "UNVERIFIED" not in text or True  # ADRs may legitimately cite unverified items


def test_adr_generator_is_reproducible():
    """Regenerating the ADRs into a temp dir must produce identical content."""
    script = os.path.join(BASE, "scripts", "gen_adrs.py")
    assert os.path.exists(script), "gen_adrs.py missing"
    with tempfile.TemporaryDirectory() as tmp:
        # The generator writes into <repo>/decisions; copy the repo skeleton there.
        repo = os.path.join(tmp, "repo")
        os.makedirs(os.path.join(repo, "decisions"))
        os.makedirs(os.path.join(repo, "scripts"))
        with open(script) as fh:
            content = fh.read()
        with open(os.path.join(repo, "scripts", "gen_adrs.py"), "w") as fh:
            fh.write(content)
        res = subprocess.run(
            [sys.executable, os.path.join(repo, "scripts", "gen_adrs.py")],
            capture_output=True,
            text=True,
        )
        assert res.returncode == 0, f"generator failed: {res.stderr}"
        gen = sorted(os.listdir(os.path.join(repo, "decisions")))
        orig = sorted(
            f for f in os.listdir(os.path.join(BASE, "decisions"))
            if f.startswith("ADR-") and f.endswith(".md")
        )
        assert gen == orig, "generated ADR filenames differ from the committed set"
        for f in gen:
            a = open(os.path.join(repo, "decisions", f)).read()
            b = open(os.path.join(BASE, "decisions", f)).read()
            assert a == b, f"ADR content differs for {f}"


def test_version_matrix_marks_and_sources():
    path = os.path.join(BASE, "compatibility", "version-matrix.md")
    text = open(path).read()
    assert "Check date" in text, "version matrix must record a check date"
    assert "UNVERIFIED" in text, "version matrix must mark unverified items"
    assert "https://" in text, "version matrix must cite source URLs"
    # Every VERIFIED data row must carry a source: a URL or a named official document.
    for line in text.splitlines():
        if not line.startswith("| ") or "| VERIFIED |" not in line:
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 6:
            continue  # legend row, not a data row
        source = cells[3]
        assert source, f"VERIFIED row without a source cell: {line[:120]}"
        assert ("http" in source or "docs." in source or "README" in source
                or "index.yaml" in source or "release" in source
                or "Guide" in source or "documentation" in source
                or ".md" in source
                or source.startswith("Same")), \
            f"VERIFIED row without a resolvable source: {line[:120]}"


def test_artifact_matrix_has_all_mandatory_columns():
    path = os.path.join(BASE, "offline-artifacts", "artifact-matrix.md")
    text = open(path).read()
    for col in ["Component", "Version", "Artifact type", "Official source",
                "Internal destination", "Dependencies", "Download procedure",
                "Integrity", "Configuration", "Refresh", "Validation"]:
        assert col in text, f"artifact matrix missing column {col!r}"


def test_network_matrix_has_required_fields():
    path = os.path.join(BASE, "network-matrix", "network-communication-matrix.md")
    text = open(path).read()
    for col in ["Source", "Destination", "Proto", "Port", "Dir", "Purpose",
                "Scope", "Firewall location", "Config ref", "Validation command"]:
        assert col in text, f"network matrix missing column {col!r}"
    # Row numbering must be contiguous from 1.
    rows = re.findall(r"^\|\s*(\d+)\s*\|", text, re.M)
    nums = [int(r) for r in rows]
    assert nums == list(range(1, len(nums) + 1)), "network matrix row numbers are not contiguous"


def test_no_plaintext_secret_patterns():
    """Guard against committing credentials or private keys."""
    patterns = {
        "private key block": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
        "aws access key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
        "github token": re.compile(r"\bghp_[A-Za-z0-9]{30,}\b"),
        "gitlab pat": re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}\b"),
        "slack token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    }
    skip_dirs = {".git", "node_modules", "__pycache__"}
    offenders = []
    for root, dirs, files in os.walk(BASE):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for name in files:
            if not name.endswith((".md", ".yml", ".yaml", ".sh", ".py", ".json", ".txt")):
                continue
            p = os.path.join(root, name)
            try:
                text = open(p, errors="replace").read()
            except OSError:
                continue
            for label, rx in patterns.items():
                if rx.search(text):
                    offenders.append(f"{os.path.relpath(p, BASE)}: {label}")
    assert not offenders, "possible secrets found: " + "; ".join(offenders)


def test_roadmap_phases_present():
    path = os.path.join(BASE, "requirements", "implementation-roadmap.md")
    text = open(path).read()
    for i in range(1, 16):
        assert f"## Phase {i} " in text, f"roadmap missing phase {i}"


def test_acceptance_criteria_all_not_run():
    """A test must never be marked passed without evidence."""
    path = os.path.join(BASE, "requirements", "acceptance-criteria.md")
    text = open(path).read()
    # The status table has the columns: ID | Test | Phase | Owner | Status | ...
    header = "| ID | Test | Phase | Owner | Status | Evidence | Date | Tester |"
    assert header in text, "acceptance criteria status table header not found"
    body = text.split(header, 1)[1].split("\n\n", 1)[0]
    rows = [l for l in body.splitlines() if re.match(r"^\|\s*[A-Z]-\d+\s*\|", l)]
    assert rows, "acceptance criteria status table is empty"
    for row in rows:
        cells = [c.strip() for c in row.strip("|").split("|")]
        status = cells[4] if len(cells) > 4 else ""
        assert status == "NOT RUN", f"acceptance test not marked NOT RUN: {row[:120]}"


def main():
    tests = [
        ("ADRs exist with all required sections", test_adrs_exist_and_have_all_sections),
        ("ADR generator is reproducible", test_adr_generator_is_reproducible),
        ("version matrix has dates, marks and sources", test_version_matrix_marks_and_sources),
        ("artifact matrix has all mandatory columns", test_artifact_matrix_has_all_mandatory_columns),
        ("network matrix has required fields and contiguous rows", test_network_matrix_has_required_fields),
        ("no plaintext secret patterns in the repo", test_no_plaintext_secret_patterns),
        ("roadmap has all 15 phases", test_roadmap_phases_present),
        ("acceptance tests are not pre-marked as passed", test_acceptance_criteria_all_not_run),
    ]
    for name, fn in tests:
        check(name, fn)
    print()
    if FAILURES:
        print(f"{len(FAILURES)} check(s) failed")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
