# Kubernetes Manifests

## Directory Structure
```
manifests/
├── base/
│   ├── namespaces.yaml
│   ├── storage-classes.yaml
│   ├── network-policies.yaml
│   └── resource-quotas.yaml
├── applications/
│   ├── ingress-nginx/
│   ├── cert-manager/
│   ├── velero/
│   └── monitoring/
├── overlays/
│   ├── dev/
│   ├── staging/
│   └── prod/
└── kustomization.yaml
```

## Example: Storage Classes (manifests/base/storage-classes.yaml)

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: ceph-rbd
  annotations:
    storageclass.kubernetes.io/is-default-class: "true"
provisioner: rbd.csi.ceph.com
parameters:
  clusterID: "<ceph-fsid>"
  pool: k8s-rbd
  imageFormat: "2"
  imageFeatures: layering
  csi.storage.k8s.io/provisioner-secret-name: csi-rbd-secret
  csi.storage.k8s.io/provisioner-secret-namespace: ceph-csi-rbd
reclaimPolicy: Delete
allowVolumeExpansion: true
volumeBindingMode: Immediate
---
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: ceph-cephfs
provisioner: cephfs.csi.ceph.com
parameters:
  clusterID: "<ceph-fsid>"
  fsName: k8s-cephfs
  pool: k8s-cephfs-data
reclaimPolicy: Delete
allowVolumeExpansion: true
volumeBindingMode: Immediate
```

## Example: Network Policies (manifests/base/network-policies.yaml)

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all
  namespace: default
spec:
  podSelector: {}
  policyTypes:
    - Ingress
    - Egress
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-dns
  namespace: default
spec:
  podSelector: {}
  policyTypes:
    - Egress
  egress:
    - to:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: kube-system
      ports:
        - protocol: UDP
          port: 53
```

## Usage with Kustomize

```bash
# Apply base
kubectl apply -k manifests/base/

# Apply specific application
kubectl apply -k manifests/applications/ingress-nginx/

# Apply with overlay (prod)
kubectl apply -k manifests/overlays/prod/
```