# Deployment Topology (reference sizing, PROVISIONAL)

[Previous step](00-overview.md) | [Next step](03-failure-domains.md)

---

## Server roles

| Role | Count (ref) | Min (prod) | Required? | Notes |
|---|---|---|---|---|
| Automation Management Server | 1 (+1 standby) | 1 | Yes | Ansible, AWX, GitLab runner. Not a K8s node |
| Management control-plane | 3 | 3 | Yes | Rancher, Argo CD, Keycloak, Prometheus |
| Management infra workers | 3 | 2 | Yes | system + platform add-ons, no app workloads |
| Application control-plane | 3 | 3 | Yes | per cluster |
| Application workers (general) | N | 2 | Yes | app workloads |
| GPU workers | N | 1 | Environment | H100/H200 dedicated pool |
| Storage workers | 3+ | 3 | Yes | Rook OSD hosts |
| Artifact/registry services | 2 | 1 | Yes | Harbor + Nexus |
| GitLab | 2 | 1 | Yes | stateful — back up |
| Identity (Keycloak) | 2 | 1 | Yes | external DB strongly preferred |
| Vault | 3 | 1 | Yes | standalone, Raft integrated storage, offline unseal |
| NTP / DNS | 2 | 1 | Yes | chrony; CoreDNS + external |
| Load balancer (edge) | 2 | 2 | Yes | HAProxy + Nginx + Keepalived via Docker Compose. Two nodes minimum, because a single edge node is a single point of failure for every client-facing endpoint |

## Consolidation risk

Consolidating roles onto few hosts lowers cost and raises blast radius. Explicitly discouraged: storage + control plane on one host; Vault inside the cluster it protects; GitLab runner on a control-plane node; identity provider in the same cluster that consumes its secrets.

## Bare metal vs VM

| Concern | Bare metal | VM |
|---|---|---|
| Ceph OSD | Recommended; direct disk, predictable latency | Acceptable with SCSI/PCIe passthrough, not shared storage |
| GPU | Recommended; full NUMA + PCIe topology, MIG on H100/H200 SXM | vGPU/SR-IOV; MIG generally not virtualizable; passthrough required |
| etcd | Low latency to local SSD | Virtual disk + vCPU jitter risk; local SSD + local vCPUs |
| Failure domain | Physical host | Host + hypervisor + storage array |
| Upgrade | Firmware/BIOS in scope | BIOS out of scope; hypervisor tooling in scope |


[Previous step](architecture/02-deployment-topology.md) | [Next step](architecture/03-failure-domains.md)
