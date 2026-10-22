# Deliverable 6 — Network Communication Matrix

Legend: **R** = required, **O** = optional. Scope column: N2N = node-to-node, P2P = pod-to-pod, C2S = client-to-service, S2E = service-to-external.

Ports marked "verify" must be confirmed against the selected release before firewall rules are cut. Defaults below are the well-known values; the authoritative check is the component's own documentation for the pinned version.

| # | Source | Destination | Proto | Port | Dir | Purpose | R/O | Scope | DNS/Range | Firewall location | Config ref | Validation command | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Any node | Kubernetes API | TCP | 6443 | out | kubectl, Argo CD, Rancher, controllers | R | C2S | 10.20.0.0/24 | mgmt+cp fw | `kubernetes/control-plane/` | `curl -k https://apiserver:6443/healthz` | verify: K8s API server |
| 2 | Control-plane | etcd peer | TCP | 2380 | both | etcd raft | R | N2N | 10.20.0.0/24 | cp fw | `kubespray/groups/etcd.yml` | `ss -lntp \| grep 2380` | verify |
| 3 | Control-plane, workers | etcd client | TCP | 2379 | out | etcd client | R | N2N | 10.20.0.0/24 | cp fw | `kubespray/groups/etcd.yml` | `ss -lntp \| grep 2379` | verify |
| 4 | Control-plane | etcd peer | TCP | 2380 | out | etcd raft | R | N2N | 10.20.0.0/24 | cp fw | `kubespray/groups/etcd.yml` | `etcdctl endpoint health` | verify |
| 5 | Nodes | kube-apiserver health/etcd local | TCP | 10257, 10259 | in | kubelet health, kube-scheduler | R | N2N | cp segment | cp fw | Kubespray defaults | `curl -k https://node:10257/healthz` | verify |
| 6 | Nodes | kubelet | TCP | 10250 | in | exec/logs/metrics, monitoring | R | N2N | mgmt+cp | cp fw | Kubespray defaults | `curl -k https://node:10250/pods` | verify |
| 7 | Workers | NodePort | TCP | 30000-32767 | in | NodePort services (avoid if MetalLB used) | O | C2S | node IPs | dmz fw | K8s config | `kubectl get svc -A` | disable if not used |
| 8 | L4 LB | MetalLB speaker | TCP | 7474 (bgp) / 4789 (bgp) | out | BGP peering | O | N2N | 10.61.0.0/24 | dmz fw | MetalLB config | `kubectl -n metallb-system logs speaker` | verify |
| 9 | MetalLB speaker | peers | TCP | 7946 (TCP), 7946/UDP (gossip) | both | L2/BGP session | R (BGP) | N2N | 10.61.0.0/24 | dmz fw | MetalLB config | `kubectl -n metallb-system get pods` | verify |
| 10 | Clients | Argo CD server | TCP | 443 | in | GitOps UI/API | R | C2S | DMZ VIP | dmz fw | `management-cluster/argocd/` | `curl -k https://argocd/healthz` | verify |
| 10a | Clients | L7 ingress (F5 NGINX Ingress Controller) | TCP | 80, 443 | in | HTTP/TLS traffic entry | R | C2S | DMZ VIP | dmz fw | `kubernetes/ingress/` | `curl -vk https://<vip>/ -H 'Host: app.internal'` | verify: controller service ports, not the retired ingress-nginx defaults |
| 10b | Edge LB node | Edge LB peer | IP proto 112 | 112 | both | VRRP adverts (unicast peers) | R (tier 1/2) | N2N | 10.60.0.0/24 | dmz fw | `network-matrix/external-load-balancer.md` | `docker logs edge-keepalived` | verify: IP protocol 112, not TCP. Unicast peers need the peer address on the VRRP interface |
| 10c | Edge LB node | HAProxy stats (management only) | TCP | 8404 | in | Load balancer statistics | R | N2N | 10.60.0.1/10.60.0.2 | mgmt fw | `manifests/external-lb/haproxy.cfg` | `curl -s http://<lb-mgmt>:8404/` | verify: bound to the management address, never the DMZ address |
| 10d | Edge LB node | Local health listener | TCP | 8443 | local | keepalived health check | R | local | 127.0.0.1 | host fw | `manifests/external-lb/nginx.conf` | `curl -s http://127.0.0.1:8443/healthz` | verify |
| 10e | Edge LB node | Kubernetes API (via edge) | TCP | 6443 | out | Edge-proxied API access for kubectl, Rancher, Argo CD, CI | R | S2E | 10.20.0.100 | dmz fw | `manifests/external-lb/haproxy.cfg` | `curl -k https://<edge>:6443/readyz` | verify |
| 11 | Argo CD | GitLab | TCP | 443 | out | repo fetch | R | S2E | gitlab.internal | dmz fw | `management-cluster/argocd/` | `argocd app list` | verify |
| 12 | Argo CD | K8s API | TCP | 6443 | out | apply state | R | C2S | 10.20.0.0/24 | dmz fw | Argo CD config | `argocd app get` | verify |
| 13 | Argo CD | Vault | TCP | 8200 | out | secret retrieval | R (if used) | C2S | vault.internal | mgmt fw | `secrets-management/vault/` | `vault status` | verify |
| 14 | Argo CD repo-server | GitHub/git | TCP | 443 | out | upstream mirror fetch | O | S2E | — | dmz fw | — | — | only in connected staging |
| 15 | Clients | Rancher server | TCP | 443 | in | cluster management UI | R | C2S | DMZ VIP | dmz fw | `management-cluster/rancher/` | `curl -k https://rancher/v3/health` | verify |
| 16 | Rancher | K8s API | TCP | 6443 | out | cluster mgmt | R | C2S | 10.20.0.0/24 | mgmt fw | Rancher config | Rancher logs | verify |
| 17 | Clients | Keycloak | TCP | 8443 (or 443 behind proxy) | in | SSO/OIDC | R | C2S | DMZ VIP | dmz fw | `management-cluster/keycloak/` | `curl -k https://keycloak/realms/master/.well-known/openid-configuration` | verify |
| 18 | Keycloak | AD/LDAP | TCP | 389, 636 | out | directory sync | R (if AD) | S2E | dc.internal | mgmt fw | `identity/` | `ldapsearch -x -H ldaps://dc` | verify |
| 19 | Nodes | Keycloak | TCP | 8443 | out | OIDC for kubectl/Rancher | O | S2S | keycloak.internal | mgmt fw | `identity/` | `kubectl oidc-login` | verify |
| 20 | Automation server | All managed nodes | TCP | 22 | in | Ansible SSH | R | N2N | mgmt subnet | mgmt fw | `automation/ansible/` | `ansible all -m ping` | verify |
| 21 | Automation server | Vault | TCP | 8200 | out | secrets | R | C2S | vault.internal | mgmt fw | `automation/ansible/` | `vault status` | verify |
| 22 | Automation server | GitLab | TCP | 443 | out | SCM/CI | R | C2S | gitlab.internal | mgmt fw | `automation/gitlab-ci/` | `git ls-remote` | verify |
| 23 | GitLab Runner | GitLab | TCP | 443 | out | job coordination | R | C2S | gitlab.internal | mgmt fw | `automation/gitlab-ci/` | runner registration logs | verify |
| 24 | GitLab Runner | K8s API | TCP | 6443 | out | deploy/validate | R | C2S | 10.20.0.0/24 | mgmt fw | CI config | job log | verify |
| 25 | GitLab Runner | Harbor | TCP | 443 | out | push images | R | C2S | harbor.internal | mgmt fw | CI config | `skopeo inspect` | verify |
| 26 | All nodes | Harbor | TCP | 443 | out | image pull | R | C2S | harbor.internal | mgmt fw | `containerd` config | `crictl pull` | verify |
| 27 | All nodes | Nexus | TCP | 443, 8081 | out | rpm/deb/pypi/helm | R | C2S | nexus.internal | mgmt fw | repo config | `curl -I https://nexus` | verify |
| 28 | Ceph clients | Ceph MON | TCP | 6789 | out | MON | R | N2N | 10.40.0.0/24 | storage fw | `storage/ceph/` | `ceph -s` | verify |
| 29 | Ceph clients | Ceph OSD | TCP | 6800-7568 | out | OSD data | R | N2N | 10.40.0.0/24 | storage fw | `storage/ceph/` | `ceph osd tree` | verify |
| 30 | Ceph clients | Ceph MDS | TCP | 6800 | out | CephFS | R (if CephFS) | N2N | 10.40.0.0/24 | storage fw | `storage/ceph/` | `ceph fs status` | verify |
| 31 | Ceph clients | RGW | TCP | 7480 | out | S3 API | R (if RGW) | N2N | 10.40.0.0/24 | storage fw | `storage/ceph/` | `curl http://rgw:7480` | verify |
| 32 | Ceph OSD | Ceph OSD | TCP | 6800-7568 | both | replication/rebalance | R | N2N | 10.41.0.0/24 | storage fw | `storage/ceph/` | `ceph osd perf` | verify |
| 33 | Prometheus | All scrape targets | TCP | 9100, 10250, 6443, 8080, 9101, 8081, 9090, 9187 | out | metrics scrape | R | N2N | varies | mgmt fw | `monitoring/` | `promtool` targets UI | verify per exporter |
| 34 | Alertmanager | Alert receivers | TCP/SMTP | 443/587 | out | notifications | R | S2E | relay/mail | mgmt fw | `monitoring/` | `amtool alert list` | verify |
| 35 | Log shipper | Log backend | TCP | 3100 (Loki), 9200 (OpenSearch), 5044 (Logstash) | out | log ingestion | R | C2S | 10.70.0.0/24 | mgmt fw | `logging/` | backend health API | verify |
| 36 | Users | Grafana | TCP | 443 | in | dashboards | R | C2S | DMZ VIP | dmz fw | `monitoring/` | `curl -k https://grafana/api/health` | verify |
| 37 | Users | OpenSearch Dashboards | TCP | 443 | in | log search UI | O | C2S | DMZ VIP | dmz fw | `logging/` | `curl -k https://opensearch` | verify |
| 38 | Vault | AD/LDAP | TCP | 636 | out | AD auth backend | O | S2E | dc.internal | mgmt fw | `secrets-management/vault/` | `vault auth list` | verify |
| 39 | Vault | KMS | TCP | varies | out | auto-unseal | O | S2E | kms.internal | mgmt fw | `secrets-management/vault/recovery/` | seal status | verify |
| 40 | Velero | Object storage | TCP | 443 | out | backup target | R | S2S | RGW/S3 | mgmt fw | `lifecycle/backup/` | `velero backup get` | verify |
| 41 | Velero | K8s API | TCP | 6443 | out | snapshot/restore | R | C2S | 10.20.0.0/24 | mgmt fw | `lifecycle/backup/` | `velero backup create` | verify |
| 42 | Gatekeeper | K8s API | TCP | 6443 | both | admission webhook | R | C2S | 10.20.0.0/24 | mgmt fw | `kubernetes/security/` | `kubectl get validatingwebhookconfigurations` | verify |
| 43 | GPU node | DCGM exporter | TCP | 9400 | in | GPU metrics | R | N2N | 10.50.0.0/24 | gpu fw | `gpu-ai/monitoring/` | `curl http://node:9400/metrics` | verify |
| 44 | NVIDIA container runtime | NVIDIA driver | n/a | local | n/a | GPU access | R | local | — | — | `gpu-ai/drivers/` | `nvidia-smi` | local |
| 45 | GPU node | K8s API | TCP | 6443 | out | scheduling | R | C2S | 10.20.0.0/24 | mgmt fw | `gpu-ai/scheduling/` | `kubectl get nodes -l nvidia.com/gpu.present=true` | verify |
| 46 | GPU node | model store (RGW/MinIO) | TCP | 443 | out | model download | R | C2S | storage segment | storage fw | `gpu-ai/inference/` | `curl -I https://models` | verify |
| 47 | Clients | LLM inference API | TCP | 8000 | in | OpenAI-compatible API | R | C2S | DMZ VIP | dmz fw | `gpu-ai/inference/` | `curl http://vllm:8000/v1/models` | verify |
| 48 | Nodes | NTP | UDP | 123 | out | time sync | R | S2E | ntp.internal | mgmt fw | OS guide | `chronyc tracking` | verify |
| 49 | Nodes | DNS | UDP/TCP | 53 | out | name resolution | R | S2E | dns.internal | mgmt fw | OS guide | `dig +short kubernetes.default` | verify |
| 50 | Ops workstation | Cluster mgmt VIPs | TCP | 443, 22 | in | admin access | R | C2S | DMZ | dmz fw | OS guide | `curl -k` | verify |
| 51 | All | SMTP relay | TCP | 587 | out | alerts | O | S2E | mail.internal | mgmt fw | `monitoring/` | `swaks --server` | verify |
| 52 | AD/LDAP clients | DC | TCP | 389/636 | out | directory | R | S2E | dc.internal | mgmt fw | `identity/` | `id testuser` | verify |
| 53 | Kerberos KDC | clients | UDP/TCP | 88 | both | Kerberos auth | R (if Kerberos) | N2N | mgmt subnet | mgmt fw | `identity/` | `kinit -V` | verify |
| 54 | Harbor | DB (PostgreSQL) | TCP | 5432 | out | Harbor state | R | S2E | 10.80.0.0/24 | mgmt fw | Harbor config | `pg_isready` | verify |
| 55 | GitLab | DB (PostgreSQL) | TCP | 5432 | out | GitLab state | R | S2E | 10.80.0.0/24 | mgmt fw | GitLab config | `pg_isready` | verify |
| 56 | Keycloak | DB (PostgreSQL) | TCP | 5432 | out | realm state | R | S2E | 10.80.0.0/24 | mgmt fw | Keycloak config | `pg_isready` | verify |
| 57 | Argo CD HA | Redis | TCP | 6379 | out | cache/coordination | R (HA) | S2E | 10.80.0.0/24 | mgmt fw | Argo CD HA doc | `redis-cli ping` | verify |
| 58 | Docker registry | registry | TCP | 5000 | out | registry storage (Harbor) | R | N2S | 10.80.0.0/24 | mgmt fw | Harbor config | `curl http://registry:5000/v2/` | verify |
| 59 | Nexus | DB (PostgreSQL) | TCP | 5432 | out | Nexus state | R | S2E | 10.80.0.0/24 | mgmt fw | Nexus config | `pg_isready` | verify |

## Validation of the matrix

Semi-automated: export live listeners and compare to the matrix.

```bash
# List all listening TCP/UDP ports on a node
ss -tulpn

# Prometheus: which targets are down
kubectl -n monitoring get pods -l app.kubernetes.io/name=prometheus -o name
kubectl -n monitoring exec sts/prometheus-kube-prometheus-prometheus -c prometheus -- \
  wget -qO- http://localhost:9090/api/v1/targets | head -c 2000
```

Firewall rules are generated from this matrix per environment. See `network-matrix/firewall-rules-generation.md`.
