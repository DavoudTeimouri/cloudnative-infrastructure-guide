# MetalLB

## A. Purpose and architecture

MetalLB provides a load-balancer implementation for `type: LoadBalancer` Services on bare metal, using either L2 (ARP) or BGP. Without it, a LoadBalancer Service stays `pending` forever outside a cloud environment.

```
  Service (type: LoadBalancer) -> MetalLB assigns an IP from the pool
      |
  speaker (DaemonSet) announces the IP:
     L2 mode: ARP replies on the LAN segment
     BGP mode: BGP peering with the router
```

## B. Requirements

- A dedicated IP range that is not used for anything else and is routable to the nodes.
- Layer 2 (same VLAN) for L2 mode, or BGP peering with the router for BGP mode.
- The nodes must be able to announce and receive the traffic.

## C. Offline preparation

- Helm chart: `harbor.internal/charts/metallb` (chart 0.16.1, app v0.16.1).
- Images: `metallb/controller` and `metallb/speaker`, both v0.16.1.

## D. Installation

```bash
helm repo add metallb https://metallb.github.io/metallb/charts
helm install metallb metallb/metallb \
  --namespace metallb-system --create-namespace \
  --version 0.16.1 \
  --set image.repository=harbor.internal/platform/metallb
```

L2 mode (simplest):

```yaml
apiVersion: metallb.io/v1beta1
kind: IPAddressPool
metadata:
  name: default-pool
  namespace: metallb-system
spec:
  addresses:
    - 10.61.0.10-10.61.0.30
---
apiVersion: metallb.io/v1beta1
kind: L2Advertisement
metadata:
  name: default-l2
  namespace: metallb-system
spec:
  ipAddressPools:
    - default-pool
```

BGP mode (needs router peering):

```yaml
apiVersion: metallb.io/v1beta1
kind: IPAddressPool
metadata:
  name: default-pool
  namespace: metallb-system
spec:
  addresses:
    - 10.61.0.10-10.61.0.30
---
apiVersion: metallb.io/v1beta1
kind: BGPAdvertisement
metadata:
  name: default-bgp
  namespace: metallb-system
spec:
  ipAddressPools:
    - default-pool
  peers:
    - 10.20.0.1          # the router's BGP peer address
```

```yaml
# Helm values for BGP
peers:
  - my-asn: 64500
    peer-asn: 64500
    peer-address: 10.20.0.1
    peer-port: 179
    my-router-id: 10.20.0.11
    password: "<from Vault>"
    password-secret:
      name: bgp-credentials
      key: password
```

BGP uses TCP port 179 and requires a router that peers with the node addresses. L2 mode needs no router change but requires the client and the VIP to be on the same VLAN.

## E. Integration

| Integration | Mechanism |
|---|---|
| LoadBalancer Services | The controller assigns an IP from the pool and programs the speaker |
| Ingress | The ingress controller requests a LoadBalancer Service, or the VIP is configured statically |
| ExternalDNS | Publishes an A record for the assigned IP |
| Cilium | Cilium's `loadBalancer.mode=hybrid` handles the traffic forwarding; MetalLB provides the address |

## F. Validation

```bash
# A LoadBalancer Service gets an address
kubectl -n default expose deployment nginx --port=80 --type=LoadBalancer
kubectl -n default get svc nginx
# NAME    TYPE           EXTERNAL-IP      PORT(S)
# nginx   LoadBalancer   10.61.0.10       80/TCP

# From a client on the same segment
curl http://10.61.0.10

# The speaker is announcing
kubectl -n metallb-system logs ds/speaker --tail=50
kubectl -n metallb-system get ippools,ipaddresspools,l2advertisements
```

Expected: the Service shows an `EXTERNAL-IP` from the pool and the client reaches it.

## G. Operations

| Task | Procedure |
|---|---|
| Add an IP to the pool | Edit the IPAddressPool; new Services can use it, existing assignments are unaffected |
| Remove an IP | Remove it from the pool only after checking no Service holds it: `kubectl get svc -A -o json` and look for the address |
| Move a Service's IP | Delete the Service and recreate it; MetalLB reassigns |
| Switch L2 to BGP | Apply the BGPAdvertisement, remove the L2Advertisement, and configure the router peer |
| Failover | L2 mode: the new leader answers the ARP requests after a short delay. BGP mode: the router converges on the withdraw and re-advertise |

## H. Known traps

1. **The VIP must be on a segment the clients can reach.** An IP from a different VLAN works only with BGP and a correct router configuration.
2. **L2 mode on a routed VLAN fails.** ARP requests do not cross a router. Use BGP or put the clients on the same segment.
3. **IPAddressPool changes do not move existing assignments.** A Service keeps its IP until it is deleted.
4. **A single-advertisement setup has a single point of failure.** The leader speaks for the whole pool. For HA, run BGP with multiple peers or accept the failover delay.
5. **The MetalLB service account needs `speaking` permissions.** The chart handles this; a custom RBAC override breaks it.

## I. Best practices

Mandatory:
- A dedicated, documented IP range, not carved out of the pod CIDR or the node subnet.
- A corresponding DNS record managed by ExternalDNS, so nothing depends on a hard-coded IP.
- The pool sized for the number of Services that need external addresses, plus headroom.

Strongly recommended:
- BGP where the network team can peer, because it survives a routed segment and gives a faster, cleaner failover.
- Static `loadBalancerIP` on the Services that must have a stable address (the ingress controller, Rancher, Argo CD, Keycloak).
- Monitor `metallb_ippool_assignments_total` and alert when the pool is nearly exhausted.
