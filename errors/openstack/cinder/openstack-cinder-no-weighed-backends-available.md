---
title: "OpenStack Cinder No Weighed Backends Available"
slug: openstack-cinder-no-weighed-backends-available
technologies: [openstack, cinder]
severity: high
tags: [openstack, cinder, scheduler, capacity, volume-type, production]
related: [openstack-cinder-volume-in-error-state, openstack-placement-no-allocation-candidates]
last_reviewed: 2026-06-27
---

# OpenStack Cinder No Weighed Backends Available

## Error Message

```text
cinder-scheduler[3110]: ERROR cinder.scheduler.flows.create_volume [req-5e1d...] \
Failed to run task cinder.scheduler.flows.create_volume.ScheduleCreateVolumeTask;\
No valid backend was found. No weighed backends available
```

```text
$ openstack volume show 91a2...
| status | error                                             |
| error  | No valid backend was found. No weighed backends.. |
```

## Description

This is Cinder's scheduling-stage failure — the analogue of Nova's `NoValidHost`.
`cinder-scheduler` filters and weighs all reporting backends against the volume
request (size, volume type, extra-specs, capabilities). When every backend is
filtered out, no backend remains to be weighed, so scheduling fails before any
backend even attempts provisioning and the volume goes straight to `error`.

## Technologies

- openstack (cinder-scheduler, cinder-volume backends)

## Severity

**high** — no new volumes of the affected type/size can be provisioned; existing
volumes are unaffected, but volume creation is broken for matching requests.

## Common Causes

1. Genuine capacity exhaustion — no backend has enough free space after
   `max_over_subscription_ratio` for the requested size.
2. Volume-type extra-specs (e.g. `volume_backend_name`) match no live backend.
3. `cinder-volume` backend services are `down`, so the `CapacityFilter` /
   `AvailabilityZoneFilter` has nothing to weigh.
4. Backends are reporting stale or zero capacity (driver capability-report bug).
5. Requested availability zone has no backend.

## Root Cause Analysis

Each `cinder-volume` backend periodically reports capabilities/capacity to the
scheduler. On a create request, `cinder-scheduler` runs the filters in
`scheduler_default_filters` (Availability, Capacity, CapabilitiesFilter, etc.)
over those reports, then weighs survivors. If a filter eliminates all backends —
because none match the type's `volume_backend_name`, none have free space, or
none are reporting at all — the weighing set is empty and the task raises
`No weighed backends available`. The scheduler debug log shows which filter
removed the last backend.

## Diagnostic Commands

```bash
# Are backend services up and which AZ/host?
openstack volume service list

# The volume type and its extra-specs that must be matched
openstack volume type show <type> -c properties

# Scheduler messages for the failed request
openstack volume message list --resource-uuid <volume-id>

# Scheduler filtering detail
journalctl -u devstack@c-sch --since "15 min ago" | grep -iE "filter|weighed|capacity"

# Backend free capacity (LVM example)
sudo vgs
```

## Expected Results

```text
# volume service list
| Binary           | Host              | Status  | State |
| cinder-volume    | host@lvm-1        | enabled | down  |   <- backend down

# scheduler log
Filter CapacityFilter returned 0 hosts
```

A backend `down`, a `CapacityFilter returned 0 hosts` line, or a type whose
`volume_backend_name` matches nothing live identifies the cause.

## Resolution

1. **Capacity:** add/free backend storage, or request a smaller volume. Review
   `max_over_subscription_ratio` and `reserved_percentage`.
2. **Type mismatch:** correct the volume type's `volume_backend_name` /
   extra-specs to match a live backend, or point requests at the right type.
3. **Down backend:** restart `cinder-volume` and confirm it reports `up`:
   ```bash
   openstack volume service list
   ```
4. **Stale capacity:** restart the offending backend so it re-reports capabilities.

## Validation

```bash
openstack volume create --size 1 --type <type> sched-test
openstack volume show sched-test -c status -f value   # Expect: available
openstack volume delete sched-test
```

## Prevention

- Alert on backend free capacity and on any `cinder-volume` going `down`.
- Keep volume types' extra-specs in sync with deployed backends.
- Review over-subscription ratios so reported capacity is honest.
- Audit AZ-to-backend mapping when adding/removing storage hosts.

## Related Errors

- [OpenStack Cinder Volume in Error State](./openstack-cinder-volume-in-error-state.md)
- [OpenStack Placement No Allocation Candidates](../placement/openstack-placement-no-allocation-candidates.md)

## References

- [Cinder scheduler filters and weighers](https://docs.openstack.org/cinder/latest/configuration/block-storage/scheduler-filters.html)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`openstack` · `cinder` · `scheduler` · `capacity` · `volume-type` · `production`
