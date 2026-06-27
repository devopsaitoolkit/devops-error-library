---
title: "OpenStack Neutron Port Binding Failed"
slug: openstack-neutron-port-binding-failed
technologies: [openstack, neutron]
severity: high
tags: [openstack, neutron, ml2, port-binding, ovs, production]
related: [openstack-neutron-ip-address-exhaustion, openstack-nova-instance-failed-to-spawn]
last_reviewed: 2026-06-27
---

# OpenStack Neutron Port Binding Failed

## Error Message

```text
neutron-server[2980]: ERROR neutron.plugins.ml2.managers [req-4b8e...] \
Failed to bind port 6f1a9c2d-... on host compute-03 for vnic_type normal using \
segments [{'id': 'a1...', 'network_type': 'vxlan', 'segmentation_id': 1042, \
'physical_network': None}]
```

```text
$ openstack port show 6f1a9c2d-...
| binding_vif_type | binding_failed |
```

## Description

`binding_failed` means the Neutron ML2 plugin could not find a mechanism driver
(OVS, Linuxbridge, SR-IOV, OVN) on the target host that is able to bind the port
to one of the network's segments. Without a successful bind, the port has no
working VIF type, so Nova cannot wire the instance's interface and the build
fails with a VIF-creation error. The bind happens at instance-launch time on the
chosen compute host.

## Technologies

- openstack (neutron-server, ML2 mechanism drivers, L2 agent on compute)

## Severity

**high** — instances scheduled to the affected host cannot get networking and
fail to spawn; if the L2 agent is down fleet-wide, all builds fail to bind.

## Common Causes

1. The L2 agent on the target host is `down` or not reporting, so its mechanism
   driver is skipped.
2. `physical_network` / bridge-mapping mismatch — the host has no
   `bridge_mappings` entry for the segment's physical network (flat/VLAN).
3. The network type is not enabled in `mechanism_drivers` / `type_drivers`, or
   the host's agent does not support it.
4. `vnic_type` mismatch — e.g. `direct` (SR-IOV) requested but no SR-IOV agent /
   no free VF on the host.
5. MTU or segment configuration the driver rejects.

## Root Cause Analysis

When a port is bound to a host, ML2 iterates its configured `mechanism_drivers`
and asks each whether it can bind the port for the host's `vnic_type` and the
network's segments. A driver can bind only if its corresponding agent is alive on
that host and its mappings cover the segment. If no driver succeeds, ML2 sets
`binding:vif_type = binding_failed` and logs the segment details it tried. The
log line plus the agent state reveal whether it is a dead agent, a missing
bridge mapping, or an unsupported segment/vnic_type.

## Diagnostic Commands

```bash
# Is the port actually in binding_failed?
openstack port show <port-id> -c binding_vif_type -c binding_host_id

# Are L2 agents on the target host alive?
openstack network agent list --host compute-03

# The network's segment (type / physical_network / segmentation_id)
openstack network show <network-id> -c provider:network_type \
  -c provider:physical_network -c provider:segmentation_id

# neutron-server binding log
journalctl -u devstack@q-svc --since "10 min ago" | grep -iE "bind|binding_failed"

# On the compute host: bridge mappings the OVS agent advertises
sudo ovs-vsctl show
```

## Expected Results

```text
# network agent list
| Agent Type         | Host       | Alive | State |
| Open vSwitch agent | compute-03 | XXX   | UP    |   <- 'XXX' / dead agent

# server log
Refusing to bind port ... no mechanism driver could bind for physical_network 'physnet1'
```

A dead agent, or a `physical_network` with no matching `bridge_mappings`, names
the cause. A healthy port shows a real `binding_vif_type` like `ovs`.

## Resolution

1. **Dead agent:** restart and confirm the L2 agent reports `UP`:
   ```bash
   openstack network agent list --host <host>
   ```
2. **Bridge mapping:** add the missing `bridge_mappings` (and OVS bridge) for the
   segment's `physical_network` on the host, then restart the agent.
3. **Type/driver:** enable the network type in `type_drivers` and the matching
   driver in `mechanism_drivers`.
4. **SR-IOV:** ensure the SR-IOV agent runs and free VFs exist for `vnic_type
   direct`.
5. Delete the `binding_failed` port (or the ERROR instance) and re-create.

## Validation

```bash
openstack port create --network <network> bind-test
openstack port show bind-test -c binding_vif_type -f value   # Expect: ovs (not binding_failed)
openstack port delete bind-test
```

## Prevention

- Alert on Neutron L2 agents going `down`.
- Manage `bridge_mappings` consistently across hosts via configuration mgmt.
- Validate `type_drivers`/`mechanism_drivers` after upgrades.
- Track SR-IOV VF availability where `direct` ports are used.

## Related Errors

- [OpenStack Neutron IP Address Exhaustion](./openstack-neutron-ip-address-exhaustion.md)
- [OpenStack Nova Instance Failed to Spawn](../nova/openstack-nova-instance-failed-to-spawn.md)

## References

- [Neutron ML2 plug-in configuration](https://docs.openstack.org/neutron/latest/admin/config-ml2.html)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`openstack` · `neutron` · `ml2` · `port-binding` · `ovs` · `production`
