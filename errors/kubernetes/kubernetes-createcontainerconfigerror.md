---
title: "Kubernetes CreateContainerConfigError"
slug: kubernetes-createcontainerconfigerror
technologies: [kubernetes]
severity: high
tags: [kubernetes, pod, configmap, secret, production]
related: [kubernetes-crashloopbackoff, kubernetes-mountvolume-setup-failed]
last_reviewed: 2026-06-27
---

# Kubernetes CreateContainerConfigError

## Error Message

```text
NAME                       READY   STATUS                       RESTARTS   AGE
billing-5c9d7f6b8b-r4tlz   0/1     CreateContainerConfigError   0          47s
```

```text
Warning  Failed  12s (x5 over 47s)  kubelet
  Error: configmap "billing-config" not found
```

```text
Warning  Failed  9s (x4 over 41s)  kubelet
  Error: couldn't find key DATABASE_URL in Secret prod/billing-secrets
```

## Description

`CreateContainerConfigError` means the kubelet successfully pulled the image and
created the pod sandbox, but it cannot assemble the container's configuration
*before* starting it. This almost always comes from a referenced ConfigMap or
Secret — or a specific key within one — that does not exist. Unlike
`CrashLoopBackOff`, the container never even starts, so there are no application
logs to read; the answer is entirely in the pod events.

## Technologies

- kubernetes (kubelet)

## Severity

**high** — the container cannot be created, so the pod is `0/1` and the workload
has no healthy replica until the missing config object exists.

## Common Causes

1. A ConfigMap or Secret named in `envFrom`, `env.valueFrom`, or a volume does not
   exist in the pod's namespace.
2. The object exists but the specific `key` referenced is absent.
3. The ConfigMap/Secret is in a different namespace than the pod (these references
   are namespace-local).
4. A typo in the ConfigMap/Secret name or key.
5. The object is created *after* the pod (ordering issue in a fresh deploy or a
   GitOps sync race).

## Root Cause Analysis

Before launching a container, the kubelet resolves every `valueFrom`,
`secretKeyRef`, `configMapKeyRef`, and projected volume into concrete environment
variables and files. If any referenced object or key is missing, the kubelet
cannot build the container's config and aborts container creation with
`CreateContainerConfigError`, retrying on the standard back-off. Because this
happens at config-assembly time — earlier than process start — the failure is
deterministic and the event names the exact missing object or key.

## Diagnostic Commands

```bash
# The event naming the missing ConfigMap/Secret or key
kubectl describe pod <pod> -n <namespace>

# Which ConfigMaps/Secrets the pod references
kubectl get pod <pod> -n <namespace> -o jsonpath='
{range .spec.containers[*].envFrom[*]}{.configMapRef.name}{.secretRef.name}{"\n"}{end}'

# Confirm whether the named object exists in this namespace
kubectl get configmap,secret -n <namespace>

# Inspect the keys present in the referenced object
kubectl get configmap billing-config -n <namespace> -o jsonpath='{.data}'
```

## Expected Results

```text
Error: configmap "billing-config" not found
```

or

```text
Error: couldn't find key DATABASE_URL in Secret prod/billing-secrets
```

The first form means the whole object is missing; the second means the object
exists but the key does not. A healthy pod skips this error and proceeds to
`ContainerCreating` → `Running`.

## Resolution

1. Create the missing object in the *same namespace* as the pod:

   ```bash
   kubectl create configmap billing-config \
     --from-literal=LOG_LEVEL=info -n <namespace>
   ```
2. If only a key is missing, add it to the existing object:

   ```bash
   kubectl create secret generic billing-secrets \
     --from-literal=DATABASE_URL='postgres://...' \
     -n <namespace> --dry-run=client -o yaml | kubectl apply -f -
   ```
3. Fix any name/key typo in the pod spec to match the actual object.
4. Ensure deploy ordering so ConfigMaps/Secrets are applied before the workload
   (Helm hooks or GitOps sync waves).

## Validation

```bash
kubectl get pod <pod> -n <namespace> -w
# Expect: status leaves CreateContainerConfigError and reaches Running 1/1.
```

## Prevention

- Validate that every referenced ConfigMap/Secret/key exists in CI (kubeconform +
  a custom check, or `kubectl --dry-run=server`).
- Use `optional: true` on `valueFrom` references that are genuinely optional.
- Apply config objects in an earlier sync wave than the workloads that need them.

## Related Errors

- [Kubernetes CrashLoopBackOff](./kubernetes-crashloopbackoff.md)
- [Kubernetes MountVolume SetUp failed](./kubernetes-mountvolume-setup-failed.md)

## References

- [Kubernetes: Configure a Pod to Use a ConfigMap](https://kubernetes.io/docs/tasks/configure-pod-container/configure-pod-configmap/)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`kubernetes` · `pod` · `configmap` · `secret` · `production`
