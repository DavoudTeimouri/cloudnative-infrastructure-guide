# 08. Traffic edge

**Purpose:** Provide client-facing entry to the platform — external load balancer, VIPs via
Keepalived, HAProxy/Nginx, and Kubernetes Ingress (Cilium or Nginx ingress controller).

## Prerequisites
- Step 07 complete: application clusters running.
- Step 05 complete: MetalLB configured (fallback pool).

## Steps

### 08.1 External load balancer + VIP
Deploy two edge nodes (HAProxy + Nginx) with Keepalived for VIP failover. VIPs live in the `dmz`
segment; backend targets are the MetalLB pool / node IPs of your clusters.

Source: `network-matrix/external-load-balancer.md`

### 08.2 Ingress controller
Install an ingress controller (Nginx or Cilium) in each cluster. Route hostnames (`*.apps.internal`,
`*.platform.internal`) to cluster services via Ingress resources.

Source: `kubernetes/ingress/multi-controller-plan.md`

### 08.3 Firewall rules
Generate and apply rules from `network-matrix/firewall-rules-generation.md`. Allow only:
- Client → VIP 80/443
- VIP → edge backends (health checks)
- Edge → MetalLB pool / node ports
- Intra-cluster CNI traffic per port matrix

Source: `network-matrix/port-requirements.md`

## Validation
- [ ] VIP fails over between the two edge nodes (keepalived state MASTER/BACKUP).
- [ ] `curl` through the VIP reaches a sample service in each cluster.
- [ ] Ingress hostname resolves and terminates TLS.
- [ ] Firewall drops all traffic not explicitly allowed (default deny).
- [ ] MetalLB `LoadBalancer` Services get external IPs from the pool.

## Navigation
**[← Prev · 07. Application cluster](./07-application-cluster.md)** | **[Next → 09. Platform services](./09-platform-services.md)**
