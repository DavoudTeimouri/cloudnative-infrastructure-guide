# Storage alternatives to Ceph

Ceph is the platform standard (ADR-0008). This file records the alternatives, when each one wins, and what it costs to adopt.

## Comparison

| Technology | Type | Scale ceiling | HA | S3 | Filesystem | Snapshot/clone | Operational cost | Offline footprint |
|---|---|---|---|---|---|---|---|---|
| Ceph (Rook) | Block + file + object | Very large | Yes | Yes | Yes | Yes | High | Large |
| Ceph (cephadm, external) | Block + file + object | Very large | Yes | Yes | Yes | Yes | Medium | Medium |
| Longhorn | Block (replicated) | Small-to-medium | Yes | No | No (limited) | Yes | Low-medium | Small |
| OpenEBS | Block / file (JSC, CSI) | Medium | Yes | No | Yes | Yes | Medium | Medium |
| NFS (managed) | Shared filesystem | Medium | Depends on the server | No | Yes | Server-side | Low | Small |
| Enterprise SAN | Block | Large | Yes | No | No | Yes | Low | Small (vendor) |
| MinIO | Object (S3) | Medium | Yes | Yes | No | Yes | Low | Small |
| GlusterFS | File | Medium | Yes | No | Yes | Yes | Medium | Medium |
| Local-path provisioner | Block (node-local) | None | No | No | No | No | None | Tiny |

## When each wins

### Longhorn

Adopt when:
- The site is small (under ~10 TB, tens of nodes).
- Storage must live entirely inside the cluster with no external dependency.
- The team wants a simple operator and accepts that it is not Ceph.

Do not adopt when: object storage is required, the estate is large, or multi-cluster shared capacity is needed. Longhorn is a block-storage product; it is not a Ceph replacement.

Trade-offs: it replicates volumes across nodes with its own data engine, which is easy to operate but has a real per-node overhead and does not provide a filesystem or object API.

### OpenEBS

Adopt when a CSI-based dynamic provisioner is needed and the site already runs a storage operator with an external engine (for example, a JSC setup on separate storage nodes).

Do not adopt when the goal is simplicity. OpenEBS has several storage engines and its project status has been a factor in the past; confirm the current maintenance status before adopting.

### NFS

Adopt for shared-file workloads where the workload is not latency-sensitive and the data is not the system of record. NFS over Kubernetes with the CSI driver is simple and works.

Do not adopt for databases, or as the primary substrate for a storage platform. NFS has no replication story of its own; the HA comes from the server.

### Enterprise SAN

Adopt when the site already owns a SAN and the budget supports it. It gives the best latency, the best support path, and hardware-level reliability features. The trade-off is cost, vendor lock-in, and an operational model that is outside the Kubernetes team.

Use it for the database tier, keep Ceph for the general-purpose tier where the software-defined model is an advantage.

### MinIO

Adopt when S3-compatible object storage is needed and Ceph's RGW is not justified. MinIO is far lighter than RGW and simpler to run.

Do not adopt when the platform already standardizes on Ceph RGW — two object stores double the data-management surface and the backup work.

### GlusterFS

Adopt only for existing estates with an established Gluster practice. For a new build, it is a poor trade against Ceph given Ceph's wider adoption, better ecosystem integration, and better support path.

### local-path provisioner

Adopt only for non-persistent, node-local, disposable data — caches, scratch space, and log spools. It is the Kubespray default and must be replaced by a real StorageClass before any stateful workload lands on it.

## The decision this platform actually made

| Requirement | Driver |
|---|---|
| Block, file, and object from one platform | Ceph |
| Shared capacity across multiple clusters | Ceph via cephadm plus the external CSI driver |
| Storage-native to Kubernetes for cluster-local volumes | Ceph via Rook |
| Hardware acceleration for databases, where a SAN exists | SAN, if available |

## Storage comparison against Rook-Ceph and external Ceph

| Aspect | Rook-Ceph | External Ceph (cephadm) | Longhorn | OpenEBS | SAN |
|---|---|---|---|---|---|
| Deployment | Operator inside K8s | cephadm on dedicated hosts | Operator inside K8s | Operator + engine | External appliance |
| Cluster coupling | Yes | No | Yes | Yes | No |
| Object storage | RGW | RGW | No | No | No |
| Multi-cluster consumption | No | Yes | No | Limited | Yes |
| Upgrade complexity | Two layers (Rook then Ceph) | One (ceph orch) | One | Medium | Low |
| Failure blast radius | A cluster network fault can affect storage | Storage hosts are independent | Node-local | Depends | Independent |
| Offline artifact volume | High | Medium | Low | Medium | Low |

## Consequences of the Ceph-only decision

Accepted:
- Ceph is a large operational surface for a small team. Mitigation: the cephadm path keeps the lifecycle in the vendor's hands.
- A cluster-wide CNI or network fault can take Rook-managed storage with it. Mitigation: the external Ceph path for anything shared or critical.
- Ceph is the heaviest component in the artifact matrix. Mitigation: the staging-and-import workflow in `offline-artifacts/offline-artifact-architecture.md`.

Not accepted:
- Using Rook for storage that must survive the loss of the cluster it runs in.
- Mixing two object stores.
- Introducing a second block platform for a single application without a documented reason.
