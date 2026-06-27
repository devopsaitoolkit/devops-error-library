---
title: "OpenStack Nova Exceeded Maximum Number of Retries"
slug: openstack-nova-exceeded-maximum-number-of-retries
technologies: [openstack, nova]
severity: high
tags: [openstack, nova, scheduler, retries, reschedule, production]
related: [openstack-nova-instance-failed-to-spawn, openstack-nova-no-valid-host-was-found]
last_reviewed: 2026-06-27
---

# OpenStack Nova Exceeded Maximum Number of Retries

## Error Message

```text
nova-conductor[2147]: ERROR nova.scheduler.utils [req-1b7c...] [instance: 8f2a...] \
Setting instance to ERROR state.: nova.exception.MaxRetriesExceeded: Exceeded \
maximum number of retries. Exhausted all hosts available for retrying build \
failures for instance 8f2a....
```

```text
MaxRetriesExceeded: Exceeded maximum number of retries. Exceeded max scheduling attempts 3 \
for instance 8f2a.... Last exception: internal error: process exited while connecting to monitor
```

## Description

Nova reschedules a failed build to another host up to `max_attempts`
(default 3) times. When every attempt fails — or the scheduler runs out of
candidate hosts to try — `nova-conductor` raises `MaxRetriesExceeded` and parks
the instance in `ERROR`. Crucially, the message includes the **last exception**,
which is the real failure being repeated on each host. This error is a symptom:
the underlying spawn failure is what you must actually fix.

## Technologies

- openstack (nova-conductor, nova-scheduler, nova-compute)

## Severity

**high** — instance builds fail after exhausting all retries; if a systemic
condition (bad image, broken cell, host-wide config error) is in play, every new
build hits the same wall.

## Common Causes

1. A repeating spawn failure on each candidate host (libvirt error, full disk,
   VIF plugging timeout) — same root cause as Instance Failed to Spawn.
2. Too few candidate hosts: `max_attempts` exceeds the number of hosts that pass
   filtering, so retries are exhausted immediately.
3. A bad or corrupt image/flavor that fails identically everywhere.
4. A host-aggregate or NUMA/PCI constraint that only one host meets, and that
   host keeps failing.
5. Messaging/RPC timeouts during reschedule that count as attempts.

## Root Cause Analysis

On a build failure that *is* retryable, `nova-compute` sends the instance back to
`nova-conductor`, which asks the scheduler to pick another host, decrementing the
retry budget and excluding already-tried hosts. When `num_attempts` reaches
`scheduler.max_attempts`, or the scheduler returns no new host, conductor raises
`MaxRetriesExceeded`. The `retry` dict in the request spec records each failed
host and its exception — so the **last exception** field is the proximate cause
that recurs across hosts.

## Diagnostic Commands

```bash
# Fault includes the last underlying exception
openstack server show <instance> -c fault -f value

# Compute services available to retry against
openstack compute service list --service nova-compute

# Conductor log: see each rescheduled host and its exception
journalctl -u devstack@n-cond --since "20 min ago" | grep -iE "retry|MaxRetries|reschedul"

# Current max_attempts setting
crudini --get /etc/nova/nova.conf scheduler max_attempts
```

## Expected Results

```text
fault | {'message': 'Exceeded maximum number of retries... Last exception:
         libvirtError: ... No space left on device'}

# conductor log shows the same exception on every attempted host
Retrying build on host compute-02 after failure on compute-01
Retrying build on host compute-03 after failure on compute-02
```

The repeated `Last exception` across hosts is the real bug. If only 2 hosts pass
filtering but `max_attempts = 3`, retries exhaust before a real chance.

## Resolution

1. Read the **last exception** and fix that root cause (see Instance Failed to
   Spawn for disk/libvirt/VIF fixes) — that resolves the retry exhaustion.
2. If the constraint is too tight, relax aggregate/AZ/PCI requirements so more
   hosts qualify.
3. Align `max_attempts` with real candidate count; raising it blindly only masks
   a systemic failure.
4. Remove a bad image/flavor from circulation if it fails identically everywhere.
5. Delete the `ERROR` instance and recreate after the underlying fix.

## Validation

```bash
openstack server create --flavor m1.small --image cirros --network private retry-test
openstack server show retry-test -c status -f value   # Expect: ACTIVE
# Confirm no reschedule loops in the conductor log on the new build
```

## Prevention

- Treat `MaxRetriesExceeded` as a pointer to the last exception — alert on it.
- Keep `scheduler.max_attempts` consistent with available capacity.
- Catch systemic issues (bad images, host-wide config) before they fan out.
- Monitor per-host spawn failure rates to spot a degrading compute node early.

## Related Errors

- [OpenStack Nova Instance Failed to Spawn](./openstack-nova-instance-failed-to-spawn.md)
- [OpenStack Nova NoValidHost: No Valid Host Was Found](./openstack-nova-no-valid-host-was-found.md)

## References

- [Nova scheduler configuration](https://docs.openstack.org/nova/latest/configuration/config.html)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`openstack` · `nova` · `scheduler` · `retries` · `reschedule` · `production`
