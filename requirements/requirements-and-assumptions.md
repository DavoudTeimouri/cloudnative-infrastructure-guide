# Deliverable 1 — Requirements, Assumptions, Risks

## 1. Confirmed requirements

| ID | Requirement | Source |
|---|---|---|
| R-01 | Kubernetes deployed with Kubespray + Ansible | Master prompt §3 |
| R-02 | Support Oracle Linux and Ubuntu Server | §2.1 |
| R-03 | Ceph as primary SDS; alternatives documented | §10 |
| R-04 | Rancher Management Cluster + independent Application Clusters | §8 |
| R-05 | Fully offline artifact distribution is mandatory | §4 |
| R-06 | OS prep, config, maintenance, upgrades automated | §1.6 |
| R-07 | GitLab for source control, CI/CD, change management | §7 |
| R-08 | Ansible primary; AWX/Semaphore/Rundeck evaluated | §6 |
| R-09 | Prometheus observability + centralized logging | §12, §13 |
| R-10 | Policy enforcement, vulnerability management, runtime detection | §14 |
| R-11 | Centralized secrets management (Vault or justified alternative) | §15 |
| R-12 | Dedicated GPU worker pools for AI/LLM inference | §16 |
| R-13 | Repeatable lifecycle, backup, DR, operational validation | §1.13 |
| R-14 | Complete dependency/version/network/offline inventory | §1.14 |

## 2. Unresolved decisions (require owner input)

| ID | Decision | Options | Default applied | Blocks |
|---|---|---|---|---|
| D-01 | Control-plane size | 3 vs 5 | 3 first environment, 5 reference/production | Kubespray inventory |
| D-02 | etcd topology | stacked vs dedicated | stacked on control-plane | Kubespray inventory |
| D-03 | Ceph deployment model | cephadm / Rook-Ceph / both | Rook-Ceph in K8s + cephadm for external capacity | Storage phase |
| D-04 | CNI | Calico / Cilium | Cilium (eBPF, L7 policy, MetalLB integration) | Network phase |
| D-05 | Secrets product | HashiCorp Vault / OpenBao | **HashiCorp Vault** (Community edition, BSL 1.1, internal use permitted). OpenBao is the fallback if legal rejects the license | Secrets phase |
| D-06 | Automation GUI | AWX / Semaphore / Rundeck | AWX | Automation phase |
| D-07 | Identity source | Keycloak only / AD primary | Keycloak broker, AD/LDAP upstream, local break-glass always | Identity phase |
| D-08 | L7 ingress | NGINX Ingress (F5) / NGINX Gateway Fabric / Traefik | F5 NGINX Ingress Controller (NIC 5.7.0, chart 2.8.0). The community ingress-nginx project is retired and not adoptable | Ingress phase |
| D-09 | Service mesh | none / Istio / Linkerd | none at v1; evaluate at scale threshold | Deferred |
| D-10 | LLM serving engine | vLLM / llama.cpp / Triton | vLLM primary, llama.cpp for edge/GGUF | GPU phase |
| D-11 | GPU sharing | MIG / time-slicing | MIG on H100/H200, time-slicing only for burst dev | GPU phase |
| D-12 | Long-term metrics | Thanos / VictoriaMetrics | Thanos sidecar | Monitoring phase |
| D-13 | Logging backend | OpenSearch / Loki | Loki primary, OpenSearch where full-text search required | Logging phase |
| D-14 | Image registry | Harbor / GitLab registry | Harbor (scan, retention, replication) | Offline phase |

## 3. Assumptions (PROVISIONAL)

| ID | Assumption | Validation step |
|---|---|---|
| A-01 | x86_64 across all roles | `uname -m` on targets |
| A-02 | >=1 Gbps per storage node, 10 Gbps Ceph back-to-back | `iperf3` between OSD nodes |
| A-03 | Separate VLANs: mgmt, control-plane, pod, storage, gpu, dmz | confirm L2 design with network owner |
| A-04 | MTU 1500 on pod/service networks (VXLAN overhead accounted if used) | `ping -M do -s 1472` across nodes |
| A-05 | PDU redundancy per rack for storage and control-plane | facility review |
| A-06 | 25 GbE+ GPU interconnect, NVLink where present | `nvidia-smi topo -m` |
| A-07 | No public CA reachable; internal PKI or self-signed CA with explicit trust distribution | PKI decision |
| A-08 | No inbound internet; egress via controlled staging transfer only | confirm firewall policy |

## 4. Risks

| ID | Risk | Impact | Likelihood | Mitigation | Owner |
|---|---|---|---|---|---|
| RK-01 | Offline dependency closure incomplete (missing transitive artifact) | Deployment blocks mid-way | High | Artifact matrix + staging validation before prod import (§4.3 step 10) | Platform |
| RK-02 | Single automation server becomes control-plane SPOF | All infra changes blocked | Medium | Vault+GitLab backup, documented rebuild path, optional standby automation node | DevOps |
| RK-03 | Vault + Identity + Management Cluster circular dependency | Secrets unrecoverable during outage | Medium | Vault outside Management Cluster, offline unseal material — ADR-0025 | SecOps |
| RK-04 | Ceph failure domain collapsed onto one host/rack | Data loss on rack failure | Medium | CRUSH host/root failure domain, >=3 hosts | Storage |
| RK-05 | Kubespray variable drift between releases | Silent misconfiguration | Medium | Version-pinned inventory + per-release upgrade notes | Platform |
| RK-06 | GPU driver/CUDA/GPU Operator mismatch | No GPU scheduling | Medium | Compatibility matrix + staging canary | AI |
| RK-07 | Certificates expire in offline env | TLS outage | Medium | cert-manager + internal CA, expiry alerting | SecOps |
| RK-08 | Image provenance drift through mirroring | Supply-chain compromise | Medium | Cosign verification, immutable tags in Harbor | SecOps |
| RK-09 | Time skew breaks etcd, Kerberos, TLS | Cluster instability | Low | NTP from internal source, `chronyc tracking` check | Ops |
| RK-10 | Log ingestion floods storage | Logging outage | Medium | Retention + sampling + capacity thresholds | Ops |
