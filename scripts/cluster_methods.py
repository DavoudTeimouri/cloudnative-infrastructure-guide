#!/usr/bin/env python3
"""Observe Kubernetes cluster installation methods and flag deprecated ones.

Loads catalog/catalog.json and reports each cluster method's lifecycle stage.
A method is "deprecated" when lifecycle == "Deprecated". Deprecated methods
must name a removalDate and a replacement, otherwise --check fails.
"""

import json
import sys

CATALOG = "catalog/catalog.json"


def load():
    with open(CATALOG) as f:
        return json.load(f)


def methods(catalog):
    return catalog.get("clusterMethods", [])


def deprecated(catalog):
    return [m for m in methods(catalog) if m.get("lifecycle") == "Deprecated"]


def check(catalog):
    problems = []
    for m in deprecated(catalog):
        if not m.get("removalDate"):
            problems.append("%s: Deprecated but no removalDate" % m["id"])
        if not m.get("replacement"):
            problems.append("%s: Deprecated but no replacement" % m["id"])
    return problems


def main():
    argv = sys.argv[1:]
    catalog = load()
    if "--check" in argv:
        problems = check(catalog)
        for p in problems:
            print("DEPRECATION CHECK FAIL: " + p)
        if problems:
            sys.exit(1)
        print("cluster methods: %d total, %d deprecated, all deprecated have removal plan" % (
            len(methods(catalog)), len(deprecated(catalog))))
    elif "--self-test" in argv:
        problems = check(catalog)
        print("self-test: deprecated=%d problems=%d" % (len(deprecated(catalog)), len(problems)))
    else:
        for m in methods(catalog):
            flag = ""
            if m.get("lifecycle") == "Deprecated":
                flag = " DEPRECATED -> %s (removal %s)" % (m.get("replacement", "none"), m.get("removalDate", "none"))
            elif m.get("lifecycle") == "Candidate":
                flag = " CANDIDATE"
            print("%s - %s [%s]%s" % (m["id"], m["title"], m.get("lifecycle", "?"), flag))


if __name__ == "__main__":
    main()
