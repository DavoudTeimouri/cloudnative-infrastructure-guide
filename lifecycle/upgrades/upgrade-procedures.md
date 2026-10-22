# Upgrade procedures

Format for every component upgrade: source -> target, compatibility, pre-validation, offline artifact preparation, backup, dependency and upgrade order, canary, execution, post-checks, rollback feasibility, downtime, risks, success criteria.

## Rules that apply to every upgrade

1. **Never skip a minor version.** Kubernetes supports one minor of skew; Ceph and Istio have explicit supported upgrade paths.
2. **Pin, do not float.** The target version is added to `compatibility/version-matrix.md` with a source URL and a check date before the upgrade starts.
3. **Mirror first, upgrade second.** Every artifact for the target version is in the internal registry and pull-verified before any node is touched.
4. **Backup before the change.** Not "a backup exists" — a backup that has been verified.
5. **One node at a time** for node-level components, with a health check between nodes.
6. **Know the rollback before the upgrade.** If the rollback is not possible, say so explicitly in the change record and get approval for the risk.
7. **Canary first.** Every upgrade runs on a staging copy of the production inventory first.

## Component upgrade summary

| Component | Upgrade path | Reversible? | Order | Offline artifacts |
|---|---|---|---|---|
| Oracle Linux (minor) | `dnf upgrade` | Yes, within the same release | Before node drain | RPMs |
| Oracle Linux (major 8->9) | `leapp` upgrade | **No** | Canary node first | RPMs + leapp data |
| Ubuntu (minor) | `apt full-upgrade` | Yes, within the same release | Before node drain | DEBs |
| Ubuntu (22.04->24.04) | `do-release-upgrade` | **No** | Canary node first | DEBs |
| Kernel | Package update + reboot | Yes, if the old kernel is retained | Drain, upgrade, reboot, verify, uncordon | Kernel + modules |
| containerd | Package update | Yes | Drain nodes one at a time | RPM/DEB |
| Ansible | pip in the venv | Yes | Automation server only | Wheels |
| Helm 3 -> Helm 4 | Install the Helm 4 binary | Partly | Operator tooling first, then the CI and the automation server | Binary |
| Kubespray | New release branch, new inventory | Cluster-level, **no rollback of the cluster** | See below | Images + files_repo |
| Kubernetes | Kubespray `cluster.yml` with a new `kube_version` | **No** | Control plane first, then workers | Images + kubeadm |
| etcd | Managed by Kubespray | **No** | With the control-plane node | Images |
| NGINX Ingress (F5) | Helm upgrade via Argo CD | Yes | Canaries first | Chart + images |
| ingress-nginx (community) | **No path — project retired** | No | n/a | Existing deployments keep running on their pinned version with no further security fixes. Migrate to the F5 controller or NGINX Gateway Fabric |
| Cilium | Helm upgrade via Argo CD | Yes | Canary node pool | Chart + images |
| CSI (Rook) | With the Rook upgrade | Yes | See the Ceph order | Images |
| Ceph (cephadm) | `ceph orch upgrade` | **No across a major version** | mon -> mgr -> osd -> mds -> rgw | RPMs |
| Ceph (Rook) | Rook operator, then `cephVersion.image` | **No across a major version** | Operator first, then Ceph | Images |
| Rancher | Helm upgrade via Argo CD | Yes | Canaries first | Chart + images |
| Harbor | Upgrade procedure per release | Yes | Read the release notes | Images |
| Nexus | Upgrade procedure per release | Yes, after a DB backup | DB backup first | Package |
| GitLab | Omnibus/Helm upgrade | Yes, after a backup | Read the upgrade notes | Package + images |
| Vault | Binary + config upgrade | Yes, with a raft snapshot first | Standby -> active | Binary |
| Keycloak | Upgrade procedure per release | Yes, with a DB backup | DB backup first | Package + images |
| Argo CD | Helm upgrade via Argo CD | Yes | Canaries first | Chart + images |
| Prometheus stack | Helm upgrade via Argo CD | Yes | Canaries first | Chart + images |
| Loki / Fluent Bit | Helm upgrade via Argo CD | Yes | Canaries first | Chart + images |
| Gatekeeper / Kyverno | Helm upgrade via Argo CD | Yes | Audit mode first | Chart + images |
| Falco | Helm upgrade via Argo CD | Yes | Canaries first | Chart + images |
| NVIDIA driver | GPU Operator | Yes, with a drain | One GPU node at a time | RPMs + images |
| NVIDIA GPU Operator | Helm upgrade | Yes, with a drain | One GPU node at a time | Chart + images |
| CUDA components | Image tag change | Yes | With the workload rollout | Images |
| AI inference engine | Deployment image change | Yes | Rolling deployment | Images |
| Model serving platform | Argo CD sync | Yes | Rolling | Images |

## Helm 3 to Helm 4

Helm 3 is in support mode: the final Helm 3 feature release was 2026-09-09, and **security fixes end 2027-02-10** (`https://helm.sh/blog/helm-v3-end-of-life`). Helm 4 is the current stable line.

1. Read the Helm 4 release notes and the HIP-0012 migration notes for the pinned target version.
2. Install the Helm 4 binary alongside Helm 3 on the automation server and in the CI image. Do not replace in place.
3. Run every chart install, upgrade, template, and lint operation with Helm 4 against the full chart set. Helm 4 is expected to be compatible with the majority of existing Helm 3 charts, but "expected" is not "verified": run it.
4. Fix the charts that fail. Each fix is an MR in the owning chart repository.
5. Switch the CI image and the automation scripts to Helm 4.
6. Keep the Helm 3 binary available until 2027-02-10, because Kubespray release-2.32 ships Helm 3.22.0 internally.

Rollback: the Helm 3 binary is kept, so a rollback is a path change. The risk is in the charts: if a chart was modified to work with Helm 4, confirm it still works with Helm 3 before removing the old binary.

## Kubernetes minor upgrade

Source and target: consecutive minor versions only. Both must be in the Kubespray release's supported range.

1. **Compatibility**: read the Kubespray release notes for the target Kubernetes version; confirm the kubeadm version required. Confirm the CNI, CSI, and ingress chart versions support the target Kubernetes version (see `compatibility/version-matrix.md`).
2. **Pre-validation**: `kubectl get nodes -o wide` all Ready, etcd healthy, no pods in `CrashLoopBackOff`, no pending CSI volumes.
3. **Offline artifacts**: mirror the kubeadm binaries, the control-plane images, and any new CNI or CSI images. Pull-verify them.
4. **Backup**: Velero backup plus an etcd snapshot.
5. **Order**: control-plane nodes one at a time, then workers. Kubespray does this sequentially; the control plane is upgraded first.
6. **Canary**: run the same upgrade on a staging cluster with the production inventory.
7. **Execution**: change `kube_version` in the group vars, commit, then `ansible-playbook -i inventory/<cluster>/hosts.ini cluster.yml -b`.
8. **Post-checks**: `kubectl get nodes`, `kubectl get pods -A`, `kubectl --version`, the CSI driver pod version, the ingress controller version, and a functional smoke test per application.
9. **Rollback**: not supported by Kubernetes. The recovery path is the backup restore.
10. **Downtime**: control-plane API availability is maintained by the HA setup; workloads do not restart. Worker pods restart on their node's turn.
11. **Risks**: an incompatible CNI or CSI version is the most common failure; a webhook that does not support the new API version blocks writes.
12. **Success**: all nodes Ready at the new version, all pods running, application checks pass.

## Ceph upgrade (cephadm)

Order is fixed: monitor -> manager -> OSD -> MDS -> RGW.

1. Confirm the source and target are adjacent in the Ceph release sequence and that the path is documented in the target release's upgrade notes.
2. Confirm the target Ceph version is supported by the pinned Rook release if the same cluster is also consumed by Rook.
3. Snapshot: `cephadm shell -- ceph mon dump` and the OSD map, plus a RBD/CephFS backup.
4. Upgrade the manager first: `cephadm shell -- ceph orch upgrade start cephadm`.
5. Then the monitors, one at a time: `cephadm shell -- ceph orch upgrade start mon`.
6. Then the OSDs: `cephadm shell -- ceph orch upgrade start osd`. The orchestrator restarts OSDs one at a time and waits for the cluster to return to HEALTH_OK between them.
7. Then the MDS and RGW.
8. Post-checks: `ceph -s` HEALTH_OK, `ceph versions` shows the target on every daemon, a workload read/write test on RBD and CephFS.
9. Rollback: not possible across a major version. Within a minor version, reinstalling the previous package is possible but not a supported rollback path.
10. Risks: an interrupted upgrade leaves the cluster in a mixed-version state. Ceph supports mixed versions only within a narrow window.

## Rook upgrade

Order: operator -> Ceph -> CSI.

1. Read the target Rook release notes for the supported Ceph version and the supported Kubernetes versions. Both are hard constraints.
2. Mirror the new operator, CSI, and Ceph images.
3. Upgrade the operator via Argo CD.
4. Change `cephVersion.image` to the target Ceph version and apply.
5. Wait for the Rook orchestrator to complete the daemon upgrade.
6. Verify `ceph -s` and that existing PVCs still mount.
7. Rollback: reverting the operator to the previous version is possible; reverting Ceph across a major version is not.

## GPU operator and driver upgrade

1. Read the target operator release notes: the shipped driver version, the shipped toolkit version, and the supported Kubernetes versions.
2. Mirror the driver, toolkit, device plugin, DCGM exporter, and operator images.
3. Drain one GPU node. Verify no GPU pods remain (`kubectl get pods -A --field-selector spec.nodeName=<node>`).
4. Upgrade the operator via Argo CD. The operator upgrades the driver on the node.
5. Verify on the node: `nvidia-smi`, `lsmod | grep nvidia`, and the driver version matching the target.
6. Verify in a pod: run `nvidia-smi` in a test pod on that node.
7. Uncordon and repeat for the next node.
8. Rollback: reinstall the previous driver package and re-apply the previous operator. The driver rollback is straightforward; a workload pinned to a CUDA feature removed in the new driver is not.

## Secret and certificate rotation

Not a version upgrade, but the same discipline applies.

| Item | Trigger | Procedure | Reversible |
|---|---|---|---|
| Vault unseal key | Share rotation | Generate a new key, re-unseal, `vault operator generate-root` | No |
| Vault root token | Compromise or policy | `vault operator generate-root`, revoke the old | No |
| CA intermediate | Planned rotation | Issue a new intermediate from the root, switch issuance, wait for leaf expiry, revoke the old | No |
| Leaf certificate | Expiry or compromise | cert-manager re-issues; for a manual certificate, `openssl` + reload | Yes |
| Repository credential | Rotation schedule | Update in the repository, then in the client config | Yes |
| K8s client certificate | Expiry | Kubespray renews; `kubeadm certs renew` | Yes |

## After every upgrade

- Update `compatibility/version-matrix.md` with the new version, the source URL, and the check date.
- Update `offline-artifacts/artifact-matrix.md` status for the affected artifacts.
- Re-run the affected acceptance tests.
- Record the actual downtime and any deviation from this procedure in the change record.
