---
title: "LINSTOR Satellite Offline"
slug: linstor-satellite-offline
technologies: [linstor]
severity: high
tags: [linstor, satellite, connectivity, drbd, production]
related: [linstor-not-enough-available-nodes, linstor-controller-database-locked]
last_reviewed: 2026-06-27
---

# LINSTOR Satellite Offline

## Error Message

```text
$ linstor node list
╭──────────────────────────────────────────────────────────╮
┊ Node    ┊ NodeType  ┊ Addresses                  ┊ State   ┊
╞══════════════════════════════════════════════════════════╡
┊ node-01 ┊ SATELLITE ┊ 10.0.0.11:3366 (PLAIN)     ┊ Online  ┊
┊ node-02 ┊ SATELLITE ┊ 10.0.0.12:3366 (PLAIN)     ┊ OFFLINE ┊
┊ node-03 ┊ COMBINED  ┊ 10.0.0.13:3366 (PLAIN)     ┊ Online  ┊
╰──────────────────────────────────────────────────────────╯
```

```text
ERROR REPORT 65A1F0C2-00000-000000
Category: LinStorException
Connection refused: node-02/10.0.0.12:3366
Satellite not connected — controller cannot reach the linstor-satellite service.
```

## Description

A LINSTOR satellite is the agent that runs on every storage node and executes the
controller's instructions — creating LVM/ZFS volumes, configuring DRBD, and
reporting capacity back. When `linstor node list` shows a node in the `OFFLINE`
state, the **controller has lost its TCP control connection** (default port 3366)
to that satellite. The node's existing DRBD replication may still be running, but
the controller can no longer place, resize, or repair resources there until the
connection is restored.

## Technologies

- linstor (controller ⇄ satellite control channel, port 3366)

## Severity

**high** — the node is invisible to the orchestration layer. New volumes cannot be
placed on it, and a failover or auto-place that needs it will fail. If the
satellite is also where a resource's only `Primary` lives, a workload may be at
risk.

## Common Causes

1. The `linstor-satellite` systemd service is stopped, crashed, or failed to start
   after a reboot.
2. A firewall or security group blocks TCP port 3366 between controller and node.
3. The node is genuinely down (powered off, kernel panic, network partition).
4. TLS/SSL is configured on one side only, so the control handshake is rejected.
5. Clock skew or a stale satellite that needs the controller to re-issue its
   configuration.

## Root Cause Analysis

The controller holds a persistent control connection to each satellite. On any
disruption — service restart, dropped packets, blocked port — the controller marks
the node `OFFLINE` and stops issuing API calls to it. The satellite is stateless
with respect to LINSTOR metadata: all desired state lives in the controller
database, and the satellite reapplies it on (re)connect. So `OFFLINE` almost always
means a transport/process problem, not data corruption. The fix is to restore
connectivity; the controller then re-pushes the node's resource definitions.

## Diagnostic Commands

```bash
# Which node(s) the controller considers offline
linstor node list

# Is the satellite process actually running on the node?
systemctl status linstor-satellite

# Satellite logs — look for bind/permission/TLS errors
journalctl -u linstor-satellite -n 100 --no-pager

# Can the controller reach the satellite control port?
ss -lntp | grep 3366            # run on the satellite node
nc -vz 10.0.0.12 3366           # run from the controller

# Underlying DRBD replication is independent of the control channel
drbdadm status
```

## Expected Results

```text
# Healthy: socket is listening and reachable
LISTEN 0 50 0.0.0.0:3366 0.0.0.0:* users:(("java",pid=812,...))
Connection to 10.0.0.12 3366 port [tcp/*] succeeded!

# Faulty: satellite down or port blocked
nc: connect to 10.0.0.12 port 3366 (tcp) failed: Connection refused
journalctl: "Address already in use" or "satellite shutting down"
```

## Resolution

1. On the offline node, restart the satellite and confirm it binds 3366:

   ```bash
   sudo systemctl restart linstor-satellite
   sudo systemctl enable linstor-satellite   # survive reboots
   ```
2. If the port is blocked, open TCP 3366 (and 3370 for TLS, plus the DRBD data
   ports 7000-7999) between controller and satellite.
3. If TLS is in use, verify both controller and satellite share the same keystore
   configuration; a one-sided TLS config silently refuses the handshake.
4. If the node itself is down, bring it back; the satellite reconnects
   automatically and the controller re-pushes resource config — no manual
   re-create needed.

## Validation

```bash
linstor node list
# Expect: the node returns to State "Online".
drbdadm status
# Expect: resources on that node show Connected / UpToDate.
```

## Prevention

- `systemctl enable linstor-satellite` on every node so it survives reboots.
- Codify firewall rules for 3366/3370 and DRBD 7000-7999 in your provisioning.
- Alert on any node not `Online` in `linstor node list` (scrape via the REST API).
- Keep controller and satellite package versions in lock-step.

## Related Errors

- [LINSTOR Not Enough Available Nodes](./linstor-not-enough-available-nodes.md)
- [LINSTOR Controller Database Locked](./linstor-controller-database-locked.md)

## References

- [LINBIT: The LINSTOR User's Guide](https://linbit.com/drbd-user-guide/linstor-guide-1_0-en/)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`linstor` · `satellite` · `connectivity` · `drbd` · `production`
