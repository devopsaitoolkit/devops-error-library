---
title: "Kubernetes ErrImagePull"
slug: kubernetes-errimagepull
technologies: [kubernetes]
severity: high
tags: [kubernetes, pod, image, registry, production]
related: [kubernetes-imagepullbackoff, kubernetes-exec-format-error]
last_reviewed: 2026-06-27
---

# Kubernetes ErrImagePull

## Error Message

```text
NAME                       READY   STATUS         RESTARTS   AGE
worker-58b7c6d99f-q7wzt    0/1     ErrImagePull   0          18s
```

```text
Warning  Failed  17s  kubelet  Failed to pull image "ghcr.io/acme/worker:latest":
  rpc error: code = Unknown desc = failed to pull and unpack image
  "ghcr.io/acme/worker:latest": failed to resolve reference
  "ghcr.io/acme/worker:latest": unexpected status from HEAD request to
  https://ghcr.io/v2/acme/worker/manifests/latest: 401 Unauthorized
Warning  Failed  17s  kubelet  Error: ErrImagePull
```

## Description

`ErrImagePull` is the *immediate* failure the kubelet reports the first time it
cannot pull a container image. It is the precursor to `ImagePullBackOff`: the
first one or two attempts surface as `ErrImagePull`, and after the kubelet begins
backing off, the status flips to `ImagePullBackOff`. Catching the error at the
`ErrImagePull` stage is useful because the event still carries the raw runtime
error (HTTP status, registry response) before back-off noise sets in.

## Technologies

- kubernetes (kubelet, container runtime, image service)

## Severity

**high** — the container cannot start. The pod stays at `0/1` ready and the
workload has no healthy replica on that node until the pull succeeds.

## Common Causes

1. Missing or invalid registry credentials, returning `401 Unauthorized` or
   `403 Forbidden`.
2. A non-existent tag or repository, returning `404` / `manifest unknown`.
3. The registry host is unresolvable or unreachable (`no such host`, `i/o
   timeout`).
4. An expired or rotated pull-secret token that the ServiceAccount still
   references.
5. TLS verification failure against a registry using a private CA the node does
   not trust.

## Root Cause Analysis

When a pod is admitted, the kubelet invokes the runtime's image service to fetch
the image. The runtime performs a `HEAD`/`GET` on the registry manifest endpoint
using any supplied auth. The HTTP status of that request maps directly to the
error: `401`/`403` for auth, `404`/`manifest unknown` for a bad reference, a
transport error for networking, and an `x509`/`tls` error for certificate trust.
`ErrImagePull` is simply the kubelet's wrapper around whichever stage failed; the
underlying registry status in the event message is the real signal.

## Diagnostic Commands

```bash
# Full event chain including the raw HTTP status from the registry
kubectl describe pod <pod> -n <namespace>

# The exact image string requested
kubectl get pod <pod> -n <namespace> \
  -o jsonpath='{range .spec.containers[*]}{.image}{"\n"}{end}'

# Which pull secrets the pod resolved
kubectl get pod <pod> -n <namespace> \
  -o jsonpath='{.spec.imagePullSecrets[*].name}'

# Reproduce the pull on the node directly (read-only)
sudo crictl pull ghcr.io/acme/worker:latest
```

## Expected Results

```text
Warning  Failed  kubelet  Failed to pull image "...": ... 401 Unauthorized
Warning  Failed  kubelet  Error: ErrImagePull
```

`401`/`403` = credentials. `404` / `manifest unknown` = wrong tag or repo.
`no such host` = DNS. `x509: certificate signed by unknown authority` = registry
TLS trust. A successful `crictl pull` returning an image ID confirms the
credentials and reference are correct from that node.

## Resolution

1. For `401`/`403`, recreate the pull secret with a current token and ensure it is
   referenced by the pod's ServiceAccount:

   ```bash
   kubectl create secret docker-registry ghcr \
     --docker-server=ghcr.io --docker-username=<user> \
     --docker-password=<token> -n <namespace> --dry-run=client -o yaml \
     | kubectl apply -f -
   ```
2. For `404`, correct the image tag/repo in the Deployment and avoid `:latest`.
3. For DNS/network errors, fix node resolution or egress rules to the registry.
4. For TLS errors, install the registry's CA into the node trust store or the
   runtime's registry config.

## Validation

```bash
kubectl describe pod <pod> -n <namespace> | grep -A2 Events
# Expect: "Normal  Pulled  Successfully pulled image", then container starts.
```

## Prevention

- Use immutable digest references and validate them in CI.
- Rotate registry tokens through a controller (e.g. external-secrets) so pods
  never reference an expired secret.
- Pre-pull critical images onto nodes or use a pull-through cache.

## Related Errors

- [Kubernetes ImagePullBackOff](./kubernetes-imagepullbackoff.md)
- [Kubernetes exec format error](./kubernetes-exec-format-error.md)

## References

- [Kubernetes: Pull an Image from a Private Registry](https://kubernetes.io/docs/tasks/configure-pod-container/pull-image-private-registry/)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`kubernetes` · `pod` · `image` · `registry` · `production`
