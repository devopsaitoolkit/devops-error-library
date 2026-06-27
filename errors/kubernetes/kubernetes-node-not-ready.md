---
title: "Kubernetes Node NotReady"
slug: kubernetes-node-not-ready
technologies: [kubernetes]
severity: critical
tags: [kubernetes, node, kubelet, networking, production]
related: [kubernetes-failedscheduling, kubernetes-evicted-pod]
last_reviewed: 2026-06-27
---

# Kubernetes Node NotReady

## Error Message

```text
NAME              STATUS     ROLES    AGE    VERSION
ip-10-0-3-42      NotReady   <none>   83d    v1.29.4
```

```text
Conditions:
  Type             Status    Reason                       Message
  Ready            False     KubeletNotReady              container runtime
                                                          network not ready:
                                                          NetworkPluginNotReady
  MemoryPressure   Unknown   NodeStatusUnknown            Kubelet stopped posting
                                                          node status.
```

## Description

A node in `NotReady` state has failed its readiness condition: the kubelet either
stopped posting status to the API server (`Unknown`, the node controller marks it
after `node-monitor-grace-period`) or is reporting an unhealthy subsystem
(`False`, e.g. runtime or CNI not ready). Pods on a `NotReady` node are not
scheduled to it, and after the eviction timeout their pods are marked for deletion
and rescheduled elsewhere — so a `NotReady` node both loses new placement and
drains its existing workload.

## Technologies

- kubernetes (kubelet, node controller, container runtime, CNI)

## Severity

**critical** — losing a node removes capacity and, if many nodes go NotReady
together (a control-plane or network-wide fault), can cascade into a cluster-wide
outage as pods reschedule onto shrinking capacity.

## Common Causes

1. The kubelet process is stopped, crashed, or cannot reach the API server
   (status goes `Unknown`).
2. The container runtime (containerd/CRI-O) is down or unresponsive.
3. The CNI plugin is not ready, so `Ready` stays `False` with
   `NetworkPluginNotReady`.
4. Node resource exhaustion — disk full (`/var/lib/kubelet`), out of memory, or
   PID exhaustion — wedges the kubelet.
5. Network partition / expired kubelet certificate breaking the node-to-API
   heartbeat.

## Root Cause Analysis

The kubelet posts a node `Lease` heartbeat and a `NodeStatus` to the API server.
The node controller watches these: if the lease is not renewed within the
monitor-grace-period, it sets the `Ready` condition to `Unknown`. Separately, the
kubelet itself sets `Ready=False` when a local subsystem (runtime, CNI, disk) is
unhealthy, attaching a `Reason`/`Message`. So `Unknown` means "we lost contact
with the kubelet" (look at the node/host and connectivity), while `False` with a
specific reason means "the kubelet is alive but reporting a broken subsystem"
(look at that subsystem's logs).

## Diagnostic Commands

```bash
# Which condition and reason flipped the node
kubectl describe node <node> | grep -A8 Conditions

# Kubelet health and recent errors on the node
systemctl status kubelet --no-pager
journalctl -u kubelet -n 200 --no-pager

# Container runtime health on the node
sudo crictl info | grep -i ready

# Node resource pressure
df -h /var/lib/kubelet && free -m
```

## Expected Results

```text
Ready   False   KubeletNotReady   container runtime network not ready:
                                   NetworkPluginNotReady
```

or, for a lost heartbeat:

```text
Ready   Unknown   NodeStatusUnknown   Kubelet stopped posting node status.
```

A healthy node shows `Ready  True  KubeletReady  kubelet is posting ready
status`. `Unknown` directs you to host/network/kubelet-process issues; `False`
with a reason directs you to that named subsystem.

## Resolution

1. If the kubelet is down, restart it and inspect why it stopped:
   `sudo systemctl restart kubelet` then read `journalctl -u kubelet`.
2. If the runtime is down, restart containerd/CRI-O and confirm `crictl info`
   reports ready.
3. If `NetworkPluginNotReady`, restore the CNI daemonset pod on the node.
4. If the node is out of disk/PIDs, reclaim space (image GC, log rotation) or
   increase limits; then the kubelet recovers.
5. If the node is unrecoverable, cordon and drain it and replace it:

   ```bash
   kubectl cordon <node>
   kubectl drain <node> --ignore-daemonsets --delete-emptydir-data
   ```

## Validation

```bash
kubectl get node <node> -w
# Expect: STATUS returns to Ready; new pods schedule onto it again.
```

## Prevention

- Alert on node `Ready` transitions and on kubelet lease staleness.
- Monitor node disk, memory, and PID usage with pre-exhaustion alerts.
- Automate certificate rotation so kubelet certs do not expire.
- Spread workloads so a single NotReady node cannot take out a service.

## Related Errors

- [Kubernetes FailedScheduling](./kubernetes-failedscheduling.md)
- [Kubernetes Evicted Pod](./kubernetes-evicted-pod.md)

## References

- [Kubernetes: Node Status](https://kubernetes.io/docs/concepts/architecture/nodes/#condition)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`kubernetes` · `node` · `kubelet` · `networking` · `production`
