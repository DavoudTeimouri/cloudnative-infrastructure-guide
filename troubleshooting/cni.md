# CNI and network policy troubleshooting

## Symptoms

- Pods stay `ContainerCreating` with a network error.
- Pod-to-pod traffic between nodes fails; same-node traffic works.
- A NetworkPolicy blocks traffic that should be allowed.
- DNS resolution from inside a pod fails.
- The API server is unreachable from a node.

## Likely causes

| Cause | Discriminator |
|---|---|
| CNI agent not ready | `kubectl -n kube-system get pods -l k8s-app=cilium` |
| MTU mismatch between the pod network and the physical network | `ping -M do -s 1472` across nodes fails, same-node succeeds |
| Missing route for the pod CIDR | On the node: `ip route get <pod-ip>` fails; on a router: no route for the pod CIDR |
| kube-proxy not installed and Cilium's replacement not enabled | `kubectl -n kube-system get ds kube-proxy` absent AND `kubeProxyReplacement` not set |
| A default-deny NetworkPolicy with no allow rule | Traffic fails only for pods in that namespace |
| IPtables/ipvs rules stale | Services do not resolve to a backend |
| DNS service unreachable | `nslookup kubernetes.default` from a pod fails |

## Diagnostic commands

```bash
# CNI status
kubectl -n kube-system get pods -l k8s-app=cilium -o wide
cilium status --verbose
cilium connectivity test

# Hubble (Cilium observability)
cilium hubble list
cilium hubble observe --namespace default

# Node routes
ip route get <remote-pod-ip>
ip -br addr

# MTU
ping -M do -s 1472 <peer-node-ip>     # 1472 + 28 = 1500
ping -M do -s 1400 <peer-node-ip>     # smaller payload

# Service resolution from a pod
kubectl run nettest --rm -it --restart=Never --image=busybox:1.36 -- \
  nslookup kubernetes.default.svc.cluster.local
kubectl run nettest --rm -it --restart=Never --image=busybox:1.36 -- \
  wget -S -O- --timeout=5 http://<service>.<ns>.svc.cluster.local

# Network policies in a namespace
kubectl get networkpolicies -n <ns>
kubectl get ciliumnetworkpolicies -n <ns>
kubectl get cnp -n <ns> -o yaml

# Kube-proxy / service handling
kubectl -n kube-system get ds kube-proxy
iptables -t nat -L KUBE-SERVICES -n | head -30
```

## Expected healthy state

- `cilium status`: `KubeProxyReplacement: True` when enabled, `KVStore: Disabled` for the embedded etcd mode, all agents `Ready`.
- `cilium connectivity test`: all probes pass.
- A pod can resolve `kubernetes.default.svc.cluster.local` and reach the API.
- `ip route get <remote-pod-ip>` returns a route on the node.

## Remediation

### MTU

Set the MTU to the physical network MTU minus the encapsulation overhead, then restart the CNI agent.

```yaml
# Cilium Helm values
ipam:
  mode: kubernetes
ipv4:
  enabled: true
mtu: 1450        # 1500 - 50 for VXLAN; for native routing use the physical MTU
```

```bash
ip link show cilium_host
```

### Missing route

With Cilium in `routingMode: native`, the node needs a route to the pod CIDR via the other nodes. Either:

- BGP (`bgpControlPlane.enabled: true`) and a BGP speaker on the router, or
- static routes on the router for each node's pod CIDR segment, or
- encapsulation (VXLAN), which does not need external routes.

The native-routing mode requires the network team to add routes. This is the single most common cause of cross-node pod failures in a native-routing deployment.

### kube-proxy replacement

```yaml
kubeProxyReplacement: strict
k8sServiceHost: <apiserver-vip>
k8sServicePort: 6443
```

`k8sServiceHost` and `k8sServicePort` are mandatory when kube-proxy is absent, otherwise the agent cannot reach the API server.

### A NetworkPolicy blocks the traffic

```bash
# Which policies apply to a pod
kubectl get networkpolicies -A -o json | \
  jq -r '.items[] | select(.spec.podSelector.matchLabels as $l | ...)'

# Cilium policy trace
cilium policy trace <src-pod> <dst-pod> --to-dst-port 443
```

`cilium policy trace` is the fastest way to see which policy allows or denies a flow.

### DNS

```bash
# From a pod
kubectl exec -it <pod> -- nslookup kubernetes.default.svc.cluster.local

# CoreDNS
kubectl -n kube-system get pods -l k8s-app=kube-dns
kubectl -n kube-system logs -l k8s-app=kube-dns --tail=50
```

If CoreDNS is healthy but resolution fails from one namespace, a NetworkPolicy is blocking the DNS egress (UDP 53 to the CoreDNS service). A default-deny egress policy needs an explicit DNS allowance.

## Risks

- Changing the Cilium MTU requires a pod restart on the node; the agent restarts and pods lose their network.
- Enabling strict kube-proxy replacement is not reversible at runtime without a node drain.
- Deleting a NetworkPolicy to "fix" connectivity removes a security control. Find the offending rule instead.

## Verification after remediation

```bash
cilium connectivity test
kubectl run nettest --rm -it --restart=Never --image=busybox:1.36 -- \
  wget -q -O- --timeout=5 http://kubernetes.default.svc
```

Then re-run acceptance test B-09 (network policy enforcement: the allowed flow succeeds and the denied flow still fails).
