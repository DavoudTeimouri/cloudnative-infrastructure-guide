#!/usr/bin/env python3
"""Verify a GitHub repo branch content via the API. Read-only."""
import json
import os
import subprocess
import sys
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


owner, repo, branch = sys.argv[1:4]
root = get(f"/repos/{owner}/{repo}/contents/")
print(f"root entries: {len(root)}")
for e in sorted(root, key=lambda x: x["name"]):
    print(f"  {e['type']:4} {e['name']}")

commits = get(f"/repos/{owner}/{repo}/commits?per_page=100")
print(f"commits on {branch}: {len(commits)}")
for c in commits[:5]:
    print(f"  {c['sha'][:8]} {c['commit']['message'].splitlines()[0][:70]}")

info = get(f"/repos/{owner}/{repo}")
print(f"description: {info.get('description')}")
print(f"private: {info.get('private')}  default_branch: {info.get('default_branch')}")

topics = get(f"/repos/{owner}/{repo}/topics")
print(f"topics: {', '.join(topics.get('names', []))}")
