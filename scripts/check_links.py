#!/usr/bin/env python3
"""Check relative links and in-page anchors in every Markdown file.

Stdlib only, no network. External URLs are not fetched: this gate catches
broken repository paths and dead anchors, which are the failures that a
reader hits.

Usage: python3 scripts/check_links.py
"""
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {".git", "node_modules", "__pycache__"}
LINK = re.compile(r"\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
FENCE = re.compile(r"^```.*?^```", re.S | re.M)
HEADING = re.compile(r"^#{1,6}\s+(.*)$", re.M)
EXPLICIT_ID = re.compile(r"<a\s+(?:id|name)=\"([^\"]+)\"", re.I)


def slug(text):
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"[*_]{1,2}([^*_]+)[*_]{1,2}", r"\1", text)
    text = text.strip().lower()
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"\s+", "-", text)


def anchors(path):
    text = open(path, encoding="utf-8", errors="replace").read()
    found, seen = set(), {}
    for match in HEADING.finditer(text):
        base = slug(match.group(1))
        n = seen.get(base, 0)
        seen[base] = n + 1
        found.add(base if n == 0 else f"{base}-{n}")
    found.update(EXPLICIT_ID.findall(text))
    return found


def check(base):
    problems = []
    for root, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            if not name.endswith(".md"):
                continue
            path = os.path.join(root, name)
            rel = os.path.relpath(path, base)
            text = FENCE.sub("", open(path, encoding="utf-8", errors="replace").read())
            for target in LINK.findall(text):
                if target.startswith(("http://", "https://", "mailto:", "tel:")):
                    continue
                if "{" in target or target.startswith("#"):
                    if target.startswith("#") and len(target) > 1:
                        if target[1:] not in anchors(path):
                            problems.append(f"{rel}: missing anchor {target}")
                    continue
                file_part, _, anchor = target.partition("#")
                dest = os.path.normpath(os.path.join(root, file_part))
                if not os.path.exists(dest):
                    problems.append(f"{rel}: missing file {target}")
                elif anchor and dest.endswith(".md") and anchor not in anchors(dest):
                    problems.append(f"{rel}: missing anchor {target}")

    return problems


def main():
    if "--self-test" in sys.argv:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "a.md"), "w") as fh:
                fh.write("# Target\n\n[ok](a.md#target) [file](nope.md) [anchor](a.md#missing)\n")
            found = check(tmp)
            assert len(found) == 2, f"expected 2 problems, got {found}"
            assert any("nope.md" in f for f in found), found
            assert any("#missing" in f for f in found), found
        print("self-test ok")
        return 0

    problems = check(BASE)
    for p in problems:
        print(p)
    print(f"{len(problems)} broken link(s) in {BASE}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
