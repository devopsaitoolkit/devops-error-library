---
title: "OpenStack Nova Build of Instance Aborted"
slug: openstack-nova-build-of-instance-aborted
technologies: [openstack, nova]
severity: high
tags: [openstack, nova, build, conductor, rescheduling, production]
related: [openstack-nova-instance-failed-to-spawn, openstack-nova-exceeded-maximum-number-of-retries]
last_reviewed: 2026-06-27
---

# OpenStack Nova Build of Instance Aborted

## Error Message

```text
nova-compute[1843]: ERROR nova.compute.manager [req-9a4f...] [instance: 4d8e...] \
Build of instance 4d8e... aborted: Volume 6c1b... did not finish being created \
even after we waited 187 seconds or 61 attempts. And its status is downloading.
```

```text
BuildAbortException: Build of instance 4d8e... aborted: Failed to allocate the \
network(s), not rescheduling.
```

## Description

`BuildAbortException` is raised by `nova-compute` when a build hits a condition
that there is no point retrying — so Nova deliberately stops and does **not**
reschedule to another host. This distinguishes it from a transient spawn failure
that triggers a retry. The most common triggers are a dependent resource that
never became ready (a Cinder volume stuck in `downloading`/`creating`, or a
Neutron network that could not be allocated). The instance goes to `ERROR`.

## Technologies

- openstack (nova-compute, nova-conductor, cinder, neutron)

## Severity

**high** — the instance build fails permanently with no automatic retry; if the
dependency (Cinder/Neutron) is broken, all similar builds will abort the same way.

## Common Causes

1. Boot-from-volume where the Cinder volume never reaches `available` within the
   timeout — backend slow, image conversion stuck, or `cinder-volume` down.
2. `Failed to allocate the network(s)` — Neutron could not create or bind ports.
3. Block Device Mapping is invalid (bad volume/snapshot/image reference).
4. The maximum number of build retries was exhausted, so Nova aborts.
5. Port quota or IP exhaustion in the requested network.

## Root Cause Analysis

During `_build_resources`, `nova-compute` waits for block devices and networks
before calling `spawn()`. It polls Cinder until the volume is `available` (up to
`block_device_allocate_retries` × interval) and waits on Neutron for port
allocation. If those waits time out or return a hard error, Nova raises
`BuildAbortException` rather than rescheduling, because retrying on another host
would not fix an unavailable volume or a network it cannot allocate. The fault
text names the exact unmet dependency and how long Nova waited.

## Diagnostic Commands

```bash
# The abort reason recorded on the instance
openstack server show <instance> -c fault -f value

# If boot-from-volume: is the volume stuck?
openstack volume show <volume-id> -c status -f value

# cinder-volume service health
openstack volume service list

# Neutron port allocation for the instance
openstack port list --device-id <instance-id>

# nova-compute build log
journalctl -u devstack@n-cpu --since "15 min ago" | grep -iE "aborted|build of instance"
```

## Expected Results

```text
fault | {'message': 'Build of instance ... aborted: Volume ... did not finish
         being created even after we waited 187 seconds...'}

# volume show
status | downloading        # stuck — never reached 'available'
```

A volume stuck in `downloading`/`creating`, an empty `port list`, or a
`Failed to allocate the network(s)` line pinpoints the unmet dependency.

## Resolution

1. **Stuck volume:** fix the Cinder backend (see the Cinder error in Related),
   then recreate. Increase `block_device_allocate_retries` if the backend is
   merely slow under load.
2. **Network allocation:** resolve the Neutron failure (port binding, quota, IP
   exhaustion) before retrying.
3. **Bad BDM:** correct the volume/snapshot/image references in the request.
4. Delete the `ERROR` instance and re-create; aborted builds are not retried.

## Validation

```bash
openstack server create --flavor m1.small --image cirros \
  --boot-from-volume 10 --network private build-test
openstack server show build-test -c status -f value   # Expect: ACTIVE
```

## Prevention

- Monitor Cinder backend latency and `cinder-volume` health.
- Alert on Neutron port and IP quota approaching exhaustion.
- Validate volume/image references before bulk launches.
- Keep `block_device_allocate_retries` realistic for your backend speed.

## Related Errors

- [OpenStack Nova Instance Failed to Spawn](./openstack-nova-instance-failed-to-spawn.md)
- [OpenStack Cinder Volume in Error State](../cinder/openstack-cinder-volume-in-error-state.md)
- [OpenStack Neutron Port Binding Failed](../neutron/openstack-neutron-port-binding-failed.md)

## References

- [Nova compute troubleshooting](https://docs.openstack.org/nova/latest/admin/support-compute.html)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`openstack` · `nova` · `build` · `conductor` · `rescheduling` · `production`
