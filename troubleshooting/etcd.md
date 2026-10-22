# etcd troubleshooting

## Symptoms

- `kubectl` commands hang or fail with `etcdserver: request timed out`.
- `etcdctl endpoint health` reports unhealthy members.
- Kubernetes API writes fail while reads still work.
- `kubectl get --raw='/readyz?verbose'` shows the `etcd` check failing.

## Likely causes

| Cause | Discriminator |
|---|---|
| Quorum loss (too many members down) | `etcdctl member list` shows fewer than a quorum of healthy members |
| Disk latency or a full disk on an etcd member | `df -h` on the etcd data dir; `etcdctl endpoint status` shows a high `dbSize` and slow responses |
| Clock skew between members | `chronyc tracking` on each member |
| Network partition between members | `etcdctl endpoint health` from each member reports a different view |
| Corrupted member data | `etcdctl alarm list` shows `NOSPACE` or `CORRUPT` |
| Certificate expiry between components | `openssl x509 -enddate -noout -in /etc/kubernetes/pki/etcd/*.crt` |

## Diagnostic commands

```bash
# Member list and health (run on a control-plane node)
ETCDCTL_API=3 etcdctl \
  --endpoints=https://127.0.0.1:2379 \
  --cacert=/etc/kubernetes/pki/etcd/ca.crt \
  --cert=/etc/kubernetes/pki/etcd/healthcheck-client.crt \
  --key=/etc/kubernetes/pki/etcd/healthcheck-client.key \
  member list -w table

ETCDCTL_API=3 etcdctl \
  --endpoints=https://127.0.0.1:2379 \
  --cacert=/etc/kubernetes/pki/etcd/ca.crt \
  --cert=/etc/kubernetes/pki/etcd/healthcheck-client.crt \
  --key=/etc/kubernetes/pki/etcd/healthcheck-client.key \
  endpoint health --cluster -w table

# Endpoint status: version, db size, leader
ETCDCTL_API=3 etcdctl --endpoints=... endpoint status -w table

# Alarms
ETCDCTL_API=3 etcdctl --endpoints=... alarm list

# Slow requests logged by etcd
journalctl -u etcd --since "30 min ago" | grep -i "slow\|took too long\|apply request"
```

## Expected healthy state

```
+------------------------+------------------+---------+---------+-----------+
|        ENDPOINT        |        ID        | VERSION | DB SIZE | IS LEADER |
+------------------------+------------------+---------+---------+-----------+
| https://10.20.0.11:2379 | 8e9e05c52164694d |  3.6.15 | 20 kB  | true      |
| https://10.20.0.12:2379 | 91bc3c398fb3c146 |  3.6.15 | 20 kB  | false     |
| https://10.20.0.13:2379 | fd422379fda50e48 |  3.6.15 | 20 kB  | false     |
```

All three members healthy, one leader, all on the same version, and DB sizes within a few hundred kB of each other.

## Remediation

### Quorum loss

```bash
# Restore the down member first, then check quorum
systemctl status etcd
journalctl -u etcd -n 200
```

If a member's data directory is corrupted and it cannot rejoin:

```bash
# Only with the remaining quorum intact, and after taking a snapshot
ETCDCTL_API=3 etcdctl --endpoints=<healthy-endpoints> member remove <removed-id>
# then re-add the member from a healthy node
```

Removing a member is a quorum-affecting operation. Take a snapshot first and get authorization.

### `NOSPACE` alarm

```bash
df -h /var/lib/etcd
ETCDCTL_API=3 etcdctl --endpoints=... alarm disarm
```

Then free space or compact:

```bash
ETCDCTL_API=3 etcdctl --endpoints=... compact <revision>
ETCDCTL_API=3 etcdctl --endpoints=... defrag --endpoints=<one-at-a-time>
```

Defragment one member at a time. It blocks that member's writes while it runs.

### Clock skew

```bash
chronyc tracking
chronyc makestep
systemctl restart chronyd
```

### Last resort — restore from a snapshot

```bash
# Stop etcd on all members
systemctl stop etcd

ETCDCTL_API=3 etcdctl snapshot restore backup.db \
  --name=<member-name> \
  --initial-cluster <name1>=https://ip1:2380,name2=https://ip2:2380,name3=https://ip3:2380 \
  --initial-advertise-peer-urls https://<this-node-ip>:2380 \
  --data-dir /var/lib/etcd
```

Restore every member from the same snapshot, then start them one at a time and verify the leader.

## Risks

- `member remove` reduces the quorum. With 3 members, removing one leaves no tolerance for a further failure.
- A snapshot restore loses everything written since the snapshot. State the data loss window explicitly.
- Defragmenting all members at once removes the quorum entirely.

## Verification after remediation

```bash
ETCDCTL_API=3 etcdctl --endpoints=... endpoint health --cluster
kubectl get --raw='/readyz?verbose'
kubectl get pods -A
kubectl create job etcd-check --image=bitnami/kubectl:1.36.5 -- /bin/sh -c 'kubectl get nodes'
```

Then re-run acceptance test D-02 (etcd member loss, quorum maintained) if the incident involved a member failure.
