# ADR-0005 — Container runtime

- **Status**: Accepted (provisional pending Phase 1 review)
- **Date**: 2026-10-22
- **Deciders**: Platform Architect / SecOps / SRE
- **Supersedes / superseded by**: none

## Context

Kubespray supports containerd, Docker, and CRI-O. The runtime must match the offline image distribution design and the GPU stack.

## Requirements

See `requirements/requirements-and-assumptions.md` (R-01..R-14, D-01..D-14).

## Options considered

- 1. containerd.
- 2. Docker (via cri-dockerd).
- 3. CRI-O.

## Decision

containerd. It is the upstream default, has native registry mirror/TLS configuration, and is the runtime the NVIDIA Container Toolkit integrates with.

## Rationale and trade-offs

- Native image pull policy, no daemon socket privilege.
- Docker adds a socket and a shim layer.
- CRI-O is fine but less common in offline images.
- containerd is the boring, supported default with the cleanest offline-mirror story.

## Security and operational implications

containerd is the component that holds the registry trust and mirror configuration, so it is also the security-relevant choice for offline operation.

## Dependencies

containerd API/registry config paths and the CRI plugin version. Verify against the pinned Kubespray release and the containerd release notes.

## Failure scenarios

A broken containerd config takes down image pulls on the node, but running containers keep running until they need to restart.

## Migration considerations

Switching runtimes means rebuilding nodes. Kubespray supports it but it is a node-level operation, not a live migration.
