#!/usr/bin/env python3
"""Compare the remote GitHub tree with a local directory. Read-only."""
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
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read().decode())


def remote_tree(owner, repo, branch):
    ref = get(f"/repos/{owner}/{repo}/git/ref/heads/{branch}")
    sha = ref["object"]["sha"]
    tree = get(f"/repos/{owner}/{repo}/git/trees/{sha}?recursive=1")
    out = {}
    for e in tree["tree"]:
        if e["type"] == "blob":
            out[e["path"]] = e["sha"]
    return out, sha


def local_tree(d):
    out = {}
    for root, dirs, names in os.walk(d):
        dirs[:] = [x for x in dirs if x != ".git"]
        for n in names:
            p = os.path.join(root, n)
            rel = os.path.relpath(p, d).replace(os.sep, "/")
            out[rel] = None
    return out


owner, repo, branch, local_dir = sys.argv[1:5]
rem, sha = remote_tree(owner, repo, branch)
loc = local_tree(local_dir)
print(f"remote commit: {sha[:8]}  remote blobs: {len(rem)}  local files: {len(loc)}")
only_remote = sorted(set(rem) - set(loc))
only_local = sorted(set(loc) - set(rem))
print(f"only on remote: {len(only_remote)}")
for p in only_remote[:20]:
    print("   ", p)
print(f"only local: {len(only_local)}")
for p in only_local[:20]:
    print("   ", p)
