# Internal CA and PKI

Two PKI systems coexist and must not be confused:

| PKI | Issues | Owner | Rotation |
|---|---|---|---|
| Kubernetes internal PKI | API server, kubelet, front-proxy, etcd certificates | Kubespray | Kubespray certificate workflow |
| Platform PKI | Ingress, service, and client certificates | Vault PKI + cert-manager | cert-manager renewal; root rotation by runbook |

Source of the split: `secrets-management/vault/vault-architecture.md` §8.7.

## Chain of trust

```
Offline root CA (Vault PKI root, key offline)
└── Intermediate CA (Vault PKI, online, auto-renewed)
    └── Leaf certificates (cert-manager, Kubernetes TLS Secrets)
```

- The root key is generated once, kept offline, and backed up separately from the
  platform. It is never present on a cluster node.
- The intermediate is the only CA that signs day-to-day. Compromise of the
  intermediate is recoverable by revoking it and issuing a new one from the root.
- Leaf certificates are short-lived and renewed by cert-manager.

## Components and pins

| Component | Pin | Note |
|---|---|---|
| cert-manager | v1.21.2 (chart v1.21.2) | `compatibility/version-matrix.md` |
| cert-manager (Kubespray-managed) | 1.15.3 — not adopted | Older than the standalone chart |
| Vault | v2.2.0, chart 0.34.1 | `compatibility/version-matrix.md` |

## Bootstrap order

1. Build the offline root CA (once per estate). Store the key offline; record the
   custodian and the storage location outside Git.
2. Deploy Vault and configure the PKI secrets engine with the root, then generate
   the intermediate (`secrets-management/vault/vault-architecture.md`).
3. Deploy cert-manager with a `ClusterIssuer` pointing at the Vault intermediate.
4. Issue a test certificate and confirm the chain before any ingress depends on it.
5. Only then configure ingress hosts (`network-matrix/external-load-balancer.md`).

## Operating rules

- No private key is committed to Git or stored in a Kubernetes Secret by hand;
  cert-manager writes TLS Secrets.
- The Vault PKI role constrains allowed domains and maximum TTL. A request outside
  the allowed domains must fail.
- Certificate expiry is alerted at 30, 14, and 7 days. An expired ingress
  certificate is a platform outage for every host behind it.
- The root CA is used only to sign intermediates. Any other use is an incident.

## Validation

```bash
kubectl get clusterissuer
kubectl get certificate -A
kubectl describe certificate -n <namespace> <name>
openssl s_client -connect <host>:443 -servername <host> </dev/null 2>/dev/null | openssl x509 -noout -issuer -dates
```

## Failure scenarios

| Failure | Effect | Recovery |
|---|---|---|
| Intermediate expired | cert-manager cannot issue or renew; existing leaf certificates stay valid until expiry | Re-issue the intermediate from the root |
| Root key lost | No new intermediate can be issued; the chain cannot be extended | Rebuild the PKI and re-issue every certificate — treat as a full certificate replacement |
| cert-manager unavailable | Renewals stop; certificates expire on schedule | Restore cert-manager; existing certificates are unaffected until expiry |
| Vault sealed | Issuance stops | Unseal per `secrets-management/vault/recovery/restore.md` |

## Related

- Root CA rotation: `secrets-management/pki/root-ca-rotation.md`
- Vault PKI design: `secrets-management/vault/vault-architecture.md` §8.7
- Host certificate handling: `operating-systems/host-configuration.md`
