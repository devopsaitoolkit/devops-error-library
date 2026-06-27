---
title: "Kubernetes ProgressDeadlineExceeded"
slug: kubernetes-progressdeadlineexceeded
technologies: [kubernetes]
severity: medium
tags: [kubernetes, deployment, rollout, progress, production]
related: [kubernetes-crashloopbackoff, kubernetes-readiness-probe-failed]
last_reviewed: 2026-06-27
---

# Kubernetes ProgressDeadlineExceeded

## Error Message

```text
Waiting for deployment "checkout" rollout to finish: 2 out of 5 new replicas
have been updated...
error: deployment "checkout" exceeded its progress deadline
```

```text
Conditions:
  Type           Status  Reason
  Available      True    MinimumReplicasAvailable
  Progressing    False   ProgressDeadlineExceeded
```

## Description

`ProgressDeadlineExceeded` is set by the Deployment controller on the
`Progressing` condition when a rollout fails to make forward progress within
`spec.progressDeadlineSeconds` (default 600s). It does *not* roll back or stop the
Deployment by itself — it is a signal that new replicas are not becoming available
fast enough. Tools like `kubectl rollout status` and most CI/CD gates treat it as
a failed deploy. The real fault is always *why* the new ReplicaSet's pods are not
reaching ready.

## Technologies

- kubernetes (Deployment controller)

## Severity

**medium** — the old ReplicaSet usually keeps serving, so the running version
stays up; the impact is a stuck/failed rollout that blocks shipping the new
version. It rises to high if combined with `maxUnavailable` that has already
removed healthy old pods.

## Common Causes

1. New pods crash on startup (`CrashLoopBackOff`) so they never become ready.
2. New pods stay `Pending` because of `FailedScheduling` (no capacity/affinity
   match).
3. A readiness probe on the new pods never passes (misconfigured path/port or slow
   start beyond the probe budget).
4. Image pull failure (`ImagePullBackOff`) on the new tag.
5. `progressDeadlineSeconds` is simply shorter than the legitimate time the app
   needs to warm up at the configured rollout rate.

## Root Cause Analysis

The Deployment controller tracks rollout progress by watching the new ReplicaSet's
*available* replica count climb toward the desired count. Each time availability
advances, it resets an internal progress timer. If the timer reaches
`progressDeadlineSeconds` with no advance, it stamps `Progressing=False` with
reason `ProgressDeadlineExceeded`. Therefore the condition is downstream: the new
pods are blocked from becoming ready by one of the pod-level errors above, and the
fix lives in the new ReplicaSet's pods, not in the Deployment object.

## Diagnostic Commands

```bash
# The Progressing condition and reason
kubectl describe deployment <deploy> -n <namespace>

# The new ReplicaSet and how many replicas are ready
kubectl get rs -n <namespace> -l app=<app> \
  --sort-by=.metadata.creationTimestamp

# Why the new pods are not ready (events/probes/image)
kubectl get pods -n <namespace> -l app=<app> -o wide
kubectl describe pod <new-pod> -n <namespace>

# Live rollout state
kubectl rollout status deployment/<deploy> -n <namespace> --timeout=10s
```

## Expected Results

```text
Progressing   False   ProgressDeadlineExceeded
```

Then the *new* pods reveal the true cause — `CrashLoopBackOff`, `Pending` with a
`FailedScheduling` event, `ImagePullBackOff`, or `Running` but `0/1` ready due to
a failing readiness probe. A healthy rollout instead shows
`Progressing  True  NewReplicaSetAvailable`.

## Resolution

1. Diagnose and fix the new pods' underlying error (crash, schedule, probe, or
   image) — see the related errors.
2. If the app legitimately needs longer to roll out, raise the deadline:

   ```yaml
   spec:
     progressDeadlineSeconds: 1200
   ```
3. If the new version is broken, roll back:
   `kubectl rollout undo deployment/<deploy> -n <namespace>`.
4. Re-trigger the rollout after fixing:
   `kubectl rollout restart deployment/<deploy> -n <namespace>`.

## Validation

```bash
kubectl rollout status deployment/<deploy> -n <namespace>
# Expect: "deployment <deploy> successfully rolled out" and Progressing=True.
```

## Prevention

- Set `progressDeadlineSeconds` slightly above the worst observed honest rollout
  time.
- Get readiness probes right so ready means ready; fail fast on real crashes.
- Use a canary/progressive rollout so a bad version is caught on a small slice.
- Gate CI on `kubectl rollout status` so failed rollouts block the pipeline.

## Related Errors

- [Kubernetes CrashLoopBackOff](./kubernetes-crashloopbackoff.md)
- [Kubernetes Readiness Probe Failed](./kubernetes-readiness-probe-failed.md)

## References

- [Kubernetes: Deployment Status](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/#deployment-status)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`kubernetes` · `deployment` · `rollout` · `progress` · `production`
