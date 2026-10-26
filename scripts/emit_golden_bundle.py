#!/usr/bin/env python3
"""Emit golden-path bundle into site data.

Reads platform/golden-paths/cloudnative-service.yaml and refreshes
site/data.json so the static site and the golden-path CLI share one
source of truth. Stdlib only — no network, no build deps.
"""
import json

GOLDEN_PATH = "platform/golden-paths/cloudnative-service.yaml"
SITE_DATA = "site/data.json"


def load_yaml(path):
    try:
        import yaml
        with open(path) as f:
            return yaml.safe_load(f)
    except ImportError:
        # Minimal fallback: treat the file as a key/value list for the
        # fields we need. Real deployments should install PyYAML.
        data = {}
        current = None
        with open(path) as f:
            for line in f:
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                if stripped.startswith("- name:"):
                    current = stripped.split(":", 1)[1].strip().strip('"')
                    data[current] = {}
                elif current and ":" in stripped:
                    k, v = stripped.split(":", 1)
                    data[current][k.strip()] = v.strip().strip('"')
        return data


def main():
    gp = load_yaml(GOLDEN_PATH)

    # Read existing site data
    with open(SITE_DATA) as f:
        site_data = json.load(f)

    # Merge golden-path metadata into site data
    site_data["goldenPath"] = {
        "name": gp.get("metadata", {}).get("name", "cloudnative-service"),
        "version": gp.get("metadata", {}).get("version", "1.0.0"),
        "description": gp.get("spec", {}).get("description", ""),
        "parameters": gp.get("spec", {}).get("parameters", []),
        "defaults": gp.get("spec", {}).get("defaults", {}),
        "outputs": gp.get("spec", {}).get("outputs", []),
    }

    with open(SITE_DATA, "w") as f:
        json.dump(site_data, f, indent=2)

    print(f"Golden-path bundle emitted into {SITE_DATA}")


if __name__ == "__main__":
    main()
