---
title: "OpenStack Ironic Node Stuck in Deploying"
slug: openstack-ironic-node-stuck-in-deploying
technologies: [openstack, ironic]
severity: high
tags: [openstack, ironic, baremetal, deploying, pxe, production]
related: [openstack-nova-no-valid-host-was-found]
last_reviewed: 2026-06-27
---

# OpenStack Ironic Node Stuck in Deploying

## Error Message

```text
$ openstack baremetal node list
+--------------------------------------+----------+---------------+-------------+
| UUID                                 | Name     | Provision     | Power State |
|                                      |          | State         |             |
+--------------------------------------+----------+---------------+-------------+
| 9c1f...                              | node-07  | deploying     | power on    |
+--------------------------------------+----------+---------------+-------------+
```

```text
ironic-conductor[3120]: ERROR ironic.drivers.modules.agent_base [req-...] \
Deploy failed for node 9c1f...: Timeout reached while waiting for the IPA ramdisk \
to start. last_error: "Timeout reached while waiting for callback from ramdisk"
```

## Description

A bare-metal node is wedged in the `deploying` (or `wait call-back`) provision
state and never reaches `active`. Ironic deploys by powering the node into a PXE/
iPXE-booted IPA (Ironic Python Agent) ramdisk, which then writes the image to disk
and calls back to the conductor. If any step in that chain stalls — PXE/DHCP,
ramdisk boot, network reachability back to the conductor, or the disk write — the
node stops progressing and eventually times out or hangs.

## Technologies

- openstack (ironic-conductor, ironic-python-agent ramdisk, neutron/PXE-DHCP, TFTP/HTTP)

## Severity

**high** — the target node cannot be provisioned and is held out of the pool. If
the cause is shared infrastructure (DHCP, TFTP, the provisioning network), many
deploys fail at once.

## Common Causes

1. PXE/DHCP failure — the node never gets an address or boot file on the
   provisioning network (wrong VLAN, DHCP not serving, TFTP/HTTP unreachable).
2. The IPA ramdisk cannot route back to the conductor's callback URL (firewall,
   wrong `[deploy] http_url`/`api_url`, MTU mismatch).
3. Wrong NIC/boot mode — node boots from disk instead of network, or BIOS vs UEFI
   mismatch with the configured `boot_mode`.
4. BMC/IPMI problems so the conductor cannot reliably control power.
5. Disk/RAID issue: no valid `root_device` hint match, or the target disk fails.
6. A conductor restart/crash leaves the node's lock and TaskManager state stale.

## Root Cause Analysis

Ironic's deploy is a multi-stage state machine: set boot device to PXE, power on,
serve DHCP + boot file, boot IPA, IPA pulls the image over HTTP and writes it,
then IPA POSTs a callback (`heartbeat`) to the conductor, which finalizes and
reboots into the new OS. The node sits in `deploying`/`wait call-back` until the
heartbeat arrives. A break anywhere — L2 reachability, boot config, BMC control,
or disk — stops the heartbeat, so the node never advances and times out. The
conductor log names the stage that stalled.

## Diagnostic Commands

```bash
# Provision state and the last error
openstack baremetal node show node-07 -c provision_state -c last_error -c power_state -f value

# Conductor log for this node's deploy
journalctl -u ironic-conductor --since "30 min ago" | grep -i 9c1f

# Is the node's power controllable via the BMC?
openstack baremetal node power show node-07     # or: ipmitool -I lanplus -H <bmc> ... power status

# Validate the node's driver/interfaces are all OK
openstack baremetal node validate node-07

# Is DHCP/PXE serving on the provisioning network?
journalctl -u neutron-dhcp-agent --since "30 min ago" | grep -iE "DHCPOFFER|DHCPACK"
ss -lunp | grep -E ':67|:69'        # dnsmasq DHCP/TFTP listening

# Confirm the deploy/agent images and ramdisk URLs resolve
curl -sI http://<conductor>:8088/agent.kernel | head -n1
```

## Expected Results

```text
$ openstack baremetal node show node-07 -c provision_state -c last_error -f value
deploying
Timeout reached while waiting for callback from ramdisk

$ openstack baremetal node validate node-07
+------------+--------+----------------------------------+
| Interface  | Result | Reason                           |
+------------+--------+----------------------------------+
| power      | False  | IPMI call failed: power status.  |   <-- BMC issue
| deploy     | True   |                                  |
+------------+--------+----------------------------------+

# Healthy: validate is all True, DHCPACK appears for the node's MAC, and the
# provision state advances deploying -> wait call-back -> active.
```

## Resolution

1. Read `last_error` and `node validate` to pin the failing stage, then fix that
   stage specifically:
   - **PXE/DHCP**: correct the provisioning VLAN/network, ensure dnsmasq serves
     DHCP and TFTP/HTTP, verify the node's port MAC is registered in Ironic.
   - **Callback/network**: open conductor `api_url`/`http_url` ports to the
     provisioning subnet; fix MTU.
   - **Boot mode**: align `boot_mode` (uefi/bios) and set PXE first in BMC.
   - **BMC**: fix IPMI/Redfish credentials/connectivity so power control works.
   - **Disk**: set a correct `root_device` hint or replace the failed disk.
2. Once infrastructure is fixed, unstick the node — abort and clean back to
   `available`, then redeploy:
   ```bash
   openstack baremetal node abort node-07          # if abortable
   openstack baremetal node maintenance set node-07 --reason "stuck deploy"
   openstack baremetal node maintenance unset node-07
   openstack baremetal node deploy node-07
   ```
3. If a conductor crash left a stale lock, restart `ironic-conductor` so the node
   is re-managed.

## Validation

```bash
openstack baremetal node show node-07 -c provision_state -f value   # Expect: active
openstack baremetal node validate node-07                            # all True
```

## Prevention

- Monitor the provisioning network (DHCP/TFTP/HTTP) and conductor reachability.
- Standardize BMC firmware, boot mode, and NIC PXE order via inspection/templates.
- Set `[conductor] deploy_callback_timeout` sensibly and alert on nodes in
  `deploying` past it.
- Run periodic `node validate` across the fleet to catch BMC drift early.

## Related Errors

- [OpenStack Nova NoValidHost: No Valid Host Was Found](../nova/openstack-nova-no-valid-host-was-found.md)

## References

- [Ironic troubleshooting](https://docs.openstack.org/ironic/latest/admin/troubleshooting.html)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`openstack` · `ironic` · `baremetal` · `deploying` · `pxe` · `production`
