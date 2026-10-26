# Root CA rotation runbook

Rotation replaces the root that signs the platform intermediate. It is
downtime-sensitive and cannot be done in one step: certificates already issued
remain valid until they expire, so the old and new chains coexist during the
transition.

Prerequisite reading: `secrets-management/pki/index.md`,
`secrets-management/vault/vault-architecture.md` §8.7.

## When to rotate

- Scheduled rotation per the estate's cryptographic policy.
- Suspected or confirmed root key compromise (then rotate immediately, and treat
  every issued certificate as untrusted).
- Change of custody or storage medium for the root key.

## Order of operations

1. **Prepare.** Generate the new root key and self-signed root certificate offline.
   Record the custodian, storage location, and serial number. Do not touch the
   running intermediate yet.
2. **Distribute trust.** Add the new root certificate to every trust store that
   validates platform certificates — nodes, ingress clients, and any external
   system that pins the chain. Both roots are trusted at this point.
3. **Issue the new intermediate.** From the new root, issue an intermediate and
   import it into Vault's PKI engine alongside the old one.
4. **Switch issuance.** Point the cert-manager `ClusterIssuer` at the new
   intermediate. New certificates now chain to the new root; existing ones still
   chain to the old.
5. **Wait for leaf expiry.** Keep the old intermediate and old root trusted until
   the longest-lived certificate issued under the old chain has expired. Do not
   revoke the old intermediate before this point, or every unexpired certificate
   becomes invalid at once.
6. **Retire.** Revoke the old intermediate, remove the old root from trust stores,
   and archive the old root key according to the retention policy.

Steps 2 and 5 are the long poles. Skipping step 2 breaks every client that has not
yet learned the new root; skipping step 5 causes an outage when the old
intermediate is revoked.

## Verification

```bash
# Issuer now points at the new intermediate
kubectl get clusterissuer -o yaml | grep -A3 vault

# Newly issued certificate chains to the new root
kubectl get certificate -A
openssl s_client -connect <host>:443 -servername <host> </dev/null 2>/dev/null \
  | openssl x509 -noout -issuer -dates

# Old root still trusted during the transition (expected until step 6)
openssl verify -CAfile /etc/ssl/certs/ca-certificates.crt <leaf>.pem
```

## Rollback

Before step 6, rollback is a configuration change: point the `ClusterIssuer` back
at the old intermediate. After step 6, rollback requires re-trusting the old root
and re-issuing under the old intermediate — treat it as a new rotation, not a
revert.

## Record keeping

Record in the change ticket: old and new root serials, intermediate serials,
the date each trust store was updated, the expiry date of the last certificate
issued under the old chain, and the date the old root was removed from trust.
