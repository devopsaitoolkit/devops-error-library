---
title: "Kubernetes MountVolume SetUp failed"
slug: kubernetes-mountvolume-setup-failed
technologies: [kubernetes]
severity: high
tags: [kubernetes, storage, volume, csi, production]
related: [kubernetes-persistentvolumeclaim-pending, kubernetes-createcontainerconfigerror]
last_reviewed: 2026-06-27
---

# Kubernetes MountVolume SetUp failed

## Error Message

```text
Warning  FailedMount  kubelet
  MountVolume.SetUp failed for volume "pvc-3a9f2c1e-...":
  rpc error: code = Internal desc = Could not mount
  "/dev/disk/by-id/...": mount failed: exit status 32
  mount: /var/lib/kubelet/pods/.../mount: wrong fs type, bad option,
  bad superblock ...
```

```text
Warning  FailedAttachVolume  attachdetach-controller
  AttachVolume.Attach failed for volume "pvc-3a9f2c1e-...":
  rpc error: code = NotFound desc = volume not found
```

## Description

`MountVolume.SetUp failed` (often shown as a `FailedMount` event) means the
kubelet bound the PVC and the volume exists, but the volume could not be attached
to the node or mounted into the pod. The pod is stuck in `ContainerCreating`. This
is distinct from a Pending PVC: the claim is `Bound`; the failure is in the
attach/mount stage performed by the CSI node plugin on the target node.

## Technologies

- kubernetes (kubelet, CSI node plugin, attach/detach controller)

## Severity

**high** — the pod cannot start without its mounted volume. For stateful
workloads (databases, queues) this blocks the service until the mount succeeds.

## Common Causes

1. The volume is already attached to (and mounted on) another node — a stuck
   `ReadWriteOnce` volume left behind by a previous pod that did not detach.
2. Filesystem mismatch or corruption (`wrong fs type, bad superblock`), or the
   requested `fsType` does not match the volume.
3. The CSI node plugin daemonset is unhealthy or missing on the target node.
4. A `subPath` or mount path that does not exist, or permission/SELinux denial.
5. Underlying cloud volume was deleted out-of-band (`volume not found`) or is in a
   different AZ than the node.

## Root Cause Analysis

Mounting a CSI volume is a two-step dance: the attach/detach controller calls
`ControllerPublishVolume` to attach the disk to the node, then the kubelet calls
the node plugin's `NodeStageVolume`/`NodePublishVolume` to format (if needed) and
bind-mount it into the pod directory. A failure at attach surfaces as
`FailedAttachVolume`; a failure at mount surfaces as `MountVolume.SetUp failed`.
The most common production cause is RWO contention: a previous pod on another node
still holds the volume, so the new node's attach is rejected. Filesystem and
plugin errors show up directly in the mount exit status.

## Diagnostic Commands

```bash
# The FailedMount/FailedAttachVolume event detail
kubectl describe pod <pod> -n <namespace>

# Is the volume attached elsewhere? (which node holds it)
kubectl get volumeattachment | grep <pv-name>

# CSI node plugin health on the target node
kubectl get pods -n kube-system -o wide | grep -i csi

# Kubelet mount errors on the node
journalctl -u kubelet -n 200 --no-pager | grep -iE 'mount|attach'
```

## Expected Results

```text
Warning  FailedMount  kubelet  MountVolume.SetUp failed ... wrong fs type, bad superblock
```

or, for RWO contention:

```text
Multi-Attach error for volume "pvc-..." Volume is already exclusively attached
to one node and can't be attached to another
```

A healthy mount produces no `FailedMount` events and the pod proceeds past
`ContainerCreating`.

## Resolution

1. For RWO multi-attach, ensure the old pod is fully terminated so the volume
   detaches; if a node is dead, force-detach by deleting the stale
   `VolumeAttachment` after confirming the old pod is gone.
2. For filesystem errors, verify the PV's `fsType` matches the volume and the
   filesystem is not corrupt; reformat only an empty volume.
3. For a missing/unhealthy CSI plugin, restore the node daemonset pod.
4. For `volume not found`, the backing disk was deleted — restore from snapshot or
   recreate the PV/PVC.

## Validation

```bash
kubectl get pod <pod> -n <namespace> -w
# Expect: leaves ContainerCreating, mounts succeed, reaches Running 1/1.
kubectl exec <pod> -n <namespace> -- df -h /data
```

## Prevention

- Use `StatefulSet` with stable identities and proper termination so RWO volumes
  detach cleanly on reschedule.
- Monitor CSI node-plugin health on every node.
- Alert on `Multi-Attach` and `FailedMount` events.
- Snapshot critical volumes so a deleted disk is recoverable.

## Related Errors

- [Kubernetes PersistentVolumeClaim Pending](./kubernetes-persistentvolumeclaim-pending.md)
- [Kubernetes CreateContainerConfigError](./kubernetes-createcontainerconfigerror.md)

## References

- [Kubernetes: CSI Volumes](https://kubernetes.io/docs/concepts/storage/volumes/#csi)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`kubernetes` · `storage` · `volume` · `csi` · `production`
