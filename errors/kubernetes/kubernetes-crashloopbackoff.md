---
title: "Kubernetes CrashLoopBackOff"
slug: kubernetes-crashloopbackoff
technologies: [kubernetes]
severity: high
tags: [kubernetes, pod, scheduling, crashloopbackoff, production]
related: [kubernetes-imagepullbackoff, kubernetes-oomkilled]
last_reviewed: 2026-06-27
---

# Kubernetes CrashLoopBackOff

## Error Message

```text
NAME                     READY   STATUS             RESTARTS      AGE
web-7c9f8d6b5b-x2kqz     0/1     CrashLoopBackOff   6 (2m11s ago) 9m
```

```text
Warning  BackOff  2m (x12 over 7m)  kubelet  Back-off restarting failed container web in pod web-7c9f8d6b5b-x2kqz_prod(...)
```

## Description

`CrashLoopBackOff` is a pod state, not an error in itself. The container starts,
exits, and the kubelet restarts it — repeatedly — applying an exponential
back-off (10s, 20s, 40s … capped at 5 minutes) between attempts. The pod never
reaches a stable `Running` state. It is one of the most common reasons a workload
fails to come up in production.

## Technologies

- kubernetes (kubelet, container runtime)

## Severity

**high** — the affected workload has zero healthy replicas (or runs degraded). If
it is a single-replica Deployment or a critical DaemonSet, this is a partial or
full outage for that service.

## Common Causes

1. The application process exits non-zero on startup (bad config, missing
   environment variable, a failed dependency it needs at boot).
2. An over-aggressive `livenessProbe` kills the container before it finishes
   starting, so Kubernetes restarts a process that was actually healthy.
3. A required ConfigMap, Secret, or mounted file is missing or misnamed and the
   app aborts during initialization.
4. The container command/entrypoint is wrong (binary not found, not executable).
5. The container is `OOMKilled` on each start (see related error).

## Root Cause Analysis

Kubernetes reports the *symptom* (the restart loop), not the cause. The real
error is in the **previous** container's logs and in the pod's `lastState`. When
a container exits, the kubelet records the exit code and reason in
`state.terminated`, then schedules a restart after the back-off interval. Reading
the previous logs and the exit code tells you whether the process crashed
(application bug/config) or was killed by Kubernetes (probe or OOM).

## Diagnostic Commands

```bash
# Events, restart count, last state and exit code for the pod
kubectl describe pod <pod> -n <namespace>

# Logs from the PREVIOUS (crashed) container — where the real error is
kubectl logs <pod> -n <namespace> --previous

# Exit code and termination reason, as JSON
kubectl get pod <pod> -n <namespace> \
  -o jsonpath='{.status.containerStatuses[0].lastState.terminated}'

# Cluster events around the crash, newest last
kubectl get events -n <namespace> --sort-by=.lastTimestamp
```

## Expected Results

```text
    Last State:     Terminated
      Reason:       Error
      Exit Code:    1
      Started:      ...
      Finished:     ...
    Restart Count:  6
Events:
  Warning  BackOff  kubelet  Back-off restarting failed container
```

A non-zero `Exit Code` with `Reason: Error` points to an application/config
failure. `Reason: OOMKilled` with exit code `137` points to a memory limit.

## Resolution

1. Read `kubectl logs <pod> --previous` and fix the underlying startup failure
   (missing env var, unreachable dependency, bad config value).
2. If the failure is a too-aggressive liveness probe, add an
   `initialDelaySeconds`/`failureThreshold` that matches real startup time, and
   prefer a separate `readinessProbe` for slow starts:

   ```yaml
   livenessProbe:
     httpGet: { path: /healthz, port: 8080 }
     initialDelaySeconds: 20
     periodSeconds: 10
     failureThreshold: 3
   ```
3. If `OOMKilled`, raise `resources.limits.memory` or fix the leak.
4. Reproduce locally with the exact image, args, and env to confirm the fix
   before redeploying.

## Validation

```bash
kubectl get pod <pod> -n <namespace> -w
# Expect: STATUS Running, READY 1/1, and RESTARTS stops incrementing.
```

## Prevention

- Make containers fail fast and log the reason to stdout/stderr.
- Keep `livenessProbe` and `readinessProbe` distinct; never let a slow start trip
  liveness.
- Validate required ConfigMaps/Secrets exist in CI before deploying.
- Set memory requests/limits from observed usage to avoid OOM restart loops.

## Related Errors

- [Kubernetes ImagePullBackOff](./kubernetes-imagepullbackoff.md)
- [Kubernetes OOMKilled](./kubernetes-oomkilled.md)

## References

- [Kubernetes: Debug Running Pods](https://kubernetes.io/docs/tasks/debug/debug-application/debug-running-pod/)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`kubernetes` · `pod` · `crashloopbackoff` · `probes` · `production`
