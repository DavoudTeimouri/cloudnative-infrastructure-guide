# Host security baseline (CIS)

The host baseline is the CIS benchmark for the distribution in use, run in audit
mode first and then remediated, with every accepted deviation recorded here.
Controls that require cluster context are in `kubernetes/security/security-controls.md`;
host build steps are in `operating-systems/host-configuration.md`.

## Method

1. Install the CIS tooling from the internal repository (no public download).
2. Run in audit mode and save the report as the baseline artifact.
3. Remediate, re-run, and record the score.
4. Record each accepted deviation below with its reason and compensating control.

```bash
# Oracle Linux
dnf install -y aqua-sec-cis        # or the CIS-CAT tarball from the internal repo

# Ubuntu
apt install -y cis
```

Both packages may be absent from the mirror; in that case use the CIS-CAT tarball
from `offline-artifacts/artifact-matrix.md`. A missing scanner is not a reason to
skip the baseline.

## Baseline by profile

| Profile | Target | Notes |
|---|---|---|
| Control-plane node | CIS Level 1 Server + Level 2 where it does not break etcd or the API server | Level 2 kernel and audit settings are compatible with stacked etcd |
| Worker node | CIS Level 1 Server | Container runtime needs explicit SELinux/AppArmor policy, not a disabled profile |
| Storage node | CIS Level 1 Server | Same baseline as workers; Ceph daemons need no exemption beyond the data disks |
| Edge node | CIS Level 1 Server, minimal image set | Only the dataplane ports are opened inbound |
| Automation server | CIS Level 1 Server | Holds SSH access to the estate; treat as a tier-0 host |

## Accepted deviations

| Control | Deviation | Reason | Compensating control |
|---|---|---|---|
| Password authentication | Enabled for the local break-glass account on the console | Recovery path when the network or directory is unavailable | Account is local, locked in normal operation, credentials stored offline; every use is logged and reviewed |
| SSH root login | Disabled (`PermitRootLogin no`) — not a deviation, recorded because it is commonly relaxed | — | sudo with an audited account |
| USB storage | Blocked on production hosts | Prevents data exfiltration and unplanned boot media | Firmware-level boot order; physical access controls |
| SELinux/AppArmor | Enforcing on all hosts | Container runtimes need custom policy, not permissive mode | Policies maintained in the `security` Ansible role |

Add new deviations only with an owner, a review date, and a compensating control.
A deviation without those three fields is not accepted; it is an open finding.

## Verification

```bash
# Score, saved as the baseline artifact
cis audit --profile level1-server --report /var/log/cis-baseline-$(date +%F).json

# Spot checks that must agree with the baseline
getenforce                     # Oracle Linux: Enforcing
aa-status                      # Ubuntu: profiles enforced
sshd -T | grep -E 'permitrootlogin|passwordauthentication'
systemctl is-enabled firewalld auditd
```

## Related

- Cluster-level controls: `kubernetes/security/security-controls.md`
- Host build: `operating-systems/host-configuration.md`
- Break-glass design: `decisions/ADR-0015-identity-integration-layer.md`
- Backlog item: `requirements/component-guide-backlog.md` item 37
