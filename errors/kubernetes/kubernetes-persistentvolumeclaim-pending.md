---
title: "Kubernetes PersistentVolumeClaim Pending"
slug: kubernetes-persistentvolumeclaim-pending
technologies: [kubernetes]
severity: high
tags: [kubernetes, storage, pvc, provisioning, production]
related: [kubernetes-mountvolume-setup-failed, kubernetes-failedscheduling]
last_reviewed: 2026-06-27
---

# Kubernetes PersistentVolumeClaim Pending

## Error Message

```text
NAME            STATUS    VOLUME   CAPACITY   ACCESS MODES   STORAGECLASS   AGE
data-postgres-0 Pending                                      gp3-encrypted  6m
```

```text
Warning  ProvisioningFailed  persistentvolume-controller
  storageclass.storage.k8s.io "gp3-encrypted" not found
```

```text
Normal   WaitForFirstConsumer  persistentvolume-controller
  waiting for first consumer to be created before binding
```

## Description

A PersistentVolumeClaim stuck in `Pending` has not been bound to a
PersistentVolume. With dynamic provisioning this means the CSI driver / external
provisioner has not created (or cannot create) a volume for the claim. With static
provisioning it means no existing PV matches the claim's size, access mode, and
StorageClass. Any pod consuming the PVC stays in `Pending`/`ContainerCreating`
until the claim binds.

## Technologies

- kubernetes (PV controller, CSI driver / external provisioner)

## Severity

**high** — a stateful pod cannot start without its volume. For a StatefulSet
database or a single-replica stateful service this is a full outage of that
workload.

## Common Causes

1. The referenced `storageClassName` does not exist (typo or never installed).
2. The StorageClass uses `volumeBindingMode: WaitForFirstConsumer`, so the PVC
   *intentionally* stays Pending until a pod that uses it is scheduled — this is
   normal, not an error.
3. The CSI driver / provisioner pod is unhealthy or lacks cloud IAM permissions to
   create the disk.
4. No static PV matches the claim's requested size, `accessModes`
   (e.g. `ReadWriteMany` requested but only RWO PVs exist), or selector.
5. Cloud quota or zone constraints: the volume cannot be created in the target AZ,
   or the account is at its disk/volume quota.

## Root Cause Analysis

For dynamic provisioning, the PV controller hands the claim to the StorageClass's
provisioner, which calls the cloud/CSI API to create a disk and then a matching
PV, finally binding the two. The provisioner emits `ProvisioningFailed` with the
underlying API error if any step fails (missing class, permission denied, quota,
zone). With `WaitForFirstConsumer`, binding is deliberately deferred until the
scheduler picks a node so the volume is created in the right topology — until then
`Pending` is expected. For static PVs, the controller searches existing `Available`
PVs for one that satisfies size/access-mode/class; if none matches, the PVC waits.

## Diagnostic Commands

```bash
# The PVC events: ProvisioningFailed or WaitForFirstConsumer
kubectl describe pvc <pvc> -n <namespace>

# Does the StorageClass exist, and what binding mode?
kubectl get storageclass

# Provisioner health (CSI controller pods)
kubectl get pods -n kube-system | grep -Ei 'csi|provisioner'

# Available static PVs that might match
kubectl get pv | grep Available
```

## Expected Results

```text
Warning  ProvisioningFailed  ...  storageclass "gp3-encrypted" not found
```

means a missing StorageClass. A permission/quota message from the CSI driver means
cloud-side failure. A `WaitForFirstConsumer` event with no pod scheduled is *not*
a failure — create or schedule the consuming pod. A healthy PVC reaches
`STATUS: Bound` with a `VOLUME` name populated.

## Resolution

1. Create or correct the StorageClass name so the PVC references an existing one:

   ```bash
   kubectl get storageclass   # confirm the exact name
   ```
2. For `WaitForFirstConsumer`, ensure a pod actually mounts the PVC and can be
   scheduled — the bind happens once the pod lands on a node.
3. For provisioner failures, fix the CSI driver's cloud IAM role / quota and
   restart the controller pod if it is crashlooping.
4. For static provisioning, create a matching PV (right size, access mode, class)
   or relax the PVC request.

## Validation

```bash
kubectl get pvc <pvc> -n <namespace>
# Expect: STATUS Bound with a VOLUME (pv name) populated; the pod then starts.
```

## Prevention

- Set a sensible `storageclass.kubernetes.io/is-default-class` and validate class
  names in CI.
- Monitor CSI provisioner health and cloud volume quota.
- Match `accessModes` to what the backend supports (most block storage is RWO).
- Document that `WaitForFirstConsumer` PVCs are Pending by design until consumed.

## Related Errors

- [Kubernetes MountVolume SetUp failed](./kubernetes-mountvolume-setup-failed.md)
- [Kubernetes FailedScheduling](./kubernetes-failedscheduling.md)

## References

- [Kubernetes: Persistent Volumes](https://kubernetes.io/docs/concepts/storage/persistent-volumes/)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`kubernetes` · `storage` · `pvc` · `provisioning` · `production`
