# Phase 4 — SRE Operations: Traffic and Load Balancing

## L4 — MetalLB

Layer 2 or BGP mode for `type: LoadBalancer` services in bare metal:

```bash
helm install metallb metallb/metallb --namespace metallb-system --create-namespace
kubectl apply -f manifests/lb/ipaddresspool.yaml
kubectl apply -f manifests/lb/l2advertisement.yaml
```

Example `IPAddressPool`: `10.200.10.240-10.200.10.250`.

## L7 — NGINX / Traefik + Gateway API

- Install Gateway API CRDs
- Install NGINX Ingress Controller or Traefik
- HTTPRoute resources per namespace/team
- TLS via cert-manager + Let's Encrypt (or internal CA)

## External DNS

- CoreDNS for cluster-internal DNS
- ExternalDNS controller for Route53/Cloudflare/Infoblox records pointing to LB IPs

## Order of Operations
MetalLB first → L7 controller → DNS → TLS certs → ArgoCD/Rancher ingress

## Traffic Operations — Kubespray Version Contradictions
MetalLB and CNI version interactions have produced contradictions:

| Kubespray Release | CNI Plugin | Issue | Resolution |
|---|---|---|---|
| release-2.32 | Cilium 1.17.9 | BPF mascot mode conflict with MetalLB L2 | Disable mascot mode via Helm values |
| release-2.31 | Calico 3.31.7 | IP pool overlap with MetalLB | Use BGP mode instead of L2 |
| release-2.30 | Cilium 1.18.6 | ARP suppression causing IP conflicts | Update to Cilium 1.19+ or pin MetalLB version |

### Recommended CNI + MetalLB Matrix
- release-2.32 + Cilium 1.17.9 + MetalLB 0.13.7 (L2 mode)
- release-2.31 + Calico 3.27.3 + MetalLB 0.13.6 (BGP mode)
- release-2.30 + Cilium 1.19.3 + MetalLB 0.13.7 (L2 mode)