---
title: "OpenStack Nova Instance Failed to Spawn"
slug: openstack-nova-instance-failed-to-spawn
technologies: [openstack, nova]
severity: high
tags: [openstack, nova, libvirt, spawn, hypervisor, production]
related: [openstack-nova-no-valid-host-was-found, openstack-nova-build-of-instance-aborted]
last_reviewed: 2026-06-27
---

# OpenStack Nova Instance Failed to Spawn

## Error Message

```text
nova-compute[1843]: ERROR nova.compute.manager [req-3f1c9a2e-...] [instance: 7b2e4c1a-...] \
Instance failed to spawn: libvirt.libvirtError: internal error: process exited while \
connecting to monitor: Could not open '/var/lib/nova/instances/7b2e4c1a-.../disk': Permission denied
```

```text
nova.exception.VirtualInterfaceCreateException: Virtual Interface creation failed
```

## Description

This error is emitted by `nova-compute` after the scheduler has already picked a
host. Placement and the filters succeeded — the failure is local to the
hypervisor while the driver (usually libvirt/QEMU) tries to actually create the
domain. The instance transitions to `ERROR` and the fault message names the
underlying libvirt, storage, or networking failure. Because scheduling passed,
the root cause is almost always on the chosen compute node itself.

## Technologies

- openstack (nova-compute, libvirt, QEMU, neutron agent)

## Severity

**high** — the specific instance build fails, and if the cause is a host-wide
condition (full disk, broken libvirt, dead OVS agent) every subsequent spawn on
that compute node will fail too.

## Common Causes

1. Image download or backing-file copy failed — full or unwritable
   `/var/lib/nova/instances`, or a corrupt image in the cache.
2. libvirt/QEMU error — wrong permissions, SELinux/AppArmor denial, or a missing
   CPU feature / machine type.
3. Neutron port could not be wired up in time, raising
   `VirtualInterfaceCreateException` after `vif_plugging_timeout`.
4. Cinder volume attach failed during boot-from-volume.
5. Out of memory or hugepages not available for the requested NUMA topology.

## Root Cause Analysis

After scheduling, `nova-compute` calls the virt driver's `spawn()`. The driver
fetches/copies the image, builds the libvirt XML, plugs VIFs (waiting for a
Neutron `network-vif-plugged` event), and starts the domain. A failure at any
step raises an exception that is logged verbatim and bubbles up as the instance
fault. The exact wording — `libvirtError`, `Permission denied`,
`VirtualInterfaceCreateException`, `No space left on device` — points directly
at which stage broke.

## Diagnostic Commands

```bash
# Read the instance fault that nova recorded
openstack server show <instance> -c fault -f value

# Which compute host did it land on?
openstack server show <instance> -c 'OS-EXT-SRV-ATTR:host' -f value

# nova-compute log around the spawn failure
journalctl -u devstack@n-cpu --since "10 min ago" | grep -i spawn

# Disk space on the instances directory (a classic culprit)
df -h /var/lib/nova/instances

# libvirt health and recent domain errors
journalctl -u libvirtd --since "10 min ago"
virsh list --all
```

## Expected Results

```text
fault | {'message': 'Instance failed to spawn', 'code': 500,
         'details': "...No space left on device..."}

Filesystem            Size  Used Avail Use% Mounted on
/dev/mapper/nova-inst  50G   50G     0 100% /var/lib/nova/instances
```

A `100%` full filesystem, an AppArmor/SELinux `denied` line, or a
`network-vif-plugged` timeout in the log each identify the broken stage.

## Resolution

1. **Disk full:** clear orphaned instance dirs / image cache, grow the volume,
   then retry. Set `remove_unused_base_images = true` to auto-prune.
2. **Permissions / MAC:** ensure `/var/lib/nova/instances` is owned by `nova`,
   and fix the SELinux/AppArmor denial (`audit2why`, correct context/profile).
3. **VIF timeout:** confirm the Neutron L2 agent is healthy on the host and that
   it emits `network-vif-plugged`; raise `vif_plugging_timeout` only as a stopgap.
4. **Volume attach:** check `cinder-volume` and the host's iSCSI/FC connectivity.
5. After fixing the host cause, rebuild or recreate the instance.

## Validation

```bash
openstack server create --flavor m1.small --image cirros --network private spawn-test
openstack server show spawn-test -c status -f value   # Expect: ACTIVE
```

## Prevention

- Alert on `/var/lib/nova/instances` disk usage and image-cache growth.
- Monitor `libvirtd` and the Neutron L2 agent per compute host.
- Validate SELinux/AppArmor policy after any nova/libvirt upgrade.
- Pre-pull and checksum golden images to avoid corrupt cache copies.

## Related Errors

- [OpenStack Nova NoValidHost: No Valid Host Was Found](./openstack-nova-no-valid-host-was-found.md)
- [OpenStack Nova Build of Instance Aborted](./openstack-nova-build-of-instance-aborted.md)

## References

- [Nova compute troubleshooting](https://docs.openstack.org/nova/latest/admin/support-compute.html)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`openstack` · `nova` · `libvirt` · `spawn` · `hypervisor` · `production`
