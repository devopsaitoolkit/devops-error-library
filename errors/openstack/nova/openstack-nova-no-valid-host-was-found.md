---
title: "OpenStack Nova NoValidHost: No Valid Host Was Found"
slug: openstack-nova-no-valid-host-was-found
technologies: [openstack, nova]
severity: high
tags: [openstack, nova, scheduler, novalidhost, capacity, production]
related: [openstack-nova-instance-failed-to-spawn]
last_reviewed: 2026-06-27
---

# OpenStack Nova NoValidHost: No Valid Host Was Found

## Error Message

```text
NoValidHost: No valid host was found. There are not enough hosts available.
```

```text
nova-conductor[2147]: ERROR nova.scheduler.utils [req-...] Setting instance to ERROR state.: \
nova.exception.NoValidHost: No valid host was found. There are not enough hosts available.
```

## Description

The Nova scheduler could not find a single compute host that satisfies the
instance's requirements, so the build fails and the instance goes to `ERROR`.
The scheduler runs a chain of filters over all compute hosts; if every host is
eliminated, it raises `NoValidHost`. This is a scheduling/capacity error, not a
hypervisor error.

## Technologies

- openstack (nova-scheduler, nova-conductor, placement)

## Severity

**high** — new instances of the affected flavor/aggregate cannot be launched.
Existing workloads keep running, but capacity or scheduling is broken.

## Common Causes

1. Genuine capacity exhaustion — no host has enough free vCPU, RAM, or disk
   after overcommit ratios for the requested flavor.
2. A scheduler filter eliminates every host (e.g. `AggregateInstanceExtraSpecs`,
   availability zone, `PciPassthroughFilter`, `NUMATopologyFilter`).
3. Compute services are `down` or `disabled`, so `ComputeFilter` excludes them.
4. Placement has stale or missing inventory/allocations for the compute nodes.
5. Anti-affinity server-group policy cannot be satisfied with available hosts.

## Root Cause Analysis

Nova asks Placement for candidate resource providers, then applies the filters in
`scheduler_default_filters` to the returned hosts. Each filter removes hosts that
do not match. The scheduler logs the count of hosts remaining after each filter,
so the filter that drops the count to zero is the proximate cause. Behind that,
the reason is either real resource scarcity, a constraint (aggregate/AZ/affinity)
that no host meets, or down/disabled computes.

## Diagnostic Commands

```bash
# The instance fault with the NoValidHost reason
openstack server show <instance> -c fault -f value

# Are compute services up and enabled?
openstack compute service list --service nova-compute

# Hypervisor capacity (vCPU/RAM/disk used vs total)
openstack hypervisor list --long

# Placement resource provider inventory and usage
openstack resource provider list
openstack resource provider inventory list <rp-uuid>

# nova-scheduler filtering detail (which filter zeroed the list)
journalctl -u devstack@n-sch  # or grep the nova-scheduler log
```

## Expected Results

```text
+-------+--------------+------+---------+-------+
| Filter ComputeFilter returned 3 hosts          |
| Filter AggregateInstanceExtraSpecsFilter        |
|   returned 0 hosts                              |
+-------+--------------+------+---------+-------+
```

A filter returning `0 hosts` names the constraint to fix. In `compute service
list`, a `State: down` or `Status: disabled` host explains lost capacity.

## Resolution

1. If capacity is exhausted, add compute capacity, free resources, or use a
   smaller flavor. Review `cpu_allocation_ratio` / `ram_allocation_ratio`.
2. If a filter is at fault, fix the mismatch — correct flavor `extra_specs`,
   host-aggregate metadata, or the target availability zone.
3. Re-enable or restore down computes:
   ```bash
   openstack compute service set --enable <host> nova-compute
   ```
4. If Placement is stale, heal allocations:
   ```bash
   nova-manage placement heal_allocations --verbose
   ```

## Validation

```bash
openstack server create --flavor <flavor> --image <image> --network <net> test-vm
openstack server show test-vm -c status -f value   # Expect: ACTIVE
```

## Prevention

- Monitor hypervisor headroom and alert before pools fill.
- Keep flavor `extra_specs` and aggregate metadata in sync and under review.
- Alert on `nova-compute` services going `down`/`disabled`.
- Audit Placement inventory after host maintenance.

## Related Errors

- [OpenStack Nova Instance Failed to Spawn](./openstack-nova-instance-failed-to-spawn.md)

## References

- [Nova Scheduler documentation](https://docs.openstack.org/nova/latest/admin/scheduling.html)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`openstack` · `nova` · `scheduler` · `novalidhost` · `capacity` · `production`
