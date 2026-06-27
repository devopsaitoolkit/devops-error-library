---
title: "Kubernetes exec format error"
slug: kubernetes-exec-format-error
technologies: [kubernetes]
severity: high
tags: [kubernetes, pod, image, architecture, production]
related: [kubernetes-crashloopbackoff, kubernetes-errimagepull]
last_reviewed: 2026-06-27
---

# Kubernetes exec format error

## Error Message

```text
NAME                    READY   STATUS             RESTARTS      AGE
sync-6b8d7c9f4-2vlzr    0/1     CrashLoopBackOff   5 (38s ago)   3m
```

```text
standard_init_linux.go:228: exec user process caused: exec format error
```

```text
Warning  Failed  kubelet  Error: failed to create containerd task:
  failed to start shim: exec: "/app/server": exec format error: unknown
```

## Description

`exec format error` means the kernel could not execute the container's entrypoint
binary because its format does not match the host CPU architecture — almost always
an `arm64` image running on an `amd64` node (or vice versa). It surfaces as the
container exiting immediately on every start, so the pod lands in
`CrashLoopBackOff`. The give-away is that there is no application output at all:
the process never runs a single instruction of the app.

## Technologies

- kubernetes (kubelet, container runtime, host CPU architecture)

## Severity

**high** — the container can never start on that node; the workload has zero
healthy replicas wherever the architecture is wrong.

## Common Causes

1. A single-arch image built for `arm64` (e.g. on an Apple Silicon laptop) deployed
   onto `amd64` nodes, or the reverse.
2. A multi-arch manifest that is missing the node's architecture, so the runtime
   pulls a mismatched variant.
3. A shell script entrypoint that lacks a proper interpreter, or a statically
   compiled binary built for the wrong `GOARCH`/target triple.
4. `docker buildx` cross-build that emitted only the build-host arch.
5. A mixed-architecture node pool where pods land on nodes of the unexpected arch
   without nodeAffinity.

## Root Cause Analysis

When the runtime starts the container, it `exec`s the entrypoint. The Linux kernel
reads the ELF header (or the script shebang) and, if the binary's machine type
does not match the CPU, returns `ENOEXEC` — surfaced as `exec format error`.
Because container images are architecture-specific, a multi-arch (manifest list)
image is what lets the runtime pull the right variant per node; a single-arch
image or an incomplete manifest list will hand an `arm64` binary to an `amd64`
kernel, which cannot run it. The error therefore originates at process exec, before
any app code executes.

## Diagnostic Commands

```bash
# The exec format error in the container's previous logs
kubectl logs <pod> -n <namespace> --previous

# Architecture of the node the pod landed on
kubectl get node <node> \
  -o jsonpath='{.status.nodeInfo.architecture}{"\n"}'

# Which architectures the image manifest actually provides
crane manifest <image> | jq '.manifests[].platform'

# The pod's node assignment
kubectl get pod <pod> -n <namespace> -o wide
```

## Expected Results

```text
exec user process caused: exec format error
```

```text
{ "architecture": "amd64", "os": "linux" }   # node is amd64
[ { "architecture": "arm64", "os": "linux" } ]  # image only ships arm64
```

A mismatch between the node architecture and the image's available platforms
confirms the cause. A healthy image manifest lists every architecture the cluster
runs (`amd64`, `arm64`).

## Resolution

1. Build and push a multi-arch image covering all node architectures:

   ```bash
   docker buildx build --platform linux/amd64,linux/arm64 \
     -t registry.internal/sync:1.4.0 --push .
   ```
2. If you cannot rebuild multi-arch immediately, pin the pod to nodes whose
   architecture matches the image:

   ```yaml
   nodeSelector:
     kubernetes.io/arch: arm64
   ```
3. For Go binaries, set the correct `GOARCH`/`GOOS` for the target nodes.
4. Verify the pushed manifest is a multi-arch list before deploying.

## Validation

```bash
kubectl get pod <pod> -n <namespace> -w
# Expect: no exec format error, container starts, STATUS Running 1/1.
```

## Prevention

- Always publish multi-arch manifests when the cluster has mixed-arch nodes.
- Verify image architectures in CI (`crane manifest | jq .manifests`).
- Use `nodeSelector`/affinity on `kubernetes.io/arch` for single-arch images.
- Build release images in CI runners, not on developer laptops, to avoid arch
  surprises.

## Related Errors

- [Kubernetes CrashLoopBackOff](./kubernetes-crashloopbackoff.md)
- [Kubernetes ErrImagePull](./kubernetes-errimagepull.md)

## References

- [Docker: Multi-platform images](https://docs.docker.com/build/building/multi-platform/)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`kubernetes` · `pod` · `image` · `architecture` · `production`
