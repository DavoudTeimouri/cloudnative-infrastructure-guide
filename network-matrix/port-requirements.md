# Port requirements — server-to-server access request

Access request matrix for opening host-to-host (and host-to-service) connections
between the servers in this design. One row = one allowed flow. Use it as the
basis for firewall / nftables / security-group rules and for the pre-flight
check that every connection exists before a cluster is declared ready.

Legend: `*` = any/ephemeral source port. `both` = the flow is initiated from
either side. Rows marked `verify` must be confirmed against the pinned release
before firewall rules are cut.

## All connections

| Source IP/Subnet | Source Role/Roles | Source Port | Destination IP/Subnet | Destination Rule | Destination Port | Protocols |
|---|---|---|---|---|---|---|
| 10.10.0.0/24 | Operation server (Ansible, AWX, GitLab runner) | * | All managed nodes | Ansible SSH | 22 | TCP |
| 10.10.0.0/24 | Operation server | * | Vault | Vault API / secrets | 8200 | TCP |
| 10.10.0.0/24 | Operation server | * | GitLab | SCM / CI | 443 | TCP |
| 10.10.0.0/24 | Operation server | * | Management + application K8s API | kubectl / apply / CI | 6443 | TCP |
| DMZ VIP / clients | Ops workstation, external clients | * | Edge load balancer (VIP) | Admin + client access | 443, 22 | TCP |
| Edge LB node | Edge LB (HAProxy/Nginx + Keepalived) | * | Edge LB peer | VRRP advertisements (unicast peers) | 112 | IP proto 112 |
| Edge LB node | Edge LB | * | Kubernetes API (via edge) | Edge-proxied API access | 6443 | TCP |
| Edge LB node | MetalLB speaker | * | MetalLB peers | BGP peering | 179 | TCP |
| DMZ VIP / clients | Clients | * | L7 ingress (F5 NGINX IC / NGF / Envoy) | HTTP/TLS entry | 80, 443 | TCP |
| 10.20.0.0/24 | Control plane | * | etcd (peer) | etcd raft | 2380 | TCP |
| 10.20.0.0/24 | Control plane, workers | * | etcd (client) | etcd client | 2379 | TCP |
| Node subnets | K8s nodes | * | kube-apiserver | Kubernetes API | 6443 | TCP |
| Node subnets | K8s nodes | * | kubelet | exec / logs / metrics / monitoring | 10250 | TCP |
| Node subnets | Nodes | * | NodePort services | NodePort ingress (disable if MetalLB) | 30000-32767 | TCP |
| 10.10.0.0/24 | Prometheus | * | All scrape targets | metrics scrape | 9100, 10250, 6443, 9090, 9101, 8081, 9187 | TCP |
| Monitoring | Alertmanager | * | Alert receivers (SMTP relay) | notifications | 443, 587 | TCP |
| Logging | Log shipper | * | Log backend (Loki / OpenSearch / Logstash) | log ingestion | 3100, 9200, 5044 | TCP |
| Ceph clients | K8s nodes, app nodes | * | Ceph MON | monitor | 6789 | TCP |
| Ceph clients | K8s nodes, app nodes | * | Ceph OSD | OSD data | 6800-7568 | TCP |
| Ceph OSD | Storage nodes | * | Ceph OSD | replication / rebalance | 6800-7568 | TCP |
| Ceph clients | K8s nodes | * | Ceph MDS | CephFS | 6800 | TCP |
| Ceph clients | K8s nodes, app nodes | * | Ceph RGW | S3 API | 7480 | TCP |
| All nodes | All nodes | * | Harbor | image pull | 443 | TCP |
| All nodes | All nodes | * | Nexus | rpm / deb / pypi / helm | 443, 8081 | TCP |
| GitLab Runner | GitLab CI runner | * | GitLab | job coordination | 443 | TCP |
| GitLab Runner | GitLab CI runner | * | Kubernetes API | deploy / validate | 6443 | TCP |
| GitLab Runner | GitLab CI runner | * | Harbor | push images | 443 | TCP |
| Argo CD | Argo CD | * | GitLab | repo fetch | 443 | TCP |
| Argo CD | Argo CD | * | Kubernetes API | apply state | 6443 | TCP |
| Argo CD | Argo CD | * | Vault | secret retrieval | 8200 | TCP |
| Rancher | Rancher server | * | Kubernetes API (managed clusters) | cluster management | 6443 | TCP |
| Keycloak | Keycloak | * | AD / LDAP domain controller | directory sync | 389, 636 | TCP |
| Nodes | All nodes | * | NTP (chrony) | time sync | 123 | UDP |
| Nodes | All nodes | * | DNS (CoreDNS / external) | name resolution | 53 | UDP, TCP |
| GPU node | GPU worker | * | DCGM exporter | GPU metrics | 9400 | TCP |
| GPU node | GPU worker | * | Model store (RGW / MinIO) | model download | 443 | TCP |
| Velero | Velero | * | Object storage (RGW / S3) | backup target | 443 | TCP |
| Velero | Velero | * | Kubernetes API | snapshot / restore | 6443 | TCP |
| Harbor | Harbor | * | PostgreSQL (Harbor DB) | Harbor state | 5432 | TCP |
| GitLab | GitLab | * | PostgreSQL (GitLab DB) | GitLab state | 5432 | TCP |
| Keycloak | Keycloak | * | PostgreSQL (Keycloak DB) | realm state | 5432 | TCP |
| Nexus | Nexus | * | PostgreSQL (Nexus DB) | Nexus state | 5432 | TCP |
| Argo CD HA | Argo CD (HA) | * | Redis | cache / coordination | 6379 | TCP |

## Role groups referenced

| Role | Where it lives |
|---|---|
| Operation server | `architecture/02-deployment-topology.md` — Automation Management Server (Ansible, AWX, GitLab runner), not a K8s node |
| Control plane | Kubespray control-plane nodes, stacked etcd |
| Workers | Application cluster worker nodes (+ GPU workers) |
| Storage nodes | Ceph OSD hosts (Rook in-cluster or cephadm dedicated) |
| Edge LB | HAProxy + Nginx + Keepalived via Docker Compose, two nodes minimum |
| Management cluster | Rancher, Argo CD, Keycloak, Prometheus |
| Application cluster | One or more `appClusters` (see `site` configurator page 2) |
| Ceph | One or more `sdsClusters` (see `site` configurator page 5) |

## Validation

```bash
# From an allowed source, each destination port must be reachable
nmap -Pn -p 22,6443,2379,2380,10250,9100,6789,6800-7568,7480,8200,443,80,53,123 <target>

# From a denied source, expect filtered
nmap -Pn -p 6443,2379,2380 <target>

# Ruleset loaded?
nft list ruleset
firewall-cmd --list-all
```

Rules are generated from this matrix per environment (see
`network-matrix/firewall-rules-generation.md`) and recorded as evidence for
acceptance test B-10.
