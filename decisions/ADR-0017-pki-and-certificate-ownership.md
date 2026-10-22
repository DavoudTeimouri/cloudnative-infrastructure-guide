# ADR-0017 — PKI and certificate ownership

- **Status**: Accepted (provisional pending Phase 1 review)
- **Date**: 2026-10-22
- **Deciders**: Platform Architect / SecOps / SRE
- **Supersedes / superseded by**: none

## Context

TLS is required everywhere, offline, with renewal.

## Requirements

See `requirements/requirements-and-assumptions.md` (R-01..R-14, D-01..D-14).

## Options considered

- 1. cert-manager with an internal CA.
- 2. cert-manager with Vault PKI.
- 3. External enterprise CA with an ACME/EST bridge.

## Decision

cert-manager as the Kubernetes-side issuer and renewer, backed by Vault PKI for the internal CA, with the root CA key stored offline. Enterprise CA integration is supported if the site owns one, via a documented bridge.

## Rationale and trade-offs

- One renewal engine in the cluster.
- Vault PKI keeps the CA key inside the secrets manager.
- An enterprise CA centralizes policy across non-K8s systems.
- Vault PKI plus cert-manager gives automated renewal with the CA key protected, and Vault is already required for secrets. The trust distribution burden is real and is handled by the OS baseline.

## Security and operational implications

An internal CA means trust must be distributed to every client (OS trust store, container images, Java keystores). Missing trust distribution is the most common cause of offline TLS failures. If a Vault outage stops issuance, renewals fail at the CA layer and that path needs to be documented.

## Dependencies

Vault 8200, cert-manager webhook 6443, ACME/EST port as configured. Verify per release.

## Failure scenarios

CA unavailability stops issuance and renewal. Existing certificates keep working until expiry, so expiry alerting is mandatory.

## Migration considerations

Root CA rotation is a multi-step process with no instant cutover: issue a new intermediate, move issuance, wait for leaves to expire, revoke the old intermediate. It is not a single command.
