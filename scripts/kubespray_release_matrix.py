#!/usr/bin/env python3
"""Extract the supported component versions from a Kubespray release README.

Usage: python3 scripts/kubespray_release_matrix.py release-2.28 release-2.29 ...
Prints a table: release | k8s | etcd | containerd | ansible | python | min k8s
"""
import re
import sys
import urllib.request

UA = {"User-Agent": "cloud-native-guide/version-matrix"}


def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read().decode("utf-8", "replace")


def find(md, label):
    m = re.search(r"\[%s\]\([^)]*\)\s+([0-9][^\s]*)" % re.escape(label), md)
    return m.group(1) if m else "?"


def main():
    for rel in sys.argv[1:]:
        try:
            md = get(f"https://raw.githubusercontent.com/kubernetes-sigs/kubespray/{rel}/README.md")
            k8s = find(md, "kubernetes")
            etcd = find(md, "etcd")
            ctrd = find(md, "containerd")
            cil = find(md, "cilium")
            cal = find(md, "calico")
            helm = find(md, "helm")
            minm = re.search(r"Minimum required version of Kubernetes is v([0-9.]+)", md)
            an = re.search(r"\|>=\s*([0-9.]+),\s*<([0-9.]+)\s*\|\s*([0-9.]+)-([0-9.]+)", md)
            print(f"{rel}: k8s={k8s} etcd={etcd} containerd={ctrd} helm={helm} "
                  f"cilium={cil} calico={cal} min_k8s={minm.group(1) if minm else '?'}")
            if an:
                print(f"    ansible>={an.group(1)},<{an.group(2)} python={an.group(3)}-{an.group(4)}")
        except Exception as e:
            print(f"{rel}: ERR {e}")


if __name__ == "__main__":
    main()
