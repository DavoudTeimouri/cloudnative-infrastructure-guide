#!/usr/bin/env python3
"""Extract the Ansible/Python compatibility table from a Kubespray release.

Usage: python3 scripts/kubespray_ansible_matrix.py release-2.28 release-2.29 ...
"""
import re
import sys
import urllib.request

UA = {"User-Agent": "cloud-native-guide/version-matrix"}


def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read().decode("utf-8", "replace")


def main():
    for rel in sys.argv[1:]:
        try:
            md = get(
                f"https://raw.githubusercontent.com/kubernetes-sigs/kubespray/{rel}/docs/ansible/ansible.md"
            )
            rows = re.findall(
                r"\|\s*>=\s*([0-9.]+),\s*<([0-9.]+)\s*\|\s*([0-9.]+)-([0-9.]+)\s*\|", md
            )
            print(f"{rel}: {rows if rows else 'no table found'}")
        except Exception as e:
            print(f"{rel}: ERR {e}")


if __name__ == "__main__":
    main()
