---
title: "Kubernetes Evicted Pod"
slug: kubernetes-evicted-pod
technologies: [kubernetes]
severity: high
tags: [kubernetes, node, eviction, resources, production]
related: [kubernetes-oomkilled, kubernetes-node-not-ready]
last_reviewed: 2026-06-27
---

# Kubernetes Evicted Pod

## Error Message

```text
NAME                       READY   STATUS    RESTARTS   AGE
analytics-6c7f9d8b4-mn2pq  0/1     Evicted   0          12m
```

```text
Status:   Failed
Reason:   Evicted
Message:  The node was low on resource: ephemeral-storage. Container app was
          using 9876Mi, which exceeds its request of 0. Threshold quantity:
          1063256064, available: 982040Ki.
```

## Description

An `Evicted` pod is one the kubelet terminated to reclaim a starved node-level
resource — memory, ephemeral storage (disk), or inodes — under
*node-pressure eviction*. Unlike an OOM kill (kernel-level, single container), an
eviction is a kubelet decision that removes whole pods, lowest QoS and highest
over-request first, to bring the node back below its eviction threshold. Evicted
pods are left in a `Failed` terminal state and are not restarted in place; the
controller (Deployment/ReplicaSet) reschedules a replacement elsewhere.

## Technologies

- kubernetes (kubelet node-pressure eviction)

## Severity

**high** — capacity is being shed under pressure. A node hitting disk or memory
thresholds can evict many pods at once, and evicted-pod objects accumulate as
clutter that masks the underlying node problem.

## Common Causes

1. Node disk pressure from container logs, image cache, or `emptyDir` /
   ephemeral-storage usage exceeding the eviction threshold.
2. Node memory pressure where total pod usage approaches allocatable memory.
3. Pods with no (or too-low) resource `requests` running on a saturated node — the
   kubelet evicts them first.
4. Inode exhaustion (`nodefs.inodesFree`) from many small files.
5. A single pod writing huge volumes to ephemeral storage with no
   `ephemeral-storage` limit.

## Root Cause Analysis

The kubelet continuously compares node resource usage against configured eviction
thresholds (e.g. `memory.available < 100Mi`, `nodefs.available < 10%`). When a
soft or hard threshold is crossed, it ranks pods by QoS class and by how far each
exceeds its requests, then evicts pods until the node is back under threshold.
Because the decision is request-relative, a pod with `requests: 0` that uses
gigabytes of disk is an obvious early victim. The `Message` field records exactly
which resource was low and how the offending container compared to its request.

## Diagnostic Commands

```bash
# The eviction reason and offending resource
kubectl describe pod <pod> -n <namespace>

# All evicted pods across the cluster
kubectl get pods -A --field-selector=status.phase=Failed \
  -o wide | grep Evicted

# Node conditions: DiskPressure / MemoryPressure
kubectl describe node <node> | grep -A5 Conditions

# Disk and inode usage on the node
df -h /var/lib/kubelet && df -i /var/lib/kubelet
```

## Expected Results

```text
Reason:   Evicted
Message:  The node was low on resource: ephemeral-storage ...
```

```text
Conditions:
  Type             Status
  DiskPressure     True
```

The `Message` names the scarce resource; the node's `DiskPressure` or
`MemoryPressure` condition being `True` confirms node-level pressure rather than a
single-container OOM.

## Resolution

1. Reclaim the scarce resource on the node: prune unused images
   (`crictl rmi --prune`), rotate/limit container logs, clear oversized
   `emptyDir` usage.
2. Set realistic `requests` and an `ephemeral-storage` limit so the kubelet ranks
   pods fairly:

   ```yaml
   resources:
     requests: { memory: "512Mi", ephemeral-storage: "1Gi" }
     limits:   { memory: "1Gi",  ephemeral-storage: "2Gi" }
   ```
3. Clean up accumulated evicted-pod objects:
   `kubectl delete pods -A --field-selector=status.phase=Failed`.
4. Add nodes or move log/scratch data to a PersistentVolume off the node disk.

## Validation

```bash
kubectl describe node <node> | grep -E 'DiskPressure|MemoryPressure'
# Expect: both False. New pods stay Running and are no longer Evicted.
```

## Prevention

- Always set memory and `ephemeral-storage` requests/limits.
- Cap container log size (`--container-log-max-size`) and run image GC.
- Alert on node `DiskPressure`/`MemoryPressure` and on free-inode thresholds.
- Use a dedicated volume for scratch data instead of node ephemeral storage.

## Related Errors

- [Kubernetes OOMKilled](./kubernetes-oomkilled.md)
- [Kubernetes Node NotReady](./kubernetes-node-not-ready.md)

## References

- [Kubernetes: Node-pressure Eviction](https://kubernetes.io/docs/concepts/scheduling-eviction/node-pressure-eviction/)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`kubernetes` · `node` · `eviction` · `resources` · `production`
