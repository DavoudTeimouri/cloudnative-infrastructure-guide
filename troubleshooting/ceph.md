# Ceph troubleshooting

## Symptoms

- `ceph -s` reports `HEALTH_WARN` or `HEALTH_ERR`.
- A pool is stuck in `active+clean` or `active+remapped+backfilling`.
- A PVC write is slow or times out.
- An OSD is down.
- MON quorum is lost.

## Likely causes and their signatures

| Message | Cause | Action |
|---|---|---|
| `1 pgs degraded` | A single OSD or host is down; the pool is recovering | Replace the OSD. The pool heals itself |
| `1 pgs stuck degraded` | More failures than the replica count can tolerate | Data loss is possible. Stop writes and investigate immediately |
| `osd.N down` | OSD process or host failure | Check the host, then the OSD |
| `OSD(s) ... have full status of down` | OSD is marked out but still referenced | `ceph osd in <id>` |
| `mon.N (age ...)` | A monitor is unreachable | Check the host and the MON port |
| `pgmap_full_percent` | The pool is near full | Add capacity or free space; PGs cannot be created |
| `pgs not deep-scrubbed` | Informational, not an error | Schedule deep scrubs |
| `no candidates for ...` | No eligible OSD for the CRUSH placement | The CRUSH map or the host count does not satisfy the replica size |
| `MON_CLIENT` errors from a CSI pod | Network path or auth problem | Test from the CSI pod's namespace |

## Diagnostic commands

```bash
# cephadm path
cephadm shell -- ceph -s
cephadm shell -- ceph status
cephadm shell -- ceph health detail
cephadm shell -- ceph osd tree
cephadm shell -- ceph osd df
cephadm shell -- ceph df
cephadm shell -- ceph pg stat
cephadm shell -- ceph pg ls
cephadm shell -- ceph mon dump
cephadm shell -- ceph osd df tree
cephadm shell -- ceph crash ls

# Rook path
kubectl -n rook-ceph exec deploy/rook-ceph-operator -- ceph -s
kubectl -n rook-ceph exec deploy/rook-ceph-operator -- ceph health detail
kubectl -n rook-ceph exec deploy/rook-ceph-operator -- ceph osd tree

# Host level
df -h
ceph-volume lvm list
iostat -x 1
```

## Expected healthy state

```
HEALTH_OK
  services:
    mon: 3 daemons, quorum a,b,c
    mgr: 1 daemon, 1 active
    osd: 12 osds: 12 up, 12 in
```

## Remediation

### An OSD is down

```bash
# 1. Identify the host and device
cephadm shell -- ceph osd tree
cephadm shell -- ceph orch device ls

# 2. Check the host
ssh osd-2 "systemctl status ceph-osd@<id>; df -h /var/lib/ceph"

# 3. If the disk is gone, replace it and recreate the OSD
#    cephadm path:
cephadm shell -- ceph orch device ls
cephadm shell -- ceph orch apply osd osd-2 --replace <osd-id>

#    Rook path: add the device to spec.storage.nodes and apply
```

The pool backfills automatically. Watch it:

```bash
watch -n 10 "cephadm shell -- ceph -s"
```

### MON quorum loss

With 3 MONs, losing 1 keeps quorum. Losing 2 does not.

```bash
# Identify and remove the dead mon
cephadm shell -- ceph mon dump
cephadm shell -- ceph mon remove <mon-id>
cephadm shell -- ceph orch apply mon --placement="3 host1 host2 host3"
```

If all 3 MONs are down, the cluster is unrecoverable without the monmap and OSD map backups. That is why those maps are part of the backup set.

### The pool is full

```bash
cephadm shell -- ceph df
cephadm shell -- ceph osd df tree
```

Free space:
```bash
# Remove old snapshots
cephadm shell -- rbd snap ls <image>
cephadm shell -- rbd snap rm <image> <snapshot>
# Remove unused images
cephadm shell -- rbd ls
cephadm shell -- rbd rm <image>
# Or expand the pool
cephadm shell -- ceph osd pool set <pool> size <new-size>
```

### A stuck PG

```bash
cephadm shell -- ceph pg <pgid> query
cephadm shell -- ceph pg <pgid> stuck
cephadm shell -- ceph osd find pgid <pgid>
```

If a PG is stuck because the required OSDs are down, fix the OSDs. Forcing a PG to incomplete loses the consistency guarantee and should be a last resort with explicit authorization:

```bash
cephadm shell -- ceph osd rm-pg-upmap-items <pgid>
```

### Slow IO

```bash
# Per-OSD commit latency
cephadm shell -- ceph osd perf
# Host level
iostat -x 1
# Network between OSDs
iperf3 -c <peer-osd-host>
```

Common causes: a slow journal device, saturated network on the replication path, or an OSD running on an oversubscribed disk. Check the capacity worksheet in `storage/ceph/cephadm-deployment.md` against the measured numbers.

## Risks

- `ceph osd pool delete` destroys data irreversibly. Never run it to "clear" a pool.
- `ceph osd purge` removes an OSD's data. Only after the OSD's data is confirmed replicated elsewhere.
- Removing an OSD during a rebuild slows the rebuild and can push the pool closer to full.
- Changing the CRUSH map triggers data movement. Do it in a window, and only when the pool has headroom.

## Verification after remediation

```bash
cephadm shell -- ceph -s          # expect HEALTH_OK
cephadm shell -- ceph osd tree    # expect all OSDs up and in
# Write test
rbd create --pool rbd --size 1 testvol
rbd map testvol && rbd rm testvol
```

Then re-run acceptance test E-07 (Ceph health sustained for 24 hours) if the incident involved a pool event.
