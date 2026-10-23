# Multiple application clusters

One management cluster, several application clusters. Each application cluster has its own control
plane, its own pod and service CIDRs, its own Ceph (or none), and its own Argo CD registration. What
they share is the management plane, the registry and the identity provider.

## When more than one

| Reason | Split by |
|---|---|
| Failure domain | Site A / Site B, separate power and network |
| Environment | Production / staging / development |
| Tenant or regulation | A cluster per regulated workload, separate audit scope |
| Kubernetes version | A cluster pinned to the previous minor while it drains |

Do not split because a namespace feels crowded. Namespaces, quotas and NetworkPolicies handle that
without a second control plane.

## What must differ per cluster

| Setting | Why it must be unique |
|---|---|
| `clusterName` | It is the kubectl context, the DNS suffix (`cluster.local` stays, but the name is the identity) |
| Pod CIDR | Overlapping pod CIDRs cannot be routed between clusters |
| Service CIDR | Same reason; overlapping services break cross-cluster DNS |
| API VIP | One VIP per control plane |
| Ceph cluster | Two Ceph clusters may share hardware only with separate MONs and CRUSH roots |
| Argo CD registration | One Secret or cluster entry per cluster, named by cluster |

What may be shared: the registry, the NTP and DNS servers, the identity provider, the edge load
balancer (different VIPs or SNI hosts), the backup target.

## How the configurator models it

The **Application cluster** page configures the first cluster fully. Each extra cluster is added with
the **+ Add application cluster** button, which appends a card holding that cluster's name, pod and
service CIDRs, node counts and node sizing. Every card is independent; **Remove** deletes it. The
first card starts with non-overlapping CIDRs derived from the main cluster (10.32.0.0/16 and
10.33.0.0/16 by default), and the numbers are editable.

From those cards the site generates:

- `additional-clusters.yaml` — one record per cluster with name, counts and CIDRs;
- `argocd-cluster-secrets.yaml` — one Argo CD cluster Secret per entry, labelled
  `argocd.argoproj.io/secret-type: cluster`, with the API server placeholder to fill from that
  cluster's `admin.conf`;
- the runbook lists the repeat procedure: run `deploy.sh` again with `CLUSTER=<name>` and that
  cluster's `nodes.tsv`.

The first cluster remains the default context. Every extra cluster needs its own inventory, its own
`k8s-cluster.yml` (different CIDRs) and its own `nodes.tsv`.

## Order of work

1. Build cluster A completely and register it in Argo CD.
2. Build cluster B with its own CIDRs and its own inventory; do not copy cluster A's `k8s-cluster.yml`
   and edit the name — the CIDRs come with it.
3. Register B in Argo CD with its own Secret.
4. Create one ApplicationSet per cluster (or one Application per cluster) so a bad sync in B cannot
   roll out to A.
5. Verify cross-cluster DNS only if you actually need it. Otherwise keep the clusters independent;
   cross-cluster service discovery is a product decision, not a default.

## Failure isolation rules

- No shared etcd. Ever.
- No shared Ceph MON quorum between clusters that must survive independently.
- The management cluster must not depend on any application cluster for DNS, registry or identity.
- Backups go to a target that survives the loss of the cluster, and the restore is tested per
  cluster, not once for all of them.
