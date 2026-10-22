# Cilium CNI

## A. Purpose and architecture

Cilium provides pod networking, network policy, service load balancing, and observability, using eBPF in the kernel instead of iptables.

```
  pod A (node 1)  --eBPF-->  node 1 host stack  --underlay-->  node 2 host stack --eBPF--> pod B
        |                                                                |
     Cilium agent (DaemonSet, one per node)                     Cilium agent
        |                                                                |
   CiliumEnvoy (L7 proxy, per node)                            Hubble relay + UI
```

Modes used here:
- **Routing mode**: native (no encapsulation) when the network can route the pod CIDR; tunnel (VXLAN) otherwise.
- **kube-proxy replacement**: `kubeProxyReplacement: strict`, so iptables is not used for service handling.

## B. Requirements

| Item | Requirement |
|---|---|
| Kernel | >= 4.19 (5.4+ recommended); the pinned release requires 4.19+ |
| cgroups | v1 or v2; v2 recommended |
| Mounts | bpffs, debugfs; Cilium mounts them if the host allows |
| Privileges | The agent needs `NET_ADMIN`, `SYS_MODULE` (for certain features), and host mounts |
| BTF | Optional; required for some eBPF features |

Cilium's eBPF datapath narrows the kernel compatibility envelope compared to Calico. Confirm the node kernel against the Cilium release's requirements before deploying.

## C. Offline preparation

- Helm chart: `harbor.internal/charts/cilium` (chart 1.20.3, app 1.20.3).
- Images: `cilium/cilium`, `cilium/operator-generic`, `cilium/hubble-relay`, `cilium/hubble-ui`, `cilium/certgen`, `cilium/envoy`, and the `quay.io/cilium/*` variants of the same.
- The Cilium chart tarball and `index.yaml` must also be in the internal file mirror, because the Kubespray offline guide specifically requires `helm.cilium.io/index.yaml` and the chart tarball.

## D. Installation

Through Kubespray, the release sets `kube_network_plugin: cilium` and installs the chart itself. The offline override is in `group_vars/all/offline.yml` (see `kubespray/group-vars-template.md`).

Standalone installation (used when the cluster is not built by Kubespray):

```bash
helm install cilium cilium/cilium \
  --version 1.20.3 \
  --namespace kube-system \
  --set kubeProxyReplacement=strict \
  --set k8sServiceHost=10.20.0.100 \
  --set k8sServicePort=6443 \
  --set ipam.mode=kubernetes \
  --set ipv4.enabled=true \
  --set ipv6.enabled=false \
  --set tunnel=disabled \
  --set bpf.masquerade=true \
  --set hubble.relay.enabled=true \
  --set hubble.ui.enabled=true \
  --set image.repository=harbor.internal/platform/cilium \
  --set operator.image.repository=harbor.internal/platform/cilium \
  --set operator.image.useDigest=false \
  --set hubble.relay.image.repository=harbor.internal/platform/cilium \
  --set hubble.ui.backend.image.repository=harbor.internal/platform/cilium \
  --set hubble.ui.frontend.image.repository=harbor.internal/platform/cilium \
  --set envoy.image.repository=harbor.internal/platform/cilium \
  --set certgen.image.repository=harbor.internal/platform/cilium \
  --set image.useDigest=false
```

`tunnel=disabled` is native routing. Use `tunnel: vxlan` if the network cannot route the pod CIDR.

## E. Network policy

```yaml
apiVersion: cilium.io/v2
kind: CiliumNetworkPolicy
metadata:
  name: allow-dns
  namespace: payments
spec:
  endpointSelector:
    matchLabels:
      app: payments-api
  egress:
    - toEndpoints:
        - matchLabels:
            "k8s:io.kubernetes.pod.namespace": kube-system
            "k8s:app.kubernetes.io/name": kube-dns
      toPorts:
        - ports:
            - port: "53"
              protocol: UDP
            - port: "53"
              protocol: TCP
```

L7 policy (requires CiliumEnvoy):

```yaml
apiVersion: cilium.io/v2
kind: CiliumNetworkPolicy
metadata:
  name: allow-api-only
  namespace: payments
spec:
  endpointSelector:
    matchLabels:
      app: payments-api
  ingress:
    - fromEndpoints:
        - matchLabels:
            app: web
      toPorts:
        - ports:
            - port: "443"
              protocol: TCP
```

## F. Observability

```bash
cilium status --verbose
cilium connectivity test
cilium bpf lb list
cilium bpf endpoint list

# Hubble
cilium hubble list
cilium hubble observe --namespace payments
```

The Hubble UI is exposed through an Ingress or a LoadBalancer Service.

## G. Validation

```bash
kubectl -n kube-system get pods -l k8s-app=cilium
cilium status
# expect: KubeProxyReplacement: True, KubeProxyReplacementError: none

# Connectivity
cilium connectivity test
# expect: all probes pass

# Cross-node pod traffic
kubectl run a --rm -it --restart=Never --image=busybox:1.36 -- sleep 300 &
kubectl run b --rm -it --restart=Never --image=busybox:1.36 -- ping -c3 <a-pod-ip>

# Policy enforcement
# an allowed flow succeeds, a denied flow fails
```

## H. Operations

| Task | Procedure |
|---|---|
| Upgrade | Helm upgrade through Argo CD; a canary node pool first. The agent restarts, which briefly interrupts pod connectivity on that node |
| Add a node | Label and taint per the platform standard; Cilium's agent DaemonSet schedules onto it automatically |
| Replace a node | Drain, rebuild, uncordon. The new agent rebuilds its state from the operator |
| Change the MTU | `mtu` in the Helm values; the agent restarts and pods on that node lose connectivity briefly |
| Debug a flow | `cilium policy trace <src> <dst>` and `cilium hubble observe` |
| Recover from a stuck agent | `kubectl -n kube-system delete pod -l k8s-app=cilium` on that node |

## I. Known traps

1. **kube-proxy replacement requires the API endpoint.** Without `k8sServiceHost` and `k8sServicePort`, the agent cannot reach the API server and never becomes ready.
2. **Native routing requires external routes.** The router or switch must have a route for the pod CIDR pointing at the node addresses. Without it, cross-node pod traffic fails while same-node traffic works.
3. **A default-deny egress policy breaks DNS.** Always allow DNS to kube-dns before enabling a deny policy.
4. **MTU mismatch.** With VXLAN, the pod MTU is the physical MTU minus 50. With native routing, it equals the physical MTU.
5. **Hubble relay and UI are optional but have their own images.** In an offline environment, a missing UI image leaves the relay pod in `ImagePullBackOff` even when the datapath is fine.
6. **The operator must be able to write the Cilium CRDs and to reach the API server.** A broken operator means the agent never reconciles.

## J. Best practices

Mandatory:
- `kubeProxyReplacement: strict` with the API endpoint set.
- Explicit `ipam.mode=kubernetes` and a documented pod CIDR.
- The Hubble relay and UI images mirrored, or the features disabled entirely.
- A network policy per namespace, deployed in audit mode first.

Strongly recommended:
- Native routing where the network team can add the pod CIDR route; it removes the encapsulation overhead and the MTU problem.
- `bpf.masquerade=true` for better masquerade performance.
- A dedicated CiliumNetworkPolicy per application namespace, owned by the application team in their own GitOps repository.
- Hubble metrics exported to Prometheus for flow-level observability.
