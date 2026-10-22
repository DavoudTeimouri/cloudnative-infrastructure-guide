# Logical Architecture (Mermaid)

```mermaid
graph TB
  subgraph DMZ[DMZ / Edge]
    LB[External LB VIP]
    RP[Reverse Proxy<br/>upstream-compatible URLs]
  end

  subgraph OFF[Offline Distribution]
    HARBOR[Harbor<br/>OCI images]
    NEXUS[Nexus<br/>rpm/deb/pypi/helm/npm]
    GITLAB[GitLab<br/>SCM + CI + registry]
  end

  subgraph AUTO[Automation]
    AMS[Automation Mgmt Server<br/>Ansible + AWX]
    RUNNER[GitLab Runner]
  end

  subgraph ID[Identity and Secrets]
    KC[Keycloak]
    AD[AD / LDAP]
    VAULT[HashiCorp Vault<br/>standalone, outside K8s]
    CA[Internal CA]
  end

  subgraph MGMT[Management Cluster]
    RANCHER[Rancher]
    ARGOCD[Argo CD]
    PROM[Prometheus + Alertmanager]
    GRAF[Grafana]
    LOKI[Loki]
  end

  subgraph APP[Application Cluster]
    WORKER[General Workers]
    GPU[GPU Workers<br/>H100/H200]
    STOR[Storage Workers]
  end

  subgraph STORAGE[Storage]
    ROOK[Rook-Ceph operator]
    MON[MON x3]
    OSD[OSD pool]
    MDS[MDS]
    RGW[RGW S3]
  end

  ADM[Admin workstation] --> AMS
  ADM --> GITLAB
  AMS --> RUNNER
  RUNNER --> ARGOCD
  ARGOCD --> APP
  APP --> HARBOR
  APP --> NEXUS
  AMS --> VAULT
  RUNNER --> VAULT
  VAULT --> K8sAuth
  KC --> AD
  APP --> KC
  ROOK --> MON
  ROOK --> OSD
  ROOK --> MDS
  ROOK --> RGW
  APP --> OSD
  PROM --> APP
  PROM --> STORAGE
  PROM --> ID
  LOKI --> APP
  RP --> LB
  LB --> ARGOCD
  CA --> LB
```

## Critical path

Offline artifact distribution -> OS provisioning -> K8s control plane -> Ceph -> CSI -> Argo CD -> workload.
Secrets and identity sit on the side; they must not gate the restore path (ADR-0025).
