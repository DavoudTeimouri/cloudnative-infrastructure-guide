# Identity integration

**Decision (ADR-0015): integrate identity at the application layer. Linux nodes are not joined to
a directory.**

No SSSD, realmd, Kerberos membership or `samba`-style join on any host. Nodes keep local
administrative accounts plus one offline break-glass credential. Nothing in the host baseline
depends on the directory being reachable.

## Why not on the hosts

| Reason | Consequence of joining |
|---|---|
| Recovery independence | An unreachable domain controller blocks `sudo` or login exactly when you need it |
| Blast radius | One directory change affects every node, including the ones running Ceph and etcd |
| It buys nothing for workloads | Kubernetes authorization comes from the API server's OIDC/LDAP integration, not from host membership |
| UID/GID mapping | AD UIDs can collide with local ones and change ownership on Ceph OSD directories |
| Audit | Per-service audit logs are richer than a shared host login record |

The cost is explicit: account lifecycle is per service. Removing a person means revoking them in
every integration below, not disabling one host account.

## Targets and protocols

| Service | Integration | Protocol | Group → role mapping |
|---|---|---|---|
| Rancher | AD or LDAP auth provider | LDAPS 636 / StartTLS 389 | Rancher global role per group |
| Keycloak | User federation against AD/LDAP | LDAPS 636 | Realm roles, group→role mapper |
| Harbor | OIDC (via Keycloak) | HTTPS 443 | Project role per group |
| GitLab | LDAP (or OIDC via Keycloak) | LDAPS 636 / HTTPS | Group sync, role per group |
| Argo CD | OIDC (via Keycloak) | HTTPS 443 | RBAC policy per group claim |
| Vault | OIDC (via Keycloak) or LDAP auth | HTTPS 443 / LDAPS 636 | Vault policy per group |
| Kubernetes API | OIDC (via Keycloak) | HTTPS 443 | `RoleBinding`/`ClusterRoleBinding` per group |

Keycloak is the broker. Prefer OIDC from every service to Keycloak and one federation from
Keycloak to the directory: one place to change the directory endpoint, one place to see failed
logins, and services that only speak OIDC stay simple.

## Order of work

1. **Break-glass first.** Confirm a local account with `sudo` and an offline SSH key works on every
   node. Test it with the directory link down. Without this, the rest is a lockout waiting to happen.
2. **Keycloak realm and federation.** Set the LDAP/AD user federation, import groups, and create the
   realm roles. Test with a real federated user before wiring anything else.
3. **Keycloak clients.** One OIDC client per service, with an explicit redirect URI and a group
   claim mapper. No wildcard redirects.
4. **Service by service**, in this order: Argo CD (so the manifests for the rest are under GitOps),
   Rancher, Harbor, GitLab, Vault, then the Kubernetes API server.
5. **Remove the local superuser path** from each service only after the federated path is verified
   for a normal user *and* for an administrator.

## Rancher

```bash
# Rancher UI: Users & Authentication -> Auth Provider -> Active Directory / OpenLDAP
# Server: ldaps://dc.internal:636
# Service account: a read-only bind account, not a domain admin
# User search base / group search base: scope them to the platform OU
# Group schema: name + DN, then map groups to global roles
```

Verify: log in as a federated user, confirm the role comes from the group, then confirm the local
`admin` account still works. Rancher keeps a local admin regardless of the provider state — leave it,
with its password in Vault, and record who may use it.

## Keycloak

```bash
# Federation (UI: User Federation -> ldap), or declarative:
kcadm.sh create components -r platform -s name=corp-ad -s provider=ldap \
  -s 'config.vendor=ad' -s 'config.connectionUrl=ldaps://dc.internal:636' \
  -s 'config.usersDn=OU=Platform,DC=corp,DC=internal' \
  -s 'config.bindDn=CN=svc-keycloak,OU=Service,DC=corp,DC=internal' \
  -s 'config.bindCredential=@/run/secrets/kc-bind' \
  -s 'config.editMode=READ_ONLY' -s 'config.usernameLDAPAttribute=sAMAccountName' \
  -s 'config.uuidLDAPAttribute=objectGUID' -s 'config.groupObjectClasses=group'
```

Rules:

- `editMode=READ_ONLY`. The directory is the source of truth; Keycloak never writes back.
- Bind credential comes from Vault, never from a values file in Git.
- A local realm with two emergency accounts, credentials offline, separate from the federated realm.
  A directory outage must not lock out the platform administrators.
- Group membership drives roles. Do not hand-assign roles to federated users.

## The rest

| Service | Configuration point | Verification |
|---|---|---|
| Harbor | Administration → Authentication → OIDC, client id/secret from Vault, "automatic onboarding" off, group admin mapping | A federated user lands in the group's project with the expected role |
| GitLab | `omniauth`/`ldap` block in `gitlab.rb`, group sync enabled | A group member sees the project and cannot see another group's |
| Argo CD | `oidc.config` + `policy.csv` with `g, <group>, role:readonly`-style rules | A federated read-only user cannot sync |
| Vault | `auth/oidc` role bound to a group claim + policy | Token issued with exactly the expected policy set |
| Kubernetes | `--oidc-issuer-url`, `--oidc-client-id`, `--oidc-groups-claim` on the API server | `kubectl auth can-i --list` as a federated user matches the RoleBinding |

The Kubernetes API server flags are set in the Kubespray group vars
(`kube_apiserver_oidc_*`), so a change goes through the inventory, not through a live edit.

## Failure behavior

| Failure | Effect | Recovery |
|---|---|---|
| Directory unreachable | New UI logins fail; running workloads continue; node SSH unaffected | Local break-glass account, then fix the link |
| Keycloak unavailable | Every OIDC service rejects new sessions; existing tokens last until expiry | Restore Keycloak from backup; local service admin accounts are the interim path |
| Group renamed in the directory | Roles silently disappear or widen, depending on the mapping | Alert on login failures by group; keep mappings in Git and review on directory changes |
| Bind account password rotated | Federation stops with an authentication error in Keycloak logs | Rotation procedure updates the Vault path and the Keycloak component together |

Alert on: failed federated logins per service, a bind failure, and a drop to zero successful logins
during working hours — the last one catches a broken mapping before the ticket arrives.

## What replaces the old host-level procedure

`identity/sssd-realmd.md` was removed. If a cluster genuinely needs host-level directory login (a
regulatory requirement, or a shared jump host), implement it as an explicit per-cluster exception
with SSSD, and record it in an ADR addendum. It is not part of the baseline and the site does not
generate it.
