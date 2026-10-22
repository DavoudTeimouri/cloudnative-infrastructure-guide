#!/usr/bin/env python3
"""Fetch latest release tags from GitHub release Atom feeds (no API rate limit).

Usage: python3 scripts/github_latest_releases.py owner/repo ...
"""
import re
import sys
import urllib.request

UA = {"User-Agent": "cloud-native-guide/version-matrix"}


def latest(repo):
    url = f"https://github.com/{repo}/releases.atom"
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=40) as r:
        text = r.read().decode("utf-8", "replace")
    m = re.search(r"<entry>.*?<title>\s*([^<]+?)\s*</title>", text, re.S)
    if not m:
        return "NOT FOUND"
    tag = m.group(1)
    if tag.lower() in ("latest",):
        tags = re.findall(r"<title>\s*([^<]+?)\s*</title>", text)
        tag = tags[1] if len(tags) > 1 else "?"
    return tag


for repo in sys.argv[1:]:
    try:
        print(f"{repo:45s} => {latest(repo)}")
    except Exception as e:
        print(f"{repo:45s} => ERR {e}")
