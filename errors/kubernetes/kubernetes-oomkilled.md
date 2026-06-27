---
title: "Kubernetes OOMKilled"
slug: kubernetes-oomkilled
technologies: [kubernetes]
severity: high
tags: [kubernetes, pod, memory, oom, production]
related: [kubernetes-crashloopbackoff, kubernetes-evicted-pod]
last_reviewed: 2026-06-27
---

# Kubernetes OOMKilled

## Error Message

```text
    Last State:     Terminated
      Reason:       OOMKilled
      Exit Code:    137
      Started:      Sat, 27 Jun 2026 09:12:04 +0000
      Finished:     Sat, 27 Jun 2026 09:14:51 +0000
    Restart Count:  4
```

```text
kernel: Memory cgroup out of memory: Killed process 24817 (java)
  total-vm:4831232kB, anon-rss:1965320kB, file-rss:18044kB,
  oom_score_adj:968
```

## Description

`OOMKilled` means the Linux kernel's out-of-memory killer terminated the
container's process because the container exceeded its memory cgroup limit (or the
node ran out of memory). Kubernetes surfaces this as `Reason: OOMKilled` with exit
code `137` (128 + signal 9, SIGKILL). The container is then restarted by the
kubelet, which commonly leads to a `CrashLoopBackOff` if the workload OOMs on
every start.

## Technologies

- kubernetes (kubelet, container runtime, Linux cgroups / OOM killer)

## Severity

**high** — the process is killed abruptly with no chance to flush state or drain
connections, risking dropped requests and, for stateful workloads, data
corruption. Repeated OOM kills take the replica out of rotation.

## Common Causes

1. `resources.limits.memory` is set lower than the application's real working set.
2. A genuine memory leak that grows unbounded until the limit is hit.
3. A runtime (JVM/Node/Python) whose heap is sized larger than the container
   limit because it reads host memory, not the cgroup limit.
4. A traffic or batch-size spike that pushes memory past the limit transiently.
5. Node-level memory pressure killing the highest `oom_score_adj` container even
   when it is within its own limit.

## Root Cause Analysis

Each container runs in a memory cgroup. When the cgroup's usage (RSS + page cache
that cannot be reclaimed) reaches `limits.memory`, the kernel invokes the OOM
killer scoped to that cgroup and kills the process with SIGKILL. The kubelet reads
the cgroup's `memory.oom_control` / exit signal and records `OOMKilled`. If the
limit is unset, the container can instead trigger a *node-level* OOM, where the
kernel picks a victim by `oom_score_adj` (driven by the container's QoS class),
which is why Burstable/BestEffort pods are killed first under node pressure.

## Diagnostic Commands

```bash
# Termination reason and exit code 137
kubectl describe pod <pod> -n <namespace>

# Last-state JSON to confirm OOMKilled programmatically
kubectl get pod <pod> -n <namespace> \
  -o jsonpath='{.status.containerStatuses[0].lastState.terminated.reason}'

# Live memory usage vs limit
kubectl top pod <pod> -n <namespace> --containers

# Kernel OOM lines on the node
journalctl -k -n 200 | grep -i 'out of memory'
```

## Expected Results

```text
Reason:       OOMKilled
Exit Code:    137
```

```text
kernel: Memory cgroup out of memory: Killed process ... (java)
```

`Exit Code 137` plus `OOMKilled` confirms a memory limit hit. `kubectl top`
showing usage at or near the limit before the kill corroborates it. A node-level
OOM line *without* a cgroup limit hit points to node memory pressure rather than
the container's own limit.

## Resolution

1. Right-size the limit from observed peak usage, with headroom:

   ```yaml
   resources:
     requests: { memory: "768Mi" }
     limits:   { memory: "1Gi" }
   ```
2. For the JVM, make the heap cgroup-aware: `-XX:MaxRAMPercentage=75.0`. For
   Node.js, set `--max-old-space-size` below the container limit.
3. If it is a leak, profile and fix it; a higher limit only delays the kill.
4. Set memory `requests` equal to `limits` for critical pods so they land in the
   Guaranteed QoS class and are killed last under node pressure.

## Validation

```bash
kubectl top pod <pod> -n <namespace> --containers
# Expect: steady memory well below the limit, RESTARTS no longer incrementing.
```

## Prevention

- Set memory requests/limits from real metrics, not guesses; alert on usage > 80%
  of limit.
- Make runtimes cgroup-aware so they do not size buffers from host RAM.
- Load-test to find the true working set before setting limits.
- Use a VerticalPodAutoscaler in recommendation mode to track drift.

## Related Errors

- [Kubernetes CrashLoopBackOff](./kubernetes-crashloopbackoff.md)
- [Kubernetes Evicted Pod](./kubernetes-evicted-pod.md)

## References

- [Kubernetes: Assign Memory Resources](https://kubernetes.io/docs/tasks/configure-pod-container/assign-memory-resource/)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`kubernetes` · `pod` · `memory` · `oom` · `production`
