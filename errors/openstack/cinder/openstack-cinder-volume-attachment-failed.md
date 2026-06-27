---
title: "OpenStack Cinder Volume Attachment Failed"
slug: openstack-cinder-volume-attachment-failed
technologies: [openstack, cinder]
severity: high
tags: [openstack, cinder, attach, iscsi, nova, production]
related: [openstack-cinder-volume-in-error-state, openstack-nova-instance-failed-to-spawn]
last_reviewed: 2026-06-27
---

# OpenStack Cinder Volume Attachment Failed

## Error Message

```text
nova-compute[1843]: ERROR nova.virt.block_device [req-2c9f...] [instance: 5a7d...] \
Driver failed to attach volume 8e3b... at /dev/vdb: \
os_brick.exception.VolumeDeviceNotFound: Volume device not found at /dev/disk/by-path/\
ip-10.0.0.21:3260-iscsi-iqn.2010-10.org.openstack:volume-8e3b...-lun-1
```

```text
cinder-volume[3271]: ERROR cinder.volume.manager Unable to initialize connection \
for volume 8e3b...: iSCSI target portal 10.0.0.21:3260 not reachable
```

## Description

Attachment failure occurs when the compute node cannot connect the Cinder volume
into the guest. The control-plane attach call may succeed (the attachment record
is created), but the **data path** — iSCSI/FC login, RBD map, or multipath
discovery — does not complete, so the device never appears on the host and Nova
cannot present it to the instance. The volume often ends up stuck in `attaching`
or reverts to `available` while the instance lacks the disk.

## Technologies

- openstack (cinder-volume, nova-compute, os-brick, iSCSI/FC/RBD transport)

## Severity

**high** — the instance does not get its volume; boot-from-volume instances fail
to start, and a host-wide transport problem blocks all attaches on that compute.

## Common Causes

1. iSCSI/FC connectivity broken — target portal unreachable, wrong VLAN, MTU
   mismatch, or firewall on port 3260.
2. Initiator misconfiguration — missing/duplicate `initiatorname.iscsi`, or
   `iscsid`/`multipathd` not running on the compute node.
3. Multipath misconfiguration causing the device path never to settle.
4. Ceph/RBD: missing keyring or `ceph.conf` on the compute host.
5. Stale or duplicate attachment record left after a prior failure.

## Root Cause Analysis

On attach, `cinder-volume` runs `initialize_connection()` to export the volume
and returns connection info (target IQN/portal, or RBD pool/image). `nova-compute`
hands this to `os-brick` on the compute node, which performs the iSCSI login / FC
scan / RBD map and waits for the block device to appear under
`/dev/disk/by-path` (or `/dev/rbd*`). If the transport is unreachable, the
initiator is misconfigured, or multipath never converges, the device never
materializes and `os-brick` raises `VolumeDeviceNotFound`. The failure is on the
data path between compute host and storage, not in the Cinder DB.

## Diagnostic Commands

```bash
# Attachment state and the host involved
openstack volume show <volume-id> -c status -c attachments

# nova-compute attach error
journalctl -u devstack@n-cpu --since "10 min ago" | grep -iE "attach|os_brick|by-path"

# On the compute node: is the iSCSI target reachable / logged in?
sudo iscsiadm -m session
sudo iscsiadm -m discovery -t sendtargets -p 10.0.0.21:3260

# Transport daemons running?
systemctl status iscsid multipathd

# Multipath device view
sudo multipath -ll
```

## Expected Results

```text
# volume show
status      | attaching                 # stuck — never reached 'in-use'

# iscsiadm discovery on the compute node
iscsiadm: cannot make connection to 10.0.0.21:3260 (No route to host)
```

A failed discovery, `iscsid` not running, or a missing `/dev/disk/by-path` device
confirms a data-path problem. A healthy attach reaches `status: in-use`.

## Resolution

1. **Connectivity:** restore reachability to the storage portal (route, VLAN,
   firewall port 3260, MTU). Verify with `iscsiadm -m discovery`.
2. **Initiator/daemons:** ensure `iscsid` and `multipathd` are enabled and the
   compute node has a unique `/etc/iscsi/initiatorname.iscsi`.
3. **Ceph:** confirm `ceph.conf` and the cinder keyring exist on the compute host.
4. **Stuck record:** clean up a stale attachment, then re-attach:
   ```bash
   openstack volume attachment list --volume <volume-id>
   openstack server add volume <instance> <volume-id>
   ```

## Validation

```bash
openstack server add volume <instance> <volume-id> --device /dev/vdb
openstack volume show <volume-id> -c status -f value   # Expect: in-use
```

## Prevention

- Monitor storage-network reachability (portal ping, port 3260) from computes.
- Ensure `iscsid`/`multipathd` are enabled on every compute node via config mgmt.
- Standardize multipath.conf and initiator naming across the fleet.
- Distribute Ceph keyrings/`ceph.conf` consistently to all compute hosts.

## Related Errors

- [OpenStack Cinder Volume in Error State](./openstack-cinder-volume-in-error-state.md)
- [OpenStack Nova Instance Failed to Spawn](../nova/openstack-nova-instance-failed-to-spawn.md)

## References

- [Cinder troubleshooting](https://docs.openstack.org/cinder/latest/admin/troubleshooting.html)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`openstack` · `cinder` · `attach` · `iscsi` · `nova` · `production`
