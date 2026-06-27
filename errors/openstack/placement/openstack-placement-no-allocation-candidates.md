---
title: "OpenStack Placement No Allocation Candidates"
slug: openstack-placement-no-allocation-candidates
technologies: [openstack, placement]
severity: high
tags: [openstack, placement, nova, inventory, allocations, production]
related: [openstack-nova-no-valid-host-was-found, openstack-cinder-no-weighed-backends-available]
last_reviewed: 2026-06-27
---

# OpenStack Placement No Allocation Candidates

## Error Message

```text
nova-scheduler[2210]: DEBUG nova.scheduler.client.report [req-6d2c...] \
Got no allocation candidates from the placement API. This could be due to insufficient \
resources or a temporary occurrence as compute nodes start up.
```

```text
$ openstack allocation candidate list --resource VCPU=2 --resource MEMORY_MB=2048
No allocation candidates found.
```

## Description

Placement tracks the inventory of every resource provider (compute nodes, and
their nested PCI/PGPU providers) and the allocations consumed against it. The
Nova scheduler asks Placement for *allocation candidates* — providers that can
satisfy the requested resource classes and traits — before it ever runs filters.
When Placement returns an empty set, the scheduler has nothing to filter and the
build fails with `NoValidHost`. This error means the shortfall is at the
inventory/allocation layer, not in Nova's filters.

## Technologies

- openstack (placement, nova-scheduler, nova-compute resource tracker)

## Severity

**high** — no host can be selected for instances needing the requested resources;
new builds of the affected shape fail until inventory/allocations are corrected.

## Common Causes

1. Genuine resource exhaustion — no provider has free `VCPU`, `MEMORY_MB`, or
   `DISK_GB` after allocation ratios and `reserved` amounts.
2. Required traits or resource classes (e.g. `CUSTOM_*`, `VGPU`, PCI) exist on no
   provider, or the flavor requests a trait nothing advertises.
3. Stale allocations from deleted instances pinning capacity ("leaked"
   allocations).
4. The compute's resource tracker has not (re)reported inventory after restart or
   upgrade, so providers show zero/missing inventory.
5. `reserved` set equal to `total`, leaving no allocatable capacity.

## Root Cause Analysis

Each `nova-compute` resource tracker writes its node's inventory (totals,
`reserved`, `allocation_ratio`) and traits into Placement. On a build, the
scheduler issues a `GET /allocation_candidates` query for the flavor's resources
and required traits. Placement returns only providers whose
`total × allocation_ratio − reserved − used ≥ requested` for every class *and*
that carry all required traits. An empty response means either no provider has
the headroom, or none advertise a required trait/class — frequently because
allocations leaked or inventory was never reported. Comparing inventory against
usage per provider isolates which it is.

## Diagnostic Commands

```bash
# Can Placement satisfy the shape at all?
openstack allocation candidate list --resource VCPU=2 --resource MEMORY_MB=2048

# Providers and their inventory/usage
openstack resource provider list
openstack resource provider inventory list <rp-uuid>
openstack resource provider usage show <rp-uuid>

# Traits a provider advertises (for trait-based requests)
openstack resource provider trait list <rp-uuid>

# Find leaked allocations vs real instances
nova-manage placement audit --verbose
```

## Expected Results

```text
# inventory list
| resource_class | total | reserved | allocation_ratio | used  |
| VCPU           | 64    | 0        | 16.0             | 1024  |  <- fully consumed
| MEMORY_MB      | 128k  | 512      | 1.5              | 191k  |

# audit
Allocation for consumer <uuid> has no matching instance (leaked)
```

`used` at the effective cap, a missing required trait, or leaked allocations from
the audit each explain the empty candidate set.

## Resolution

1. **Real exhaustion:** add capacity, free resources, or adjust
   `allocation_ratio` / `reserved` in nova.conf so honest headroom exists.
2. **Leaked allocations:** heal them so capacity frees up:
   ```bash
   nova-manage placement heal_allocations --verbose
   ```
3. **Missing inventory:** restart `nova-compute` so the resource tracker
   re-reports; confirm the provider then lists inventory.
4. **Trait/class mismatch:** ensure providers advertise the trait the flavor
   requires, or fix the flavor's `resources:`/`trait:` extra-specs.

## Validation

```bash
openstack allocation candidate list --resource VCPU=2 --resource MEMORY_MB=2048
# Expect: one or more candidate rows returned
openstack server create --flavor m1.small --image cirros --network private placement-test
openstack server show placement-test -c status -f value   # Expect: ACTIVE
```

## Prevention

- Monitor per-provider headroom in Placement, not just hypervisor stats.
- Run `nova-manage placement audit` periodically to catch leaked allocations.
- Validate inventory reporting after compute restarts and upgrades.
- Keep flavor traits/resource-class requests aligned with what providers advertise.

## Related Errors

- [OpenStack Nova NoValidHost: No Valid Host Was Found](../nova/openstack-nova-no-valid-host-was-found.md)
- [OpenStack Cinder No Weighed Backends Available](../cinder/openstack-cinder-no-weighed-backends-available.md)

## References

- [Placement allocation candidates](https://docs.openstack.org/placement/latest/user/index.html)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`openstack` · `placement` · `nova` · `inventory` · `allocations` · `production`
