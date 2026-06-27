---
title: "GitLab Kubernetes Executor — Pod Timed Out / Stuck Pending"
slug: gitlab-kubernetes-executor-pod-timed-out
technologies: [gitlab]
severity: high
tags: [gitlab, runner, kubernetes, scheduling, production]
related: [gitlab-prepare-environment-exit-status-1, gitlab-job-stuck-no-runners-with-tags]
last_reviewed: 2026-06-27
---

# GitLab Kubernetes Executor — Pod Timed Out / Stuck Pending

## Error Message

```text
Preparing the "kubernetes" executor
Waiting for pod gitlab/runner-abc-project-123-concurrent-0 to be running, status is Pending
ERROR: Job failed (system failure): prepare environment: waiting for pod running: timed out waiting for pod to start
```

```text
ERROR: Job failed (system failure): image pull failed: Back-off pulling image "registry.gitlab.com/acme/builder:latest"
```

## Description

With the Kubernetes executor, each CI job runs in its own pod that the runner
creates and waits for. This error means the **build pod never reached Running**
within `poll_timeout`, so the runner aborted the job as a system failure. The pod
is usually stuck `Pending` (unschedulable / image pull back-off / PVC unbound) or
crashing in an init/helper container. The runner only sees "timed out"; the real
reason is in the pod's events.

## Technologies

- gitlab (GitLab Runner Kubernetes executor), kubernetes (scheduler/kubelet)

## Severity

**high** — affected jobs fail at setup and, if the cluster is broadly
unschedulable, every job on that runner fails — an effective CI outage.

## Common Causes

1. **Insufficient cluster resources** — no node satisfies the pod's CPU/memory
   requests, so it stays `Pending` past the timeout.
2. **Image pull failure** — wrong image, missing `imagePullSecrets`, or registry
   401/429 back-off (see related errors).
3. A node selector / taint-toleration / affinity in the runner config that no node
   matches.
4. An **unbound PVC** (cache/build volume) with no available storage class.
5. `poll_timeout` set too low for slow image pulls or autoscaling cold-starts.

## Root Cause Analysis

The runner's Kubernetes executor submits a pod (build + helper + any service
containers) and polls its status until it is `Running` or `poll_timeout` elapses.
Anything that keeps the pod out of `Running` — `Unschedulable` (resources/
selectors), `ImagePullBackOff`, `ErrImagePull`, `ContainerCreating` blocked on a
volume — causes the wait to expire. The runner reports the generic "timed out
waiting for pod to start," but `kubectl describe pod` shows the precise event
(FailedScheduling, Failed to pull image, FailedMount), which is where you fix it.

## Diagnostic Commands

```bash
# Find the stuck build pod (runner namespace)
kubectl get pods -n gitlab --sort-by=.metadata.creationTimestamp | tail -n 5

# The real reason is in the pod events
kubectl describe pod <runner-build-pod> -n gitlab

# Logs from helper/build containers (init failures show here)
kubectl logs <runner-build-pod> -n gitlab -c build --previous 2>/dev/null
kubectl logs <runner-build-pod> -n gitlab -c helper 2>/dev/null

# Node capacity vs requests, and any taints
kubectl describe nodes | grep -A6 'Allocated resources'
kubectl get nodes -o custom-columns=NAME:.metadata.name,TAINTS:.spec.taints

# Runner executor config: requests, timeout, pull secrets, selectors
grep -nE 'poll_timeout|cpu_request|memory_request|node_selector|image_pull_secrets|namespace' /etc/gitlab-runner/config.toml
```

## Expected Results

```text
# Unschedulable:
Events:
  Warning  FailedScheduling  default-scheduler  0/5 nodes available: 5 Insufficient cpu.

# Image pull:
  Warning  Failed  kubelet  Failed to pull image "...": 401 Unauthorized

# Healthy: pod transitions Pending -> ContainerCreating -> Running within seconds.
```

## Resolution

1. If unschedulable, lower the pod resource requests or add capacity:

   ```toml
   [runners.kubernetes]
     poll_timeout = 600
     cpu_request = "500m"
     memory_request = "512Mi"
   ```
2. Fix image pulls: correct the image path and add a pull secret:

   ```toml
   [runners.kubernetes]
     image_pull_secrets = ["gitlab-registry"]
   ```
   ```bash
   kubectl create secret docker-registry gitlab-registry -n gitlab \
     --docker-server="$CI_REGISTRY" --docker-username=... --docker-password=...
   ```
3. Match `node_selector`/tolerations to real nodes, or remove over-strict ones.
4. Ensure the cache/build `StorageClass` exists so PVCs bind; raise `poll_timeout`
   for autoscaled clusters with cold starts.

## Validation

```bash
# Re-run the job and watch the pod come up:
kubectl get pod <runner-build-pod> -n gitlab -w
# Expect STATUS Running, then the job proceeds past "Preparing the kubernetes executor".
```

## Prevention

- Keep cluster headroom and/or cluster-autoscaler tuned for CI burst load.
- Pre-pull common CI images to nodes or use a node-local registry mirror.
- Alert on build pods stuck `Pending` > N seconds in the runner namespace.

## Related Errors

- [GitLab Runner — Prepare Environment: Exit Status 1](./gitlab-prepare-environment-exit-status-1.md)
- [GitLab CI Job Stuck — No Runners With Required Tags](./gitlab-job-stuck-no-runners-with-tags.md)

## References

- [GitLab Runner: Kubernetes executor](https://docs.gitlab.com/runner/executors/kubernetes/)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`gitlab` · `runner` · `kubernetes` · `scheduling` · `production`
