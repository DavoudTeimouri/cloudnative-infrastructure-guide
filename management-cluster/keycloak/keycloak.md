# Keycloak identity provider

## A. Purpose and architecture

Keycloak is the identity broker for the platform. Applications integrate with it via OIDC; the directory service (AD or LDAP) is the upstream source for some realms.

```
  browser / kubectl / CI
        |
  keycloak.internal:8443 (or 443 behind the site proxy)
        |
  +-------------------+
  | realm: platform   |  -> applications (Rancher, Argo CD, Grafana, Harbor, Vault, GitLab)
  | realm: ai         |  -> inference API gateway
  | realm: external   |  -> AD / LDAP upstream
  +-------------------+
        |
  PostgreSQL (external, shared with other stateful services)
```

## B. Deployment

Keycloak runs in the Management Cluster, but the database is external (PostgreSQL on the platform database host) so a cluster loss does not take the identity store with it. The identity provider is a restore dependency, so it must not live only inside the thing it protects (ADR-0025 reasoning applied to identity).

```yaml
# values.yaml (subset)
replicas: 2
image:
  repository: harbor.internal/platform/keycloak/keycloak
  tag: "26.8.1"
dbchecker:
  image:
    repository: harbor.internal/platform/keycloak/keycloak
extraEnv: |
  - name: KC_HOSTNAME
    value: keycloak.internal
  - name: KC_HTTP_ENABLED
    value: "true"
  - name: KC_PROXY_HEADERS
    value: xforwarded
  - name: KC_HEALTH_ENABLED
    value: "true"
  - name: KC_DB
    value: postgres
  - name: KC_DB_URL_HOST
    value: postgres.platform-db.internal
  - name: KC_DB_URL_DATABASE
    value: keycloak
  - name: KC_DB_USERNAME
    value: keycloak
  - name: KC_DB_PASSWORD
    value: ${DB_PASSWORD}
  - name: JAVA_OPTS_APPEND
    value: "-XX:MaxRAMPercentage=70.0"
command:
  - "/opt/keycloak/bin/kc.sh"
  - "start"
  - "--http-enabled=true"
  - "--hostname-strict=false"
```

The database password comes from an ExternalSecret, never from the values file.

## C. Realms

| Realm | Purpose | Upstream |
|---|---|---|
| `platform` | Operators and developers of the platform | AD/LDAP federation, plus a local `breakglass` realm for emergency accounts |
| `ai` | Service accounts and tenant identities for the inference API | Local |
| `external` | Federates to AD/LDAP and exposes it to the other realms | AD/LDAP |

Federation setup for AD (in the `external` realm):

```bash
# In the external realm, add an LDAP provider
kc.sh config ldap --hostname=ldap.internal --port=636 --protocol=ldaps \
  --truststore-path=... --truststore-password=... \
  --bind-dn="cn=svc-keycloak,ou=services,dc=example,dc=com" \
  --bind-credential="$BIND_PASSWORD" \
  --users-query="(&(objectClass=person)(sAMAccountType=805306368)(uid={0}))" \
  --username-attribute=uid \
  --first-name-attribute=givenName \
  --last-name-attribute=sn \
  --email-attribute=mail \
  --group-query="(&(objectClass=group)(member={0}))" \
  --groups-attribute=memberOf
```

Bind credential is a service account password, stored in Vault and fetched at configuration time.

## D. Clients

| Client | Type | Redirect URI | Notes |
|---|---|---|---|
| `rancher` | Confidential | `https://rancher.internal/oidc/authorize` | `groups` and `uid` claims required |
| `argocd` | Confidential | `https://argocd.internal/auth/callback` | Same |
| `grafana` | Confidential | `https://grafana.internal/login/generic_oauth` | `email` and `groups` required |
| `harbor` | Confidential | `https://harbor.internal/c/oidc/callback` | |
| `gitlab` | Confidential | `https://gitlab.internal/users/auth/oidc/callback` | |
| `argocd-ci` | Confidential | none | Client credentials, for CI |
| `ai-gateway` | Confidential | `https://llm.internal/callback` | Token validation for inference |

Every client is confidential with a client secret stored in Vault. Public clients are avoided entirely — there is no case here that needs one.

Protocol mapper for `groups` (required by Rancher and Argo CD):

- Mapper type: `Group membership`
- Claim name: `groups`
- Full path: off
- Add to ID token: on
- Add to access token: on

Protocol mapper for `uid`:

- Mapper type: `User Attribute`
- User attribute: `uid`
- Claim name: `uid`
- Add to ID token: on

## E. Roles and group mapping

| Keycloak group | Platform role | Grants |
|---|---|---|
| `platform-admins` | Administrator | Everything |
| `platform-operators` | Operator | Cluster and platform operations, no secret values |
| `developers` | Developer | Own namespaces only |
| `auditors` | Auditor | Read-only access to logs and audit data |
| `team-<name>` | Team member | The team's namespace and its Argo CD project |

Group membership is authoritative in the directory. Do not manage groups in Keycloak for federated users.

## F. Session and token settings

| Setting | Value | Reason |
|---|---|---|
| SSO session idle | 30 min | Limits the exposure window of an unattended workstation |
| SSO session max | 10 h | Bounds the re-authentication burden |
| Access token lifespan | 5 min | Short-lived access tokens limit the blast radius of a leaked token |
| Refresh token lifespan | 30 min | |
| Offline sessions | off | No persistent sessions on shared workstations |
| Revoke refresh token | on | A logout invalidates the refresh token too |
| Brute force detection | on | Protects against password guessing |

Access tokens are short-lived on purpose. Every application that caches an access token must handle expiry, or it will present an expired token and get a 401 during normal operation. This is the most common OIDC integration bug.

## G. Offline operation

Keycloak does not need the internet. It needs:

- The database (local PostgreSQL).
- The CA certificate for the internal TLS endpoints.
- The AD/LDAP endpoint for federated realms. If the directory is down, Keycloak itself keeps running and issues tokens for local users; federated logins fail.

Break-glass: a local realm with a small number of emergency accounts, whose credentials are held offline. Keep this separate from the federated realms so a directory outage does not lock out the administrators.

## H. Validation

```bash
# Discovery document
curl -k https://keycloak.internal/realms/platform/.well-known/openid-configuration | jq .

# Token issue with a client-credentials grant
curl -sk -X POST \
  https://keycloak.internal/realms/platform/protocol/openid-connect/token \
  -d grant_type=client_credentials \
  -d client_id=argocd-ci \
  -d client_secret="$SECRET" | jq -r .access_token

# Groups claim present
curl -sk -X POST ... | jq -r '.access_token' | cut -d. -f2 | base64 -d 2>/dev/null | jq .groups
```

Expected: the ID token contains `groups` and `uid` for a federated user.

## I. Operations

| Task | Procedure |
|---|---|
| Add a client | `kc.sh create clients` or the admin console; the secret goes to Vault immediately |
| Rotate a client secret | Create a new secret, update the consumer, verify, then remove the old one |
| Export a realm | `kc.sh export --realm platform --users skip --directory /backup/keycloak` |
| Import a realm | `kc.sh import --realm platform --file /backup/keycloak/platform-realm.json` |
| Backup | PostgreSQL dump plus the realm export; the export is for review and for a rebuild, the dump is the recovery source |
| Upgrade | Read the release notes for the Keycloak version, back up the database, upgrade, run the automatic migration, verify the realm import |

## J. Best practices

Mandatory:
- The database outside the cluster.
- Client secrets in Vault, rotated on a schedule and immediately on suspected exposure.
- The `groups` and `uid` claims verified in the ID token before any application integrates.
- A local break-glass realm with offline-held credentials.
- Short access token lifetimes, with every application prepared for expiry.

Strongly recommended:
- A dedicated realm per trust boundary, so a compromise in one does not reach the others.
- Federation rather than user sync, so the directory stays the single source of truth.
- Alert on the Keycloak health endpoint and on authentication failure rates.
- Alert on the certificate expiry of the Keycloak endpoint.
