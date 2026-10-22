#!/usr/bin/env python3
"""Replace the full content of a GitHub repo branch with the local working tree.

Uses the Git Data API (blobs -> tree -> commit -> ref update), so no git
force-push is needed and files absent locally are removed remotely.

By default the new commit keeps the remote history as its parent. Pass
--orphan to drop the remote history entirely and start a fresh root commit
(destructive: the previous commits become unreachable from the branch).

Usage:
  python3 scripts/sync_github.py <owner> <repo> <local_dir> <branch> <message> [--orphan]
"""
import base64
import json
import os
import subprocess
import sys
import urllib.request

API = "https://api.github.com"


def token():
    return subprocess.run(
        ["bash", "-lc", "printf '%s' \"$GITHUB_TOKEN\""],
        capture_output=True, text=True, check=True,
    ).stdout.strip()


TOK = token()
HEADERS = {
    "Authorization": f"Bearer {TOK}",
    "Accept": "application/vnd.github+json",
    "User-Agent": "cloud-native-guide-sync",
}


def api(method, path, payload=None, raw=False):
    url = path if path.startswith("http") else f"{API}{path}"
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, headers=HEADERS, method=method)
    with urllib.request.urlopen(req, timeout=90) as r:
        body = r.read()
    return body if raw else json.loads(body.decode())


def collect(local_dir):
    files = []
    for root, dirs, names in os.walk(local_dir):
        dirs[:] = [d for d in dirs if d != ".git"]
        for n in names:
            p = os.path.join(root, n)
            rel = os.path.relpath(p, local_dir).replace(os.sep, "/")
            if rel.startswith(".git/"):
                continue
            mode = "100755" if os.access(p, os.X_OK) else "100644"
            files.append((rel, p, mode))
    return sorted(files)


def main():
    args = sys.argv[1:]
    orphan = "--orphan" in args
    args = [a for a in args if a != "--orphan"]
    owner, repo, local_dir, branch, message = args
    local_dir = os.path.abspath(local_dir)
    files = collect(local_dir)
    print(f"local files: {len(files)}")

    ref = api("GET", f"/repos/{owner}/{repo}/git/ref/heads/{branch}")
    head_sha = ref["object"]["sha"]
    print(f"remote head: {head_sha[:8]}")

    entries = []
    for rel, path, mode in files:
        content = open(path, "rb").read()
        blob = api("POST", f"/repos/{owner}/{repo}/git/blobs", {
            "content": base64.b64encode(content).decode(),
            "encoding": "base64",
        })
        entries.append({"path": rel, "mode": mode, "type": "blob", "sha": blob["sha"]})
    print(f"blobs created: {len(entries)}")

    tree = api("POST", f"/repos/{owner}/{repo}/git/trees", {"tree": entries})
    print(f"tree: {tree['sha'][:8]}")

    parents = [] if orphan else [head_sha]
    commit = api("POST", f"/repos/{owner}/{repo}/git/commits", {
        "message": message,
        "tree": tree["sha"],
        "parents": parents,
    })
    kind = "orphan: replaces all online history" if orphan else "on top of remote head"
    print(f"commit: {commit['sha'][:8]} ({kind})")

    api("PATCH", f"/repos/{owner}/{repo}/git/refs/heads/{branch}", {
        "sha": commit["sha"],
        "force": True,
    })
    print(f"ref updated -> {commit['sha'][:8]}")

    final = api("GET", f"/repos/{owner}/{repo}/git/ref/heads/{branch}")
    print(f"verified ref: {final['object']['sha'][:8]}")


if __name__ == "__main__":
    main()
