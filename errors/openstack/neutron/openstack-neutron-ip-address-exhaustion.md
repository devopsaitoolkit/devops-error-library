---
title: "OpenStack Neutron IP Address Exhaustion"
slug: openstack-neutron-ip-address-exhaustion
technologies: [openstack, neutron]
severity: high
tags: [openstack, neutron, ipam, subnet, exhaustion, production]
related: [openstack-neutron-port-binding-failed, openstack-nova-build-of-instance-aborted]
last_reviewed: 2026-06-27
---

# OpenStack Neutron IP Address Exhaustion

## Error Message

```text
neutron-server[2980]: ERROR neutron.api.v2.resource [req-8c3f...] create failed: \
neutron_lib.exceptions.IpAddressGenerationFailure: No more IP addresses available \
on network 3a9d2f1c-....
```

```text
$ openstack port create --network private p1
IpAddressGenerationFailureClient: No more IP addresses available on network 3a9d2f1c-....
```

## Description

`IpAddressGenerationFailure` is raised by Neutron's IPAM when a subnet's
allocation pool has no free addresses left to assign to a new port. Because every
instance NIC, router interface, DHCP agent, and floating-IP needs an address,
exhaustion blocks new ports — which in turn makes Nova builds fail with
`Failed to allocate the network(s)`. The pool, not the whole network, is the unit
that runs dry.

## Technologies

- openstack (neutron-server, IPAM, subnet allocation pools)

## Severity

**high** — no new ports can be created on the affected subnet, so new instances
on that network fail to launch; existing instances keep their addresses.

## Common Causes

1. The subnet's allocation pool is genuinely full (CIDR too small for the number
   of ports).
2. Leaked/orphaned ports holding addresses — DHCP, router, or instance ports left
   behind after failed deletes.
3. Allocation pool narrower than the CIDR (large gateway/reserved ranges).
4. A single shared subnet used by far more instances than planned.
5. Floating-IP pool on an external network exhausted.

## Root Cause Analysis

When a port is created, Neutron IPAM picks the next free address from the
subnet's `allocation_pools`. The pool size is `(pool end - pool start + 1)` minus
addresses already allocated (instances, routers, DHCP). When allocated equals
available, IPAM raises `IpAddressGenerationFailure`. Counting ports against pool
size shows whether the pool is truly full or whether orphaned ports are squatting
on addresses that should have been freed.

## Diagnostic Commands

```bash
# Subnet CIDR and its allocation pool boundaries
openstack subnet show <subnet-id> -c cidr -c allocation_pools -c gateway_ip

# How many ports already exist on the network (allocated addresses)
openstack port list --network <network-id> -f value -c ID | wc -l

# Look for orphaned ports (no device / DOWN) holding IPs
openstack port list --network <network-id> --long

# neutron-server IPAM error
journalctl -u devstack@q-svc --since "10 min ago" | grep -i IpAddressGeneration
```

## Expected Results

```text
# subnet show
cidr             | 192.168.10.0/27           # only 30 usable addresses
allocation_pools | 192.168.10.2-192.168.10.30

# port count
30                                            # pool fully consumed
```

If the port count matches the pool size the subnet is truly full; a pile of
`DOWN` ports with no `device_id` indicates leaked allocations.

## Resolution

1. **Reclaim leaks:** delete orphaned ports that hold addresses but no device:
   ```bash
   openstack port delete <orphan-port-id>
   ```
2. **Grow the pool:** if the CIDR allows, widen `allocation_pools`; otherwise add
   another subnet to the network:
   ```bash
   openstack subnet create --network <network> --subnet-range 192.168.11.0/24 extra
   ```
3. **Right-size new networks** with a CIDR that fits projected instance counts.
4. For floating IPs, extend the external subnet's pool or add an external subnet.

## Validation

```bash
openstack port create --network <network> ip-test
openstack port show ip-test -c fixed_ips -f value   # Expect an assigned address
openstack port delete ip-test
```

## Prevention

- Alert when a subnet's free-address ratio drops below a threshold.
- Periodically audit and clean orphaned `DOWN` ports.
- Size subnet CIDRs for growth; prefer multiple subnets over one large shared one.
- Track floating-IP pool utilization on external networks.

## Related Errors

- [OpenStack Neutron Port Binding Failed](./openstack-neutron-port-binding-failed.md)
- [OpenStack Nova Build of Instance Aborted](../nova/openstack-nova-build-of-instance-aborted.md)

## References

- [Neutron subnet and IPAM management](https://docs.openstack.org/neutron/latest/admin/config-ipam.html)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`openstack` · `neutron` · `ipam` · `subnet` · `exhaustion` · `production`
