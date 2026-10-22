# ADR-0024 — Offline repository and registry design

- **Status**: Accepted (provisional pending Phase 1 review)
- **Date**: 2026-10-22
- **Deciders**: Platform Architect / SecOps / SRE
- **Supersedes / superseded by**: none

## Context

The environment has no internet, so the distribution architecture is a hard constraint.

## Requirements

See `requirements/requirements-and-assumptions.md` (R-01..R-14, D-01..D-14).

## Options considered

- 1. One Nexus for everything.
- 2. Harbor for images plus Nexus for packages.
- 3. GitLab registry plus Nexus.

## Decision

Harbor for OCI images and Helm charts (OCI), Nexus for rpm/deb/PyPI/npm/helm-hosted/raw formats, GitLab for source and CI, and Ceph RGW S3 (or MinIO) for AI model weights. One system of record per artifact type, with no duplication.

## Rationale and trade-offs

- Harbor has image-specific features: scanning, replication, retention, immutability, provenance.
- Nexus covers the long tail of package formats well.
- GitLab registry duplicates Harbor without adding value.
- Splitting by artifact type avoids one system doing everything badly, and it keeps the image-specific governance (scan, sign, retain) in the tool that understands images.

## Security and operational implications

Multiple systems mean multiple auth schemes and multiple backup jobs. The client configuration burden is real: containerd, apt, dnf, pip, Helm, Git, and Ansible each need pointing at the internal source, and TLS trust must be distributed.

## Dependencies

Harbor 443 (and 5000 for the registry component), Nexus 443/8081, GitLab 443, RGW 7480, plus the manager ports for the stateful backing services. All in the network matrix.

## Failure scenarios

Registry outage blocks new deployments but not running workloads, provided images are cached on the nodes. A missing transitive dependency discovered mid-deployment is the most likely failure mode, and it is why a full staging dry run is required before production.

## Migration considerations

Migrating a format from one repository system to another is a re-import plus client reconfiguration. Keeping the mapping in the artifact matrix makes that a scripted operation.
