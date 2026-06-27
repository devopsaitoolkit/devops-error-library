---
title: "Kubernetes Readiness Probe Failed"
slug: kubernetes-readiness-probe-failed
technologies: [kubernetes]
severity: medium
tags: [kubernetes, pod, probes, readiness, production]
related: [kubernetes-crashloopbackoff, kubernetes-progressdeadlineexceeded]
last_reviewed: 2026-06-27
---

# Kubernetes Readiness Probe Failed

## Error Message

```text
NAME                     READY   STATUS    RESTARTS   AGE
payments-7d9c8b6f5-kp2nq 0/1     Running   0          3m
```

```text
Warning  Unhealthy  kubelet  Readiness probe failed: HTTP probe failed with
  statuscode: 503
Warning  Unhealthy  kubelet  Readiness probe failed: Get
  "http://10.0.4.18:8080/ready": dial tcp 10.0.4.18:8080: connect: connection
  refused
```

## Description

A failing readiness probe leaves a pod `Running` but `0/1` ready. Unlike a
liveness failure, it does *not* restart the container — instead the endpoint
controller removes the pod's IP from all Service Endpoints, so it receives no
traffic. This is the correct behavior when the pod is genuinely not ready, but it
becomes an incident when the probe is misconfigured and healthy pods are pulled
out of rotation, shrinking serving capacity.

## Technologies

- kubernetes (kubelet, endpoints/EndpointSlice controller)

## Severity

**medium** — the pod stays alive but serves no traffic. If it affects a few
replicas it is degraded capacity; if it affects all replicas behind a Service it
is a full outage of that Service despite "Running" pods.

## Common Causes

1. The probe targets the wrong path or port (e.g. probing `/` instead of
   `/ready`, or the app listens on a different port).
2. `initialDelaySeconds` is too short, so the probe runs before the app finishes
   starting and the pod never gets a chance to pass.
3. A genuine dependency the readiness handler checks (DB, cache, downstream) is
   down, so the app correctly reports not-ready.
4. The probe handler is too strict or slow and trips `timeoutSeconds`.
5. The app returns non-2xx/3xx on the probe path (a 503 during warmup, or a 404
   because the route does not exist).

## Root Cause Analysis

The kubelet runs the readiness probe on `periodSeconds`. On `failureThreshold`
consecutive failures it sets the pod's `Ready` condition to `False`. The
EndpointSlice controller watches that condition and removes not-ready pod IPs from
the Service's endpoints, so kube-proxy / the load balancer stops sending traffic
there. Therefore the symptom (`0/1` ready, no traffic) is a faithful reflection of
the probe result — the question is whether the probe accurately represents
application health or is misconfigured. The event records the exact failure:
HTTP status, `connection refused` (nothing listening), or `timeout`.

## Diagnostic Commands

```bash
# The exact probe failure (status code / connection error)
kubectl describe pod <pod> -n <namespace>

# The configured readiness probe (path, port, delays, thresholds)
kubectl get pod <pod> -n <namespace> \
  -o jsonpath='{.spec.containers[0].readinessProbe}'

# Hit the probe endpoint from inside the pod
kubectl exec <pod> -n <namespace> -- \
  wget -qO- -S http://localhost:8080/ready 2>&1 | head

# Is the pod actually in the Service endpoints?
kubectl get endpointslice -n <namespace> -l kubernetes.io/service-name=<svc>
```

## Expected Results

```text
Warning  Unhealthy  kubelet  Readiness probe failed: HTTP probe failed with statuscode: 503
```

`503`/`404` on the probe path → app-reported not-ready or wrong path.
`connection refused` → app not listening yet (delay too short or wrong port).
`timeout` → handler too slow or `timeoutSeconds` too tight. A healthy pod shows
`READY 1/1`, no `Unhealthy` events, and its IP present in the EndpointSlice.

## Resolution

1. Point the probe at the real readiness endpoint and port, and give startup
   enough room — prefer a `startupProbe` for slow boots:

   ```yaml
   readinessProbe:
     httpGet: { path: /ready, port: 8080 }
     initialDelaySeconds: 5
     periodSeconds: 10
     timeoutSeconds: 2
     failureThreshold: 3
   startupProbe:
     httpGet: { path: /ready, port: 8080 }
     failureThreshold: 30
     periodSeconds: 5
   ```
2. If a real dependency is down, fix the dependency — the probe is doing its job.
3. Loosen `timeoutSeconds`/`failureThreshold` if the handler is legitimately slow.
4. Make the readiness handler check only what is required to serve traffic, not
   every transitive dependency.

## Validation

```bash
kubectl get pod <pod> -n <namespace> -w
# Expect: READY 1/1, no further Unhealthy events, IP back in the EndpointSlice.
```

## Prevention

- Keep liveness and readiness probes distinct; use `startupProbe` for slow starts.
- Make readiness reflect "can serve traffic," not deep health of every dependency.
- Test probe paths/ports in CI against the running container.
- Alert when ready replica count drops below desired for a Service.

## Related Errors

- [Kubernetes CrashLoopBackOff](./kubernetes-crashloopbackoff.md)
- [Kubernetes ProgressDeadlineExceeded](./kubernetes-progressdeadlineexceeded.md)

## References

- [Kubernetes: Configure Liveness, Readiness and Startup Probes](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`kubernetes` · `pod` · `probes` · `readiness` · `production`
