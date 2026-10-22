# Troubleshooting runbooks

Format for every entry: symptoms -> likely causes -> diagnostic commands -> expected healthy state -> remediation -> risks -> verification.

## Index

| ID | Area | Runbook |
|---|---|---|
| T-01 | DNS | `troubleshooting/dns.md` |
| T-02 | NTP / time skew | `troubleshooting/time.md` |
| T-03 | Routing, MTU, firewall | `troubleshooting/network.md` |
| T-04 | TLS and certificates | `troubleshooting/tls.md` |
| T-05 | Registry and repository authentication | `troubleshooting/registry-auth.md` |
| T-06 | Offline dependency resolution | `troubleshooting/offline-deps.md` |
| T-07 | Linux package management | `troubleshooting/packages.md` |
| T-08 | Ansible execution | `troubleshooting/ansible.md` |
| T-09 | Kubespray | `troubleshooting/kubespray.md` |
| T-10 | etcd | `troubleshooting/etcd.md` |
| T-11 | Kubernetes API | `troubleshooting/apiserver.md` |
| T-12 | CNI and network policy | `troubleshooting/cni.md` |
| T-13 | CSI and persistent storage | `troubleshooting/csi.md` |
| T-14 | Ceph | `troubleshooting/ceph.md` |
| T-15 | Rancher | `troubleshooting/rancher.md` |
| T-16 | LDAP, AD, Keycloak | `troubleshooting/identity.md` |
| T-17 | Vault | `troubleshooting/vault.md` |
| T-18 | Secret delivery and rotation | `troubleshooting/secret-delivery.md` |
| T-19 | Prometheus targets | `troubleshooting/prometheus.md` |
| T-20 | Log ingestion | `troubleshooting/logging.md` |
| T-21 | GitLab CI/CD | `troubleshooting/gitlab-ci.md` |
| T-22 | Argo CD sync | `troubleshooting/argocd.md` |
| T-23 | Admission policy | `troubleshooting/admission.md` |
| T-24 | GPU driver and device allocation | `troubleshooting/gpu.md` |
| T-25 | LLM inference and GPU memory | `troubleshooting/inference.md` |
| T-26 | Service mesh | `troubleshooting/service-mesh.md` |
| T-27 | Upgrades | `troubleshooting/upgrades.md` |
| T-28 | Backup and recovery | `troubleshooting/backup-restore.md` |

## Universal first-response sequence

Run this before any component-specific procedure. It eliminates most misdiagnoses.

```bash
# 1. Is the problem in my session or in the system?
date; timedatectl            # skew?
dig +short <target>          # name resolution?

# 2. Is the target reachable at all?
ping -c 3 <target-ip>        # layer 3
nc -zv <target> <port>       # layer 4
curl -vk https://<target>    # layer 5/7

# 3. Is the service actually running?
systemctl status <unit> --no-pager
kubectl get pods -A | grep -v Running
kubectl get events -A --sort-by=.lastTimestamp | tail -30

# 4. Is it the cluster, or the workload?
kubectl get --raw='/readyz?verbose'
kubectl describe node <node>
```

## Universal rules

1. **Root cause before remediation.** Restarting a component hides the symptom and loses the evidence. Collect the evidence first.
2. **One change at a time.** Each change is a new hypothesis.
3. **Check the version matrix.** Most "impossible" failures are a version incompatibility.
4. **Check the network matrix.** Most "the service is down" reports are a firewall rule.
5. **Preserve the evidence.** Copy logs before restarting anything.
6. **Never run a destructive command without explicit authorization.**
7. **Record the resolution** in the relevant runbook, with the command that actually fixed it.

## Diagnostic commands by layer

| Layer | Command | Healthy state |
|---|---|---|
| Name resolution | `dig +short <name>` | The expected IP |
| Reverse | `dig -x <ip>` | The expected hostname |
| Time | `chronyc tracking` | Leap status normal, offset < 100 ms |
| Reachability | `ping -c3 <ip>` | 0% loss |
| Port | `nc -zv <ip> <port>` | Connection succeeded |
| TLS | `openssl s_client -connect <ip>:443 -servername <name>` | Verify return code 0, correct chain |
| Service | `systemctl is-active <unit>` | active |
| Container | `kubectl get pod -o wide` | Running, 0 restarts |
| Events | `kubectl describe pod` | No recent warnings |
| Logs | `kubectl logs <pod> --previous` | The previous container's output (for crash loops) |
| Cluster | `kubectl get --raw='/readyz?verbose'` | All checks ok |
| Storage | `kubectl get pvc` | Bound |
| Admission | `kubectl get validatingwebhookconfigurations` | Expected configs present |

## When to escalate

Escalate to a second engineer when:
- The evidence contradicts the runbook (the runbook is then wrong and must be corrected).
- A destructive action is required and the authorization is ambiguous.
- The failure spans two components and the boundary is unclear.
- The same symptom returns after a documented remediation.
