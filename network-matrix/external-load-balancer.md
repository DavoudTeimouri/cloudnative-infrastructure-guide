# External load balancer — active/active edge

[Previous step](../management-cluster/rancher/rancher.md) | [Next step](../management-cluster/platform-services/)

---

## A. Purpose and architecture

The external load balancer is the platform's edge: it terminates client TLS, applies the site edge policy, and forwards to the Kubernetes management endpoints (API server, Rancher, Argo CD, Keycloak, Grafana) and to the L7 ingress tier.

The user requirement is **active/active on Linux, built from Nginx or HAProxy, with Keepalived and Docker Compose**.

### The honest constraint

Keepalived implements VRRP. VRRP elects **one master** for a given virtual router id and one virtual IP address. A single VIP under VRRP is therefore **active/standby, not active/active**. This is a property of the protocol, not of the implementation.

Active/active is obtained by **not** putting all traffic behind one VRRP-owned address. The design has three tiers, and the platform implements tier 2 and tier 3 on top of the same node-local dataplane.

```
                        +----------------------+
   client ------------->| DNS / GSLB          |   tier 3: two A records or
                        +----------+-----------+
                                   |
                    +--------------+--------------+
                    |                             |
            VIP-A (10.60.0.10)            VIP-B (10.60.0.11)
                    |                             |
            +-------+-------+             +-------+-------+
            |  lb-node-1   |             |  lb-node-2   |   tier 2: router ECMP
            | nginx/haproxy|             | nginx/haproxy|          or BGP over
            | + keepalived |             | + keepalived |          the two VIPs
            +-------+-------+             +-------+-------+
                    |                             |
                    +--------------+--------------+
                                   |
                    kube-apiserver VIP, ingress, platform services
```

| Tier | Mechanism | Active/active? | Requires | Failover time |
|---|---|---|---|---|
| 1 | One VIP, Keepalived VRRP | No — active/standby | Nothing beyond the L2 segment | ~3 s (VRRP advert interval) |
| 2 | Two VIPs, upstream ECMP or BGP | **Yes** | Router support for ECMP over the two VIPs, or BGP peering | Router convergence, or instant with `SO_REUSEPORT`-style multipath |
| 3 | DNS/GSLB over the two VIPs | **Yes** | Authoritative DNS with health checks | DNS TTL bound |

Tier 2 is the primary design. Tier 3 is for client-facing names that the router cannot balance, and it also gives a coarse client-side failover for tier-1-style single-VIP endpoints.

### Node-local dataplane

Each node runs the same stack, containerised with Docker Compose:

- **Nginx or HAProxy** in front, bound to `0.0.0.0:443` and `0.0.0.0:80` on the **host network**, with `net.ipv4.ip_nonlocal_bind=1` so the process holds the socket whether or not the VIP currently sits on that node.
- **Keepalived** in the same Compose project, on host network, managing the node's VIP.
- Because the dataplane binds the wildcard address rather than the VIP, the dataplane is **up and serving on both nodes at all times**. Keepalived only decides which node the address points at. That is what makes tier 2 and tier 3 possible and what keeps a failover from requiring a container restart.

### Nginx versus HAProxy

| Aspect | Nginx | HAProxy |
|---|---|---|
| L7 features | Rich: rewrite, map, auth_request, Lua, caching | Simpler but excellent at proxying, health checking, and TLS |
| Layer 4 passthrough | `stream` module, separate binary block | Native, first-class |
| Health checks | Passive plus `nginx -t` style upstream checks; active checks need Plus or NGINX Inc. | Active health checks in OSS, per-server, with `check` |
| Stats | `stub_status` or a third-party exporter | Built-in `stats` socket and a stats page |
| Graceful reload | `nginx -s reload`, zero downtime | `USR2`/`SIGUSR1` soft stop, or the official reload procedure |
| Connection sharding | `reuseport` on `listen` (Linux 3.9+) | `SO_REUSEPORT` by default on listen sockets |
| Memory footprint | Low | Low |
| Ecosystem | Broad | Broad |

Decision: **HAProxy for the edge** when active health checks and L4 passthrough matter (the edge must health-check the API server and the ingress tier, and it must pass TCP through for the API). **Nginx for the edge** when rich L7 policy (redirects, auth_request, header manipulation) matters more than active health checks.

The Compose project below ships both, selected by an environment variable. Nginx runs the L7 policy; HAProxy runs the L4 and the active health checking. The recommended production profile is **HAProxy in front, Nginx behind it** only if both are needed; running both for the same traffic doubles the failure surface and is not recommended.

## B. Requirements and compatibility

| Item | Requirement | Status |
|---|---|---|
| OS | Oracle Linux 9 or Ubuntu Server 24.04 LTS | VERIFIED |
| Docker Engine | 26.x or later, with the Compose v2 plugin | VERIFIED against the platform's container baseline |
| Docker Compose | v5.6.1 (plugin) | VERIFIED, `https://github.com/docker/compose/releases` |
| Nginx (OSS) | 1.31.8 upstream, 1.24.0 in Ubuntu noble | VERIFIED, `https://github.com/nginx/nginx/releases` and the Ubuntu package index |
| HAProxy | 3.2.26 (3.2 branch), 2.8.5 in Ubuntu noble | VERIFIED, `https://www.haproxy.org/download/3.2/src/` and the Ubuntu package index |
| Keepalived | 2.4.3 upstream, 2.2.8 in Ubuntu noble | VERIFIED, `https://github.com/acassen/keepalived/releases` and the Ubuntu package index |
| Kernel | >= 4.19 (SO_REUSEPORT needs 3.9+; 5.x recommended) | VERIFIED against the Kubespray kernel requirements |
| VRRP | IP protocol 112. Multicast 224.0.0.18, or unicast peers | VERIFIED, `https://www.keepalived.org/documentation/keepalived-conf/` |

### VRRP multicast caveat

VRRP uses multicast on `224.0.0.18` by default. Many switched networks filter it, and the protocol will not work. Two options:

- **Unicast peers**: keepalived `unicast_src_ip` and `unicast_peer { }` per node. Works on any L2 segment. Preferred for this platform, because the DMZ segment is likely to have multicast filtering.
- **Multicast**: only if the network team confirms `224.0.0.18` is permitted end to end on the DMZ VLAN.

The HAProxy Enterprise documentation makes the same point: "some environments, such as AWS, may not allow multicasting. In these environments, you may have to configure a unicast implementation instead".

## C. Offline preparation

| Artifact | Type | Internal destination | Notes |
|---|---|---|---|
| `nginx:1.31.8` | OCI | `harbor.internal/edge/nginx` | Plus `nginx:1.31.8-alpine` if Alpine is chosen |
| `haproxy:3.2.26` | OCI | `harbor.internal/edge/haproxy` | |
| `acassen/keepalived:v2.4.3` | OCI | `harbor.internal/edge/keepalived` | The upstream image; it needs `NET_ADMIN` and host network |
| `docker/compose` | OCI (tooling) | `harbor.internal/tools/compose` | For the CI runner, not the LB nodes |
| Edge configuration | Git | `gitlab.internal/platform/edge` | Nginx, HAProxy, keepalived configs and the Compose file |
| TLS certificates | Secret | Vault, via cert-manager or a mounted file | The edge terminates TLS |

The Compose file and the configuration live in Git. The nodes are stateless: a node is rebuilt by `docker compose up -d` from the committed configuration. Certificates are mounted read-only from a path that Ansible populates from Vault.

## D. Installation

### Host preparation

```bash
# The edge needs the wildcard bind, because the dataplane is always up
# regardless of which node currently holds the VIP
cat > /etc/sysctl.d/99-edge.conf <<'EOF'
net.ipv4.ip_nonlocal_bind = 1
net.ipv4.conf.all.rp_filter = 0
net.ipv4.conf.default.rp_filter = 0
EOF
sysctl --system
```

`rp_filter=0` matters when the dataplane binds the wildcard address and the traffic arrives addressed to the VIP.

### Docker Compose stack

`manifests/external-lb/docker-compose.yml` — the full file is in the repository. Structure:

```yaml
name: edge

services:
  haproxy:
    image: harbor.internal/edge/haproxy:3.2.26
    container_name: edge-haproxy
    network_mode: host
    restart: unless-stopped
    volumes:
      - ./haproxy.cfg:/usr/local/etc/haproxy/haproxy.cfg:ro
      - ./certs:/etc/haproxy/certs:ro
    healthcheck:
      test: ["CMD", "haproxy", "-c", "-f", "/usr/local/etc/haproxy/haproxy.cfg"]
      interval: 30s
      timeout: 5s
      retries: 3
    sysctls:
      net.ipv4.ip_nonlocal_bind: "1"

  nginx:
    image: harbor.internal/edge/nginx:1.31.8
    container_name: edge-nginx
    network_mode: host
    restart: unless-stopped
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./certs:/etc/nginx/certs:ro
    healthcheck:
      test: ["CMD", "nginx", "-t"]
      interval: 30s
      timeout: 5s
      retries: 3
    sysctls:
      net.ipv4.ip_nonlocal_bind: "1"

  keepalived:
    image: harbor.internal/edge/keepalived:v2.4.3
    container_name: edge-keepalived
    network_mode: host
    restart: unless-stopped
    cap_add:
      - NET_ADMIN
      - NET_BROADCAST
      - NET_RAW
      - SYS_MODULE
    volumes:
      - ./keepalived.conf:/etc/keepalived/keepalived.conf:ro
      - ./keepalived.d:/etc/keepalived/keepalived.d:ro
    pid: host
    sysctls:
      net.ipv4.ip_nonlocal_bind: "1"
```

Why `network_mode: host` on all three:

- VRRP advertisements are sent from the physical interface, with the physical source address. A bridged container cannot emit them correctly.
- The dataplane binds `0.0.0.0:443` and must hold the socket across a VIP move. In a bridged network, the socket would be bound inside the container's namespace and would not follow the host's address changes.
- `pid: host` on keepalived is required for it to manage the host's network namespace state correctly in practice.

### HAProxy configuration

`manifests/external-lb/haproxy.cfg` — the edge frontend, with an active health check against each upstream:

```
global
    log stdout format raw local0
    maxconn 20000
    tune.ssl.default-dh-param 2048
    stats socket /run/haproxy/admin.sock mode 660 level admin
    ssl-default-bind-ciphersuites ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305

defaults
    log global
    mode http
    option httplog
    option dontlognull
    timeout connect 5s
    timeout client 60s
    timeout server 60s
    timeout http-request 10s
    timeout http-keep-alive 10s
    retries 3

frontend fe_https
    bind 0.0.0.0:443
    mode tcp
    # L4 to the L7 tier; the edge does not terminate TLS when Nginx owns it
    default_backend be_l7

backend be_l7
    mode tcp
    balance leastconn
    option tcp-check
    server nginx_local 127.0.0.1:8443 check inter 3s fall 3 rise 2
```

The `frontend` in `mode tcp` is deliberate: the edge is a TCP proxy in front of the L7 policy tier. When Nginx owns TLS termination directly, the edge HAProxy is not deployed at all — the Compose profile `edge-nginx-only` starts Nginx and keepalived only.

For a pure L4 edge (for example, the Kubernetes API server endpoint), the backend is the API VIP with an HTTP health check on `/readyz`:

```
frontend fe_api
    bind 0.0.0.0:6443
    mode tcp
    default_backend be_api

backend be_api
    mode tcp
    balance roundrobin
    option httpchk GET /readyz
    http-check expect status 200
    server kube-apiserver 10.20.0.100:6443 check inter 3s fall 3 rise 2
```

### Nginx configuration

`manifests/external-lb/nginx.conf` — TLS termination, HTTP redirect, and the platform endpoints:

```nginx
worker_processes auto;
error_log /dev/stderr warn;
pid /var/run/nginx.pid;

events {
    worker_connections 8192;
    multi_accept on;
}

http {
    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;
    access_log    /dev/stdout;

    sendfile      on;
    tcp_nopush    on;
    keepalive_timeout 65;
    server_tokens off;

    # SO_REUSEPORT: one listening socket per worker, kernel distributes
    # new connections. Linux 3.9+. Per-host process sharding, not cross-host.
    # listen directives below use it.

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 1d;
    ssl_session_tickets off;

    upstream api_server {
        server 10.20.0.100:6443 max_fails=2 fail_timeout=5s;
        keepalive 32;
    }

    upstream ingress_https {
        server 10.61.0.10:443 max_fails=2 fail_timeout=5s;
        keepalive 32;
    }

    server {
        listen 80 reuseport;
        server_name _;
        return 301 https://$host$request_uri;
    }

    server {
        listen 443 ssl reuseport;
        http2 on;
        server_name _;

        ssl_certificate     /etc/nginx/certs/tls.crt;
        ssl_certificate_key /etc/nginx/certs/tls.key;

        location / {
            proxy_pass http://ingress_https;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
    }
}
```

`reuseport` gives per-host connection sharding across workers. It does **not** load-balance across nodes. Cross-node distribution is tier 2 (router ECMP/BGP) or tier 3 (DNS/GSLB).

### Keepalived configuration

`manifests/external-lb/keepalived.conf` — unicast peers, because the DMZ VLAN is assumed to filter multicast:

```
global_defs {
    router_id lb-node-1
    enable_script_security
    script_user root
    vrrp_skip_check_adv_addr
}

vrrp_script chk_haproxy {
    script "/etc/keepalived/keepalived.d/check_haproxy.sh"
    interval 2
    weight -20
    fall 2
    rise 2
}

vrrp_instance VI_EDGE {
    state BACKUP
    interface bond0
    virtual_router_id 51
    priority 100
    advert_int 1

    authentication {
        auth_type PASS
        auth_pass <from Vault>
    }

    unicast_src_ip 10.60.0.1
    unicast_peer {
        10.60.0.2
    }

    virtual_ipaddress {
        10.60.0.10/24
    }

    track_script {
        chk_haproxy
    }

    notify_master "/etc/keepalived/keepalived.d/notify.sh MASTER"
    notify_backup "/etc/keepalived/keepalived.d/notify.sh BACKUP"
}
```

The health-check script is what keeps a node from taking the VIP when its dataplane is broken:

```bash
#!/bin/sh
# Returns 0 when the local dataplane is serving.
exec 3<>/dev/tcp/127.0.0.1/8443
```

A failed check subtracts the weight, and the node with the higher effective priority holds the address. The notification script posts the state change to the monitoring stack, so the topology in Grafana reflects which node is master.

## E. Integration

| Dimension | Mechanism |
|---|---|
| Identity | The edge proxies to the platform services; the end user's identity is handled by Keycloak behind the ingress, not at the edge |
| TLS | The edge holds the wildcard certificate, mounted read-only from a path Ansible populates from Vault. cert-manager issues it if the edge runs in-cluster; for a standalone edge, the certificate is written by Ansible from a Vault lookup |
| Secrets | The `auth_pass` for VRRP and the TLS key are written by Ansible from Vault at deploy time. Neither is in Git |
| Network | The edge is on the DMZ segment, with only the platform VIPs reachable from it. It initiates the connections, so no return route is needed for the client traffic |
| Storage | None. The edge is stateless |
| Monitoring | HAProxy `stats` socket scraped over a unix socket or a local HTTP listener; Nginx `stub_status`; keepalived state from the notification script |
| Logging | Container stdout, collected by the node's Fluent Bit agent |
| Security | The edge is the only host exposed to the untrusted segment. It runs a minimal image set, no shell access, and the host firewall allows only 80/443 inbound |
| Automation | The whole node is rebuilt by Ansible: sysctls, Docker, the Compose project, the configuration from Git, the certificates from Vault |
| GitOps | The configuration and the Compose file live in Git. The nodes are rebuilt from the committed state, so the edge is reconciled by GitOps at the node level, not by Argo CD |

## F. Validation

```bash
# The dataplane is up on both nodes, VIP or not
curl -sk --resolve edge.internal:443:10.60.0.1 https://edge.internal/healthz
curl -sk --resolve edge.internal:443:10.60.0.2 https://edge.internal/healthz

# The VIP is where keepalived says it is
ip -br addr show bond0 | grep 10.60.0.10
journalctl -u keepalived -n 50        # or: docker logs edge-keepalived

# HAProxy config is valid and the stats page is up
docker exec edge-haproxy haproxy -c -f /usr/local/etc/haproxy/haproxy.cfg
curl -s http://127.0.0.1:8404/ | head -20

# Nginx config is valid
docker exec edge-nginx nginx -t

# Failover drill (tier 1)
docker stop edge-keepalived        # on the master
# VIP moves to the peer within the VRRP advert interval
```

Expected: both nodes answer on their own address; exactly one holds the VIP at a time in tier 1; in tier 2 both hold their own VIP and the router balances between them.

## G. Operations

| Task | Procedure |
|---|---|
| Change the edge configuration | Update the committed configuration, then `docker compose up -d` on both nodes, then verify the health checks |
| Reload HAProxy without dropping connections | `docker kill -s USR2 edge-haproxy` (soft stop), then `docker kill -s USR1 edge-haproxy` (finish) |
| Reload Nginx | `docker exec edge-nginx nginx -s reload` |
| Force a failover | `systemctl stop keepalived` on the master, or lower its priority in the committed config and reload |
| Rotate the TLS certificate | Write the new certificate from Vault via Ansible, then reload the dataplane. With `haproxy` in `mode tcp` the certificate lives in Nginx, so reload Nginx |
| Add an upstream | Edit the committed upstream block, reload, confirm the health checks show it as up |
| Upgrade a component | New image tag in the committed Compose file, `docker compose pull`, `docker compose up -d`, verify, then the peer node |
| Rebuild a node | Ansible rebuild: sysctls, Docker, configuration, certificates, `docker compose up -d` |

### Failover behaviour

| Tier | Failover time | What the client sees |
|---|---|---|
| 1 (VRRP VIP) | ~3 s (advert interval 1 s, 3 adverts) | Connection reset for in-flight connections, new connections succeed after the address moves |
| 2 (ECMP/BGP) | Router convergence, or sub-second with ECMP | Same as tier 1 for the address in flight, but the router continues to use the surviving node |
| 3 (DNS/GSLB) | TTL bound, typically 30-60 s | Name resolution returns both addresses; the client may use a dead one until the TTL expires |

Mitigation for in-flight resets: the edge dataplane should use a long drain window on shutdown (`docker stop -t 30`), so existing connections finish before the process exits.

## H. Best practices

Mandatory:
- Host network for the dataplane and for keepalived. VRRP cannot work from a bridged container.
- `net.ipv4.ip_nonlocal_bind=1` on the host, so the dataplane holds its socket across a VIP move.
- The dataplane binds the wildcard address, never the VIP, so it is always serving.
- Unicast VRRP peers, not multicast, unless the network team confirms multicast on the DMZ VLAN.
- The VRRP `auth_pass` and the TLS key come from Vault, written by Ansible, never from Git.
- A health check on the dataplane, tracked by keepalived, so a broken node never takes the address.
- The edge runs a minimal image set and is the only host exposed to the untrusted segment.

Strongly recommended:
- Tier 2 for the production edge: two VIPs with router ECMP or BGP, so both nodes carry traffic and losing one halves the capacity rather than removing it.
- Tier 3 (DNS with health checks) for client-facing names the router cannot balance, with a short TTL.
- HAProxy for the L4 edge and the active health checks; Nginx for the L7 policy, and not both on the same traffic path.
- `reuseport` on the Nginx listeners for per-host worker sharding at high connection rates.
- A quarterly failover drill on both tiers, with the measured failover time recorded.


[Previous step](../management-cluster/rancher/rancher.md) | [Next step](../management-cluster/platform-services/)
