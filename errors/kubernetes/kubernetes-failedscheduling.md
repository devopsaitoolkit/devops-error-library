---
title: "Kubernetes FailedScheduling"
slug: kubernetes-failedscheduling
technologies: [kubernetes]
severity: high
tags: [kubernetes, scheduler, pending, resources, production]
related: [kubernetes-node-not-ready, kubernetes-evicted-pod]
last_reviewed: 2026-06-27
---

# Kubernetes FailedScheduling

## Error Message

```text
NAME                         READY   STATUS    RESTARTS   AGE
ingest-7f5d8c6b4d-h9xqv      0/1     Pending   0          4m2s
```

```text
Warning  FailedScheduling  default-scheduler  0/12 nodes are available:
  3 Insufficient cpu, 4 Insufficient memory,
  3 node(s) had untolerated taint {dedicated: gpu},
  2 node(s) didn't match Pod's node affinity/selector.
  preemption: 0/12 nodes are available: 12 No preemption victims found.
```

## Description

`FailedScheduling` is emitted by the kube-scheduler when it cannot find any node
that satisfies all of a pending pod's constraints. The pod stays in `Pending`
indefinitely (the scheduler retries with back-off). The event message is a
per-reason tally across all nodes — it tells you exactly how many nodes each
predicate eliminated, which is the fastest path to the root cause.

## Technologies

- kubernetes (kube-scheduler)

## Severity

**high** — the pod never runs. For a scaling event or new rollout this blocks
capacity; for a single-replica workload it is a full outage of that service.

## Common Causes

1. Insufficient allocatable CPU or memory: the pod's `requests` exceed what any
   node has free.
2. Taints on nodes that the pod does not tolerate.
3. `nodeSelector` / `nodeAffinity` / `nodeName` that no node matches.
4. Pod / node anti-affinity or `topologySpreadConstraints` that cannot be
   satisfied with current placement.
5. Unsatisfiable volume constraints (a PVC bound to a zone with no schedulable
   node), or `podAntiAffinity` requiring more nodes than exist.

## Root Cause Analysis

The scheduler runs each pending pod through two phases: *filtering* (predicates
like fit, taints, affinity, volume zone) to produce feasible nodes, then *scoring*
to pick the best. `FailedScheduling` means the filtering phase eliminated every
node. The message aggregates the reason each node was rejected. Because `requests`
(not `limits`) drive the fit check, a pod can be unschedulable even on a node that
*looks* idle if existing requests already reserve the capacity. Preemption only
helps if lower-priority victims exist; "No preemption victims found" means even
evicting pods would not free a fitting node.

## Diagnostic Commands

```bash
# The FailedScheduling event with the per-reason node tally
kubectl describe pod <pod> -n <namespace>

# The pod's CPU/memory requests that must fit
kubectl get pod <pod> -n <namespace> \
  -o jsonpath='{.spec.containers[*].resources.requests}'

# Allocatable vs allocated capacity per node
kubectl describe nodes | grep -A6 'Allocated resources'

# Node taints that may be blocking the pod
kubectl get nodes -o json \
  | jq '.items[] | {name:.metadata.name, taints:.spec.taints}'
```

## Expected Results

```text
Warning  FailedScheduling  default-scheduler  0/12 nodes are available:
  3 Insufficient cpu, 4 Insufficient memory, 3 node(s) had untolerated taint ...
```

The dominant phrase identifies the fix: `Insufficient cpu/memory` → capacity or
oversized requests; `untolerated taint` → add a toleration; `didn't match node
affinity/selector` → fix the selector or label a node; `had volume node affinity
conflict` → PVC zone mismatch.

## Resolution

1. If capacity is the issue, lower the pod's `requests` to a realistic value or
   add nodes / scale the cluster autoscaler.
2. To run on tainted nodes, add a matching toleration:

   ```yaml
   tolerations:
   - key: "dedicated"
     operator: "Equal"
     value: "gpu"
     effect: "NoSchedule"
   ```
3. Fix a `nodeSelector`/`nodeAffinity` that no node matches, or label a node so it
   matches.
4. Relax `requiredDuringScheduling` spread/affinity to `preferred` if it is
   over-constrained.

## Validation

```bash
kubectl get pod <pod> -n <namespace> -w
# Expect: STATUS moves Pending -> ContainerCreating -> Running with a node assigned.
```

## Prevention

- Set `requests` from observed usage so the fit check reflects reality.
- Keep the cluster autoscaler configured with headroom for burst scheduling.
- Review taints/affinity in CI against the actual node pool labels.
- Prefer `preferredDuringScheduling` for spread to avoid hard unschedulability.

## Related Errors

- [Kubernetes Node NotReady](./kubernetes-node-not-ready.md)
- [Kubernetes Evicted Pod](./kubernetes-evicted-pod.md)

## References

- [Kubernetes: Scheduler](https://kubernetes.io/docs/concepts/scheduling-eviction/kube-scheduler/)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`kubernetes` · `scheduler` · `pending` · `resources` · `production`
