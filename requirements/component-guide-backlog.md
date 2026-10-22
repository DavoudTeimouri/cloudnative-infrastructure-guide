# Deliverable 11 — Component Guide Backlog

Implementation order. Every guide follows the section 24 template: A Purpose/Architecture, B Requirements/Compatibility, C Offline Preparation, D Installation, E Integration, F Validation, G Operations, H Best Practices.

## Tier 1 — foundational (before any cluster exists)

| # | Guide | Path | Depends on | Phase |
|---|---|---|---|---|
| 1 | Oracle Linux baseline | `operating-systems/oracle-linux/` | — | 5 |
| 2 | Ubuntu baseline | `operating-systems/ubuntu/` | — | 5 |
| 3 | Automation Management Server | `automation/ansible/` | OS guides | 4 |
| 4 | AWX | `automation/awx/` | automation server | 4 |
| 5 | GitLab + runner | `automation/gitlab-ci/` | automation server | 4 |
| 6 | Offline artifact staging | `offline-artifacts/staging-and-import.md` | — | 2 |
| 7 | Harbor | `offline-artifacts/harbor.md` | artifact staging | 2 |
| 8 | Nexus | `offline-artifacts/nexus.md` | artifact staging | 2 |
| 9 | Internal CA / PKI bootstrap | `secrets-management/pki/` | OS guide | 3 |
| 10 | Keycloak | `management-cluster/keycloak/` | PKI | 3 |
| 11 | Linux identity integration (SSSD/realmd) | `identity/` | AD/LDAP, OS guide | 5 |
| 12 | Load balancer (keepalived/haproxy) | `network-matrix/` | OS guide | 3 |
| 13 | DNS + NTP | `operating-systems/` | OS guide | 3 |

## Tier 2 — platform

| # | Guide | Path | Depends on | Phase |
|---|---|---|---|---|
| 14 | Kubespray cluster lifecycle | `kubespray/` | OS, artifact staging, automation | 7 |
| 15 | Control plane + etcd | `kubernetes/control-plane/` | Kubespray | 7 |
| 16 | Cilium CNI | `kubernetes/networking/` | cluster | 8 |
| 17 | MetalLB | `kubernetes/networking/` | cluster | 8 |
| 18 | L7 ingress (F5 NGINX Ingress Controller) + Gateway API | `kubernetes/ingress/` | MetalLB, cert-manager | 8 |
| 19 | cert-manager | `kubernetes/ingress/` | PKI | 8 |
| 20 | ExternalDNS | `kubernetes/ingress/` | DNS | 8 |
| 21 | Ceph (cephadm) | `storage/ceph/` | OS, storage VLAN | 6 |
| 22 | Rook-Ceph + CSI | `storage/rook-ceph/` | Ceph concepts, cluster | 6/8 |
| 23 | Storage alternatives | `storage/alternatives/` | — | 6 |
| 24 | Rancher | `management-cluster/rancher/` | cluster, Keycloak | 9 |
| 25 | Argo CD | `management-cluster/argocd/` | GitLab, Keycloak | 9 |
| 26 | Platform services (registry UI, dashboards) | `management-cluster/platform-services/` | Harbor, Grafana | 9 |

## Tier 3 — secrets, security, observability

| # | Guide | Path | Depends on | Phase |
|---|---|---|---|---|
| 27 | Vault core | `secrets-management/vault/` | automation server, PKI | 4/10 |
| 28 | Vault Kubernetes auth | `secrets-management/kubernetes-integration/` | cluster | 10 |
| 29 | External Secrets Operator | `secrets-management/kubernetes-integration/` | Vault, cluster | 10 |
| 30 | Vault PKI + cert-manager | `secrets-management/pki/` | Vault | 10 |
| 31 | Vault recovery | `secrets-management/recovery/` | Vault | 10 |
| 32 | Pod Security Standards | `kubernetes/security/` | cluster | 10 |
| 33 | OPA Gatekeeper | `kubernetes/security/` | cluster | 10 |
| 34 | Kyverno | `kubernetes/security/` | cluster | 10 |
| 35 | Falco | `security/falco.md` | cluster | 10 |
| 36 | Image pipeline security (Trivy, Syft, Cosign) | `security/image-security.md` | CI | 10/13 |
| 37 | Host security baseline (CIS) | `security/host-baseline.md` | OS guides | 5/10 |
| 38 | Prometheus + Alertmanager | `monitoring/` | cluster | 11 |
| 39 | Grafana dashboards | `monitoring/dashboards/` | Prometheus | 11 |
| 40 | Thanos (if selected) | `monitoring/` | Prometheus, object storage | 11 |
| 41 | Fluent Bit + Loki | `logging/` | cluster | 11 |
| 42 | OpenSearch (if selected) | `logging/` | cluster | 11 |

## Tier 4 — GPU, AI, mesh, lifecycle

| # | Guide | Path | Depends on | Phase |
|---|---|---|---|---|
| 43 | GPU worker preparation | `gpu-ai/gpu-workers/` | OS guide, cluster | 12 |
| 44 | NVIDIA driver + toolkit | `gpu-ai/drivers/` | GPU worker | 12 |
| 45 | GPU Operator | `gpu-ai/drivers/` | cluster | 12 |
| 46 | GPU scheduling | `gpu-ai/scheduling/` | GPU Operator | 12 |
| 47 | MIG and sharing | `gpu-ai/sharing/` | GPU Operator | 12 |
| 48 | vLLM serving | `gpu-ai/inference/` | GPU, model store | 12 |
| 49 | Multi-GPU inference | `gpu-ai/inference/` | vLLM | 12 |
| 50 | GPU monitoring | `gpu-ai/monitoring/` | DCGM, Prometheus | 12 |
| 51 | Service mesh evaluation | `service-mesh/` | cluster | deferred |
| 52 | Velero backup | `lifecycle/backup/` | cluster, object storage | 9 |
| 53 | Disaster recovery | `lifecycle/disaster-recovery/` | Velero, GitLab backup | 14 |
| 54 | Upgrade runbooks | `lifecycle/upgrades/` | each component guide | 14 |
| 55 | Troubleshooting runbooks | `troubleshooting/` | all | 14 |

## Standing templates

| Template | Path | Used by |
|---|---|---|
| Component guide template | `requirements/component-guide-template.md` | all component guides |
| ADR template | `decisions/ADR-0000-template.md` | all ADRs |
| Version matrix format | `compatibility/version-matrix.md` | all version claims |
| Artifact matrix format | `offline-artifacts/artifact-matrix.md` | all offline artifacts |
