# Platform standards

Consolidated standards across the stack. Each item is marked Mandatory, Strongly recommended, or Optional/workload-dependent.

## Naming conventions

| Object | Pattern | Example |
|---|---|---|
| Kubernetes namespace | `<team>-<domain>` | `payments-core` |
| Application (Argo CD) | `<team>-<component>` | `payments-api` |
| Helm release | `<component>` | `argocd`, `cilium` |
| Hostname | `<role><index>` | `k8s-cp-1`, `k8s-gpu-2`, `ceph-st-3` |
| GitLab project | `<domain>-<artifact>` | `platform-obs-monitoring`, `apps-payments` |
| Git branch | `main`, `release/<version>`, `hotfix/<ticket>` | |
| GitLab environment | `<env>` | `staging`, `production` |
| Ansible group | role name from the topology | `control-plane`, `gpu-node` |
| Ceph pool | `<purpose>` | `replicapool`, `cephfs_metadata` |
| Vault path | `<domain>/<team>/<name>` | `secret/apps/payments/db` |
| Grafana dashboard folder | `<domain>` | `storage`, `gpu-ai` |

Rules: lowercase, hyphen-separated, no underscores in Kubernetes names, no version in the name.

## DNS

- Internal zone for all platform endpoints (`*.internal`).
- Every externally-reachable service gets a DNS record managed by ExternalDNS, never a hard-coded IP in Git.
- Split-horizon where the DMZ and the internal zone need different answers for the same name.
- Forwarders to the internal resolver only. No public resolvers.
- TTL: 60 seconds for service records, 3600 for platform records.
- Reverse DNS for every node address.

## IP addressing

| Segment | Range (PROVISIONAL) |
|---|---|
| Management | 10.10.0.0/24 |
| Control plane | 10.20.0.0/24 |
| Pod | 10.30.0.0/16, 10.31.0.0/16 |
| Service | 10.32.0.0/16, 10.33.0.0/16 |
| Storage (public / cluster) | 10.40.0.0/24 / 10.41.0.0/24 |
| GPU | 10.50.0.0/24 |
| DMZ | 10.60.0.0/24 |
| MetalLB pool | 10.61.0.10-10.61.0.30 |

Rules:
- One address plan per site, in Git, versioned.
- No overlap between segments.
- The pod CIDR is never routed to the internet.
- Reserved ranges (RFC 1918 space not used, and the shared address space) are documented and excluded.

## VLAN and network separation

| Segment | VLAN | Isolation |
|---|---|---|
| Management | dedicated | Full access to the automation, registry, identity, and secrets services |
| Control plane | dedicated | Reachable from management and from the control-plane segment only |
| Pod / service | dedicated | Not routable to the internet |
| Storage | dedicated | Only the storage hosts and the clients that mount volumes |
| GPU | dedicated | Plus the RDMA fabric where present |
| DMZ | dedicated | Only the load balancer and reverse proxy |

## Version pinning

- Every artifact has an exact version. No `latest`, no floating Git reference.
- Container images deployed by digest wherever the consumer supports it.
- A version bump is an MR that updates the version matrix, the artifact matrix, and the component guide together.
- Upgrades follow `lifecycle/upgrades/upgrade-procedures.md`.

## Secrets handling

- Vault is the only place a secret value lives.
- Secrets never enter Git, container images, pipeline artifacts, ordinary logs, or values files.
- Kubernetes Secrets hold a synchronized copy where the delivery method requires it; that copy is a separate access boundary and is audited.
- Every secret has an owner, a rotation interval, and a documented revocation path.
- Break-glass credentials are held offline and tested quarterly.

## Certificate management

- One internal CA, rooted in Vault PKI, with the root key offline.
- cert-manager issues and renews every in-cluster certificate.
- leaf lifetime: 90 days. Renewal at 30 days remaining.
- Expiry alerting at 14 days (warning) and 7 days (page).
- Root CA rotation is a multi-step runbook, not a one-line operation.

## RBAC and least privilege

- Humans authenticate through Keycloak (OIDC). No shared accounts, except the documented break-glass.
- RBAC is namespace-scoped for application teams; cluster-admin is held by two named operators.
- Service accounts are per-application, never shared.
- `pods/exec` and `pods/portforward` are restricted by RBAC, because they are equivalent to a shell on the node.
- Vault policies are path-scoped per application and per namespace.
- Quarterly review of cluster-role bindings and of the Argo CD project permissions.

## Firewall policy

- Default deny inbound. Explicit allow rules generated from the network matrix.
- One firewall implementation per host. Never two.
- The matrix is the source of truth; the ruleset is generated from it.
- Every rule carries a purpose in the matrix.

## Image provenance

- Images are built in CI, scanned, SBOM-generated, signed with Cosign, and pushed to Harbor.
- Production deploys by digest.
- Signature verification is enforced in CI and (where the policy engine supports it) at admission.
- Harbor projects are per-team, with retention and immutability tags enabled.
- The vulnerability database is refreshed monthly in the connected staging environment and mirrored offline.

## Backup retention

| Target | Frequency | Retention |
|---|---|---|
| etcd snapshot | Daily | 30 days, 1 copy offline |
| Velero backup | Daily full, plus pre-change | 30 days, 1 copy offline |
| Vault raft snapshot | Daily | 30 days, plus offline escrow of the unseal material |
| GitLab | Daily | 30 days, plus monthly full |
| Harbor and Nexus | Daily | 30 days |
| Keycloak | Daily | 30 days |
| OS and Ansible configuration | Every change (Git) | Indefinite (Git history) |
| AI model artifacts | On change (immutable) | Indefinite |

## Change management

| Change class | Approval | Window |
|---|---|---|
| Documentation | 1 reviewer | Any |
| Application deployment | 1 reviewer | Any |
| Add-on or policy change | 2 reviewers | Any |
| OS baseline or Ansible role | 2 reviewers | Change window |
| Kubernetes upgrade | 2 + platform lead | Change window |
| Storage or Ceph change | 2 + storage owner | Change window |
| Network or firewall change | 2 + network owner | Change window |
| Secrets or PKI change | 2, SecOps only | Change window |
| Emergency change | 1 + post-hoc review | Any, retroactive review within 24 h |

## Monitoring and alerting

- Every component exposes metrics. A component that cannot be scraped is an accepted risk with a written justification.
- Alerts are actionable: every alert has a runbook link and a named owner.
- Cluster-level inhibition so one node failure does not produce hundreds of pages.
- Silence is itself an alert: a Prometheus that cannot scrape a target produces a "no data" alert.
- Paging only on symptoms users feel (availability, latency, data loss risk). Everything else is a ticket.

## Logging and auditing

- All node, control-plane, application, security, and CI logs reach the central backend.
- Redaction happens in the collector, before forwarding.
- Audit logs are retained separately and longer than application logs.
- Audit logs are shipped off-host immediately.
- Kubernetes audit level is `Metadata`; `RequestResponse` on secrets requires a documented decision.

## Resource sizing and capacity thresholds

| Threshold | Action |
|---|---|
| Node CPU > 70% sustained 1 h | Review requests; add capacity |
| Node memory > 75% sustained | Review limits; add capacity |
| Pod memory > 90% of its limit | Fix the request/limit or the application |
| Ceph pool > 70% used | Plan expansion |
| Ceph pool > 80% used | Expand now |
| Prometheus disk > 70% | Reduce retention or expand |
| Log backend disk > 70% | Reduce retention or expand |
| MetalLB pool > 80% assigned | Extend the pool |
| Model cache disk > 80% | Prune old revisions |

## Maintenance windows

- OS patching: monthly, in a defined window, one node at a time.
- Kubernetes minor upgrades: quarterly, staging first.
- Certificate renewal: automatic, with an expiry report weekly.
- Vulnerability database refresh: monthly.
- Restore drill: quarterly for one application, annually for the full environment.
- DR exercise: annually.
- ADR review: annually, or when a decision's assumptions change.

## Incident response

1. Detect (alert or report).
2. Triage: impact, scope, and whether the blast radius matches the failure-domain analysis.
3. Mitigate: restore service first, root cause second.
4. Communicate: who is affected and what is blocked.
5. Recover: verify with the acceptance tests for the affected component.
6. Review: within 5 working days, produce a blameless review and update the runbook, the matrix, and the ADR if needed.

Rules: the break-glass path is used when the normal path is unavailable, not only when it is convenient. Every break-glass use is reviewed.

## Documentation and runbooks

- Every component has a guide following the template in `requirements/component-guide-template.md`.
- Every troubleshooting scenario has a runbook with the seven required sections.
- Every alert links to a runbook.
- Every ADR has a status and a review date.
- Documentation lives in the same Git repository as the code it describes, and a change to one updates the other.

## Configuration drift

- Nightly drift job compares the live state with Git.
- Drift is reported, never silently fixed — except by the designated owner of that object (Argo CD for declared state, Ansible for node state).
- A drift report older than 24 hours is an incident.
- The drift report names the object, the owner, and the expected value.

## Disaster recovery testing

- Quarterly: restore one application from a Velero backup into a scratch namespace.
- Annually: rebuild the entire environment from the documented order, offline, and pass the acceptance tests.
- Annually: restore Vault from a snapshot and unseal with the offline shares.
- Every drill records the measured RTO and compares it to the declared target.
- A drill that fails is a finding, not a formality.
