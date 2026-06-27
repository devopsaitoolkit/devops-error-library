---
title: "Kubernetes FailedCreatePodSandBox"
slug: kubernetes-failedcreatepodsandbox
technologies: [kubernetes]
severity: high
tags: [kubernetes, cni, networking, runtime, production]
related: [kubernetes-node-not-ready, kubernetes-mountvolume-setup-failed]
last_reviewed: 2026-06-27
---

# Kubernetes FailedCreatePodSandBox

## Error Message

```text
Warning  FailedCreatePodSandBox  kubelet
  Failed to create pod sandbox: rpc error: code = Unknown desc = failed to
  setup network for sandbox "9b1c...e4": plugin type="calico" failed (add):
  error getting ClusterInformation: connection is unauthorized:
  Unauthorized
```

```text
Warning  FailedCreatePodSandBox  kubelet
  Failed to create pod sandbox: rpc error: code = Unknown desc = failed to
  reserve sandbox name "web_prod_...": name is reserved
```

## Description

`FailedCreatePodSandBox` is reported by the kubelet when the container runtime
cannot create the pod's *sandbox* — the pause container plus its network and IPC
namespaces — which must exist before any application container starts. The most
common root is the CNI plugin failing to allocate a network for the sandbox, but
it can also be a runtime/socket problem or IP-address-management (IPAM)
exhaustion. The pod is stuck in `ContainerCreating`.

## Technologies

- kubernetes (kubelet, container runtime, CNI plugin)

## Severity

**high** — no container in the pod can start because the sandbox itself fails.
When the cause is cluster-wide (a broken CNI), it blocks scheduling across many
nodes at once.

## Common Causes

1. CNI plugin misconfiguration or an unhealthy CNI control plane (Calico, Cilium,
   AWS VPC CNI) returning an add error.
2. IP exhaustion — the node's pod CIDR or the IPAM pool has no free addresses.
3. The CNI binary or config (`/etc/cni/net.d`, `/opt/cni/bin`) is missing or the
   plugin daemonset is not running on the node.
4. Container runtime issues: a stale sandbox, a full disk, or a dead
   containerd/CRI-O socket.
5. RBAC/credential problems so the CNI cannot read cluster state ("Unauthorized").

## Root Cause Analysis

When the kubelet decides to run a pod, it asks the CRI runtime to create a
PodSandbox. The runtime starts the pause container and then invokes the CNI `ADD`
operation, which calls the configured plugin to attach the sandbox to the pod
network and assign an IP via IPAM. If the plugin binary is missing, its config is
invalid, it cannot reach its datastore, or IPAM has no free IP, the `ADD` fails
and the runtime returns the error to the kubelet as `FailedCreatePodSandBox`. The
plugin name in the message (`type="calico"`, `cilium`, `aws-cni`) and the verb
(`add`) localize the fault to the CNI.

## Diagnostic Commands

```bash
# The sandbox failure with the CNI plugin and verb
kubectl describe pod <pod> -n <namespace>

# Is the CNI daemonset healthy on this node?
kubectl get pods -n kube-system -o wide | grep -E 'calico|cilium|aws-node'

# kubelet/runtime log lines around sandbox creation on the node
journalctl -u kubelet -n 200 --no-pager | grep -i sandbox

# CNI config and binaries present on the node
ls -l /etc/cni/net.d /opt/cni/bin
```

## Expected Results

```text
Warning  FailedCreatePodSandBox  kubelet  ... plugin type="calico" failed (add):
  error getting ClusterInformation: connection is unauthorized: Unauthorized
```

A `plugin ... failed (add)` line points at the CNI. `failed to find plugin
"xxx" in path` means missing binaries. An IPAM message like `no IP addresses
available in range` means address exhaustion. Healthy nodes show no
`FailedCreatePodSandBox` events and CNI pods all `Running`.

## Resolution

1. Restore the CNI: ensure its daemonset is healthy on the node and restart the
   agent pod if it is crashlooping.
2. For IPAM exhaustion, enlarge the pod CIDR / IP pool, or reduce pods-per-node;
   for AWS VPC CNI, ensure enough free ENIs/IPs in the subnet.
3. For missing CNI files, reinstall the plugin so `/opt/cni/bin` and
   `/etc/cni/net.d` are populated, then the kubelet retries automatically.
4. For runtime problems, free disk on the node and restart containerd/CRI-O if its
   socket is unresponsive.

## Validation

```bash
kubectl get pod <pod> -n <namespace> -w
# Expect: leaves ContainerCreating, gets a Pod IP, reaches Running 1/1.
kubectl get pod <pod> -n <namespace> -o jsonpath='{.status.podIP}'
```

## Prevention

- Monitor CNI agent health and IPAM free-IP counts; alert before exhaustion.
- Keep CNI version compatible with the Kubernetes version during upgrades.
- Alert on node disk pressure, which silently breaks sandbox creation.

## Related Errors

- [Kubernetes Node NotReady](./kubernetes-node-not-ready.md)
- [Kubernetes MountVolume SetUp failed](./kubernetes-mountvolume-setup-failed.md)

## References

- [Kubernetes: Network Plugins](https://kubernetes.io/docs/concepts/extend-kubernetes/compute-storage-net/network-plugins/)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`kubernetes` · `cni` · `networking` · `runtime` · `production`
