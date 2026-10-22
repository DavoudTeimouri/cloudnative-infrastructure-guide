# Linux identity integration (SSSD / realmd)

## A. Purpose and scope

Two operating models, both supported, with a documented migration path between them.

| Model | Description | When to use |
|---|---|---|
| Standalone | Local accounts, local sudo, SSH keys | Small sites, isolated labs, break-glass only |
| Directory-integrated | SSSD against AD or LDAP, local break-glass retained | Production |

Both models keep a local emergency account on every node. Directory integration never removes it.

## B. Package differences

| | Oracle Linux | Ubuntu |
|---|---|---|
| SSSD | `dnf install sssd sssd-tools` | `apt install sssd sssd-ad sssd-tools` |
| realmd | `dnf install realmd` | `apt install realmd` |
| Kerberos | `krb5-user` (krb5-workstation on OL) | `krb5-user` |
| AD provider | `sssd-ad` (part of the AD DC package on OL) | `sssd-ad` |
| Config | `/etc/sssd/sssd.conf` | same |
| Cache | `/var/lib/sss/db/` | same |
| Services | `sssd`, `sssd-be`, `sssd-kcm` | same |

Ubuntu splits the AD support into `sssd-ad`; on Oracle Linux it is usually in the base `sssd` package. Verify with `dnf provides` / `apt-cache search` on the target release.

## C. Standalone model

```bash
# Create a group and user
groupadd -r sre
useradd -m -G sse -s /bin/bash sre-user

# Sudo
echo "%sre ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/90-sre
visudo -c /etc/sudoers.d/90-sre
chmod 0440 /etc/sudoers.d/90-sre

# SSH key
install -d -m 0700 -o sre-user -g sre-user /home/sre-user/.ssh
install -m 0600 -o sre-user -g sre-user authorized_keys /home/sre-user/.ssh/
```

Account lifecycle is managed by Ansible from Git. The password is never stored; the account is key-only.

## D. Directory-integrated model

### Realmd join (AD)

```bash
dnf install -y realmd
realmd discover
realm join --user=join-account EXAMPLE.COM
```

`realm join` requires DNS SRV records for the domain controller to be resolvable. In an offline environment, verify the SRV lookups work before attempting the join:

```bash
dig SRV _ldap._tcp.example.com
dig SRV _kerberos._tcp.example.com
```

If the SRV records are not resolvable, the join fails with a DNS error. Fix DNS first.

### SSSD configuration (AD)

```ini
# /etc/sssd/sssd.conf
[sssd]
services = nss, pam, sshd
domains = EXAMPLE.COM
cache_credentials = true
entry_cache_timeout = 3600
# 8h = 8 hours of offline login before the password cache is exhausted
offline_credentials_expiration = 8h
re-enable_logins = true

[domain/EXAMPLE.COM]
ad_domain = example.com
id_provider = ad
auth_provider = ad
ldap_schema_extensions = idns
access_provider = ad
subdomains = ALL
# Required for nested groups and for the AD "SSH" tab
ldap_id_mapping = schema_only
use_fully_qualified_names_for_forever = true
enumerate = false
```

```ini
# /etc/sssd/sssd.conf (LDAP provider alternative)
[domain/example.com]
id_provider = ldap
auth_provider = ldap
ldap_uri = ldaps://ldap1.example.com ldaps://ldap2.example.com
ldap_search_base = dc=example,dc=com
ldap_id_attrs = uid
ldap_uuid_attribute = entryUUID
```

Key settings and their consequences:

| Setting | Effect | Risk if wrong |
|---|---|---|
| `cache_credentials = true` | Passwords cached for offline login | A revoked AD account can still log in until the cache expires |
| `offline_credentials_expiration` | How long the cache works offline | Too long extends the revocation window |
| `enumerate = false` | Avoids a full domain enumeration at start | `getent passwd` will not list domain users; use `id <user>` instead |
| `ldap_id_mapping = schema_only` | Uses the AD schema for SID mapping | Required for POSIX groups from AD |
| `use_fully_qualified_names_for_forever = true` | `user@domain` form works permanently | Without it, some lookups fail after a change |

### UID/GID mapping

AD assigns a SID; Linux needs a UID/GID. With `ldap_schema_extensions = idns` and `ldap_id_mapping = schema_only`, SSSD derives the UID from the SID via the AD schema, so the mapping is stable and reversible.

Collision risk: a local account with UID 1000 and an AD user mapping to UID 1000 will produce the wrong home directory. SSSD's default range starts at 100000, so the risk is low unless local accounts are created with high UIDs. Keep local accounts below 1000 and the emergency account at a fixed low UID.

### SSH integration

```bash
dnf install -y openssh-server
# SSSD provides the sshd integration module
systemctl restart sshd
```

With `services = nss, pam, sshd`, SSSD answers `AuthorizedKeysCommand` for domain users. Public keys come from the AD user's attributes, so the key distribution is in the directory.

### Sudo with domain groups

```bash
# /etc/sudoers.d/90-domain-sre
%sre-admins@example.com ALL=(ALL) NOPASSWD:ALL
```

Test the group resolution before relying on it:

```bash
getent group sre-admins
id sre-user@example.com
sudo -l -U sre-user@example.com
```

A missing group in `sssd.conf` is the usual cause of "the user can log in but has no privileges".

## E. Break-glass

On every node, regardless of the model:

```bash
useradd -m -s /bin/bash -u 999 emergency
passwd -l emergency                       # key only
install -d -m 0700 /home/emergency/.ssh
# key installed from the offline escrow
usermod -aG wheel emergency                # OL
usermod -aG sudo emergency                 # Ubuntu
```

The emergency SSH key is stored on offline media and in the Vault. It is not in Git. The account must be able to log in with the directory down, which means its key must be in `authorized_keys` and not depend on SSSD.

Test it: stop SSSD (`systemctl stop sssd`) and log in as `emergency`.

## F. Directory outage behaviour

| Situation | Effect |
|---|---|
| DC unreachable, cached credentials exist | Login continues for up to `offline_credentials_expiration` |
| DC unreachable, no cache | Login fails; emergency account still works |
| SSSD service down | Same as DC unreachable |
| AD account disabled in AD | The cached password may still work until the cache expires |
| Group membership changed in AD | SSSD picks it up within `entry_cache_timeout`; running sessions are unaffected |

The revocation window is the security trade-off of offline login. It is a deliberate, documented decision, and the cache timeout must be set deliberately rather than left at the default.

## G. Migration path

Standalone -> directory-integrated:
1. Create the AD users/groups.
2. Set `enumerate = false`, join the host.
3. Create local `~/.ssh/authorized_keys` for the emergency account before joining.
4. Run `sssctl user-checks <user>` to verify the identity path.
5. Test sudo group resolution.
6. Remove the standalone local accounts (keep `emergency`).

Directory-integrated -> standalone (reversal, rare):
1. Create the local accounts from the AD export.
2. Move `/home` if the UIDs differ, or keep the homes and accept the UID change with `chown -R`.
3. Disable the `sssd` service.
4. Keep the break-glass account throughout.

## H. Validation

```bash
# Identity resolution
getent passwd sre-user@example.com
getent group sre-admins
id sre-user@example.com

# SSSD health
sssctl domain-list
sssctl user-checks sre-user@example.com
sssctl auth-check sre-user@example.com

# Offline login simulation
systemctl stop sssd
# attempt login with a cached credential; then restart sssd
systemctl start sssd

# Break-glass
sudo -u emergency sudo -n true
```

## I. Best practices

Mandatory:
- The emergency account exists on every node, key-only, tested with the directory down.
- SSSD cache TTLs set deliberately, not left at default.
- Domain sudo groups verified with `sudo -l -U` before use.
- UID ranges kept disjoint between local and domain accounts.

Strongly recommended:
- `enumerate = false` to avoid a slow full-domain enumeration at boot.
- Service accounts for automation with their own scoped keys, not personal accounts.
- Central group management in AD, not per-host sudoers edits. Per-host sudoers edits are drift.
- Monitor the SSSD service and the SSSD cache directory; a stale cache looks like a healthy system.
