---
title: "Kubernetes ImagePullBackOff"
slug: kubernetes-imagepullbackoff
technologies: [kubernetes]
severity: high
tags: [kubernetes, pod, image, registry, production]
related: [kubernetes-errimagepull, kubernetes-crashloopbackoff]
last_reviewed: 2026-06-27
---

# Kubernetes ImagePullBackOff

## Error Message

```text
NAME                       READY   STATUS             RESTARTS   AGE
api-6d4c7b9f8c-2nklp       0/1     ImagePullBackOff   0          3m14s
```

```text
Warning  Failed   2m9s (x4 over 3m)  kubelet  Failed to pull image "registry.internal/api:1.8.3":
  rpc error: code = NotFound desc = failed to pull and unpack image
  "registry.internal/api:1.8.3": failed to resolve reference
  "registry.internal/api:1.8.3": not found
Warning  Failed   2m9s (x4 over 3m)  kubelet  Error: ErrImagePull
Normal   BackOff  119s (x6 over 3m)  kubelet  Back-off pulling image "registry.internal/api:1.8.3"
```

## Description

`ImagePullBackOff` is the state the kubelet enters after one or more failed image
pulls. The first failure surfaces as `ErrImagePull`; once the kubelet decides to
retry with an exponential back-off (capped at 5 minutes), the status becomes
`ImagePullBackOff`. The container never starts because its image cannot be
retrieved from the configured registry. It is the registry-side counterpart of a
startup failure: the pod is scheduled and the node is healthy, but the image
layer fetch does not complete.

## Technologies

- kubernetes (kubelet, container runtime, image service)

## Severity

**high** — the affected pod cannot start at all, so the workload has zero healthy
replicas on that node. For a single-replica Deployment or a new rollout this is a
full outage for that service.

## Common Causes

1. The image tag does not exist in the registry (typo, never pushed, or pruned).
2. The registry requires authentication and no valid `imagePullSecret` is
   attached to the pod's ServiceAccount.
3. The registry hostname/port is wrong or unreachable from the node (DNS, network
   policy, firewall).
4. Rate limiting from a public registry (for example Docker Hub anonymous pull
   limits) returns `toomanyrequests`.
5. Image platform/arch mismatch where the manifest has no entry for the node's
   architecture.

## Root Cause Analysis

The kubelet asks the container runtime to pull the image reference declared in the
pod spec. The runtime resolves the reference against the registry, authenticates
if credentials are present, and downloads the manifest and layers. Any failure in
resolve, authenticate, or download stages raises `ErrImagePull`. After repeated
failures the kubelet stops hammering the registry and backs off, reporting
`ImagePullBackOff`. The precise reason — `not found`, `unauthorized`,
`no such host`, `toomanyrequests` — is carried in the event message and is what
distinguishes a missing tag from an auth or network problem.

## Diagnostic Commands

```bash
# Events with the exact pull failure reason
kubectl describe pod <pod> -n <namespace>

# The image reference the pod is actually requesting
kubectl get pod <pod> -n <namespace> \
  -o jsonpath='{.spec.containers[*].image}'

# Confirm an imagePullSecret is attached to the ServiceAccount
kubectl get serviceaccount <sa> -n <namespace> -o yaml

# Inspect the pull secret's registry host (decoded auth is base64)
kubectl get secret <pull-secret> -n <namespace> \
  -o jsonpath='{.data.\.dockerconfigjson}' | base64 -d
```

## Expected Results

```text
Events:
  Warning  Failed   kubelet  Failed to pull image "registry.internal/api:1.8.3":
    ... not found
  Warning  Failed   kubelet  Error: ErrImagePull
  Normal   BackOff  kubelet  Back-off pulling image "registry.internal/api:1.8.3"
```

`not found` means a missing tag. `unauthorized` / `401` means a credentials
problem. `no such host` / `i/o timeout` means a network or DNS issue. A healthy
pod shows a `Normal  Pulled  ...  Successfully pulled image` event instead.

## Resolution

1. Confirm the tag exists: `crane ls registry.internal/api` or push the image.
2. For private registries, create and attach a pull secret:

   ```bash
   kubectl create secret docker-registry regcred \
     --docker-server=registry.internal \
     --docker-username=<user> --docker-password=<pass> -n <namespace>
   kubectl patch serviceaccount default -n <namespace> \
     -p '{"imagePullSecrets":[{"name":"regcred"}]}'
   ```
3. For DNS/network failures, verify the node can reach the registry and that no
   NetworkPolicy or egress firewall blocks it.
4. For rate limits, authenticate even to public registries or mirror the image
   into your own registry.

## Validation

```bash
kubectl get pod <pod> -n <namespace> -w
# Expect: a "Successfully pulled image" event, then STATUS Running, READY 1/1.
```

## Prevention

- Pin images to immutable digests (`@sha256:...`) and verify they exist in CI
  before the manifest is applied.
- Centralize `imagePullSecrets` on the ServiceAccount, not per-pod.
- Mirror critical public images into an internal registry to avoid rate limits.
- Add an admission policy that rejects images from unapproved registries.

## Related Errors

- [Kubernetes ErrImagePull](./kubernetes-errimagepull.md)
- [Kubernetes CrashLoopBackOff](./kubernetes-crashloopbackoff.md)

## References

- [Kubernetes: Images](https://kubernetes.io/docs/concepts/containers/images/)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`kubernetes` · `pod` · `image` · `registry` · `production`
