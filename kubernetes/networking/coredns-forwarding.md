# CoreDNS forwarding

Cluster DNS answers two different question sets: service names inside the cluster, and everything
else. The second set is forwarded upstream. In an air-gapped site the upstream is the internal DNS,
and the forward path is the difference between a cluster that resolves `harbor.internal` and one that
silently times out on every image pull.

## What the configurator sets

| Value | Default | Meaning |
|---|---|---|
| `corednsForwarders` | `10.10.0.53 10.10.0.54` | Upstream resolvers, space separated |
| `corednsForwardPolicy` | `sequential` | Try the first, then the next. `random` spreads load but hides a broken server |
| `corednsCacheTtl` | `30` | Cache TTL in seconds |

Kubespray renders the upstream list from `upstream_dns_servers` in `k8s-cluster.yml`. The generated
`coredns-configmap.yaml` is the same intent expressed as a Corefile patch, for clusters whose
CoreDNS is managed outside Kubespray (or after a manual change).

## The Corefile

```
.:53 {
    errors
    health {
        lameduck 5s
    }
    ready
    kubernetes cluster.local in-addr.arpa ip6.arpa {
        pods insecure
        fallthrough in-addr.arpa ip6.arpa
        ttl 30
    }
    prometheus :9153
    forward . 10.10.0.53 10.10.0.54 {
        policy sequential
        max_concurrent 1000
    }
    cache 30
    loop
    reload
    loadbalance
}
```

`loop` is not optional. Without it, a CoreDNS that forwards to itself (or to a resolver that points
back at it) answers every query with a loop error and the whole cluster loses DNS.

## Domain-specific forwarding

Some zones must not go to the general resolver: an AD domain, a partner network, a legacy zone with
its own servers. Add a server block; the most specific zone wins:

```
corp.internal:53 {
    errors
    cache 30
    forward . 10.10.0.20 10.10.0.21 {
        policy sequential
    }
}
```

Do not forward `cluster.local` anywhere. If a stub domain collides with the cluster domain, rename the
cluster domain in the Kubespray vars (`cluster_name`) before the cluster exists; renaming it after is
a rebuild.

## Verify

```bash
kubectl -n kube-system get configmap coredns -o yaml | grep -A8 "forward"
kubectl run dnstest --rm -it --image={{value.registryHost}}/library/busybox:1.36 --restart=Never -- \
  nslookup harbor.internal
kubectl run dnstest --rm -it --image={{value.registryHost}}/library/busybox:1.36 --restart=Never -- \
  nslookup kubernetes.default.svc.cluster.local
```

Both must answer. If the first works and the second does not, the `kubernetes` plugin or the cluster
domain is wrong; if the second works and the first does not, the forward path is wrong.

## Failure modes

| Symptom | Cause |
|---|---|
| All external names time out, cluster names work | Upstream unreachable, or the node resolver is not the upstream |
| `SERVFAIL` for one zone only | That zone's forward block points at a dead server |
| Intermittent 5s latency on every new name | `policy random` with one broken upstream; switch to sequential |
| CoreDNS pods OOM after a cache change | TTL too high for the query volume; cache memory is proportional to names × TTL |
