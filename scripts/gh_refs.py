#!/usr/bin/env python3
"""List the refs (branches, tags, releases) of a GitHub repo, or delete a repo.

Explicit CLI only. Deleting a repo is irreversible and needs admin rights.

Usage:
  python3 scripts/gh_refs.py refs <owner> <repo>
  python3 scripts/gh_refs.py delete-repo <owner> <repo>
"""
import json
import subprocess
import sys
import urllib.error
import urllib.request

API = "https://api.github.com"
TOK = subprocess.run(["bash", "-lc", "printf '%s' \"$GITHUB_TOKEN\""],
                     capture_output=True, text=True, check=True).stdout.strip()
H = {"Authorization": f"Bearer {TOK}", "Accept": "application/vnd.github+json",
     "User-Agent": "cloud-native-guide-verify"}


def get(path):
    req = urllib.request.Request(f"{API}{path}", headers=H)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def delete_repo(owner, repo):
    req = urllib.request.Request(f"{API}/repos/{owner}/{repo}", headers=H, method="DELETE")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return f"HTTP {e.code}: {e.read().decode()[:400]}"


if sys.argv[1] == "refs":
    owner, repo = sys.argv[2:4]
    print("branches:", [b["name"] for b in get(f"/repos/{owner}/{repo}/branches")])
    print("tags:", [t["name"] for t in get(f"/repos/{owner}/{repo}/tags")])
    try:
        print("releases:", [r["tag_name"] for r in get(f"/repos/{owner}/{repo}/releases")])
    except urllib.error.HTTPError:
        print("releases: none")
elif sys.argv[1] == "delete-repo":
    owner, repo = sys.argv[2:4]
    print("status:", delete_repo(owner, repo))
