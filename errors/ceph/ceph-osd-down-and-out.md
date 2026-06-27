---
title: "Ceph OSD Down and Out"
slug: ceph-osd-down-and-out
technologies: [ceph]
severity: high
tags: [ceph, osd, availability, recovery, production]
related: [ceph-pg-degraded-undersized, ceph-slow-ops-osd-blocked-requests]
last_reviewed: 2026-06-27
---

# Ceph OSD Down and Out

## Error Message

```text
cluster:
  id:     5b2a9c1e-7f3d-4a8b-9e6c-1d4f8a2b3c5e
  health: HEALTH_WARN
          1 osds down
          Degraded data redundancy: 18342/2750130 objects degraded (0.667%), 23 pgs degraded
  services:
    osd: 12 osds: 11 up (since 4m), 12 in (since 3w)
```

```text
$ ceph health detail
HEALTH_WARN 1 osds down; Degraded data redundancy: 23 pgs degraded
[WRN] OSD_DOWN: 1 osds down
    osd.5 (root=default,host=ceph-node03) is down
```

## Description

An OSD is `down` when the monitors have stopped receiving heartbeats from it (or
peer OSDs reported it unreachable), so it is no longer serving I/O. Each OSD has
two orthogonal flags: `up`/`down` (is the daemon alive and reachable) and
`in`/`out` (does CRUSH still place data on it). A freshly-failed OSD is `down`
but still `in`; after `mon_osd_down_out_interval` (default 600s / 10 minutes) the
monitors mark it `out`, which triggers CRUSH to remap its PGs and backfill the
data onto surviving OSDs.

While the OSD is `down` but still `in`, affected PGs run degraded (fewer
replicas). Once it goes `out`, recovery traffic begins. Both states are visible
in `ceph status`.

## Technologies

- ceph (OSD, mon, CRUSH, BlueStore)

## Severity

**high** — every PG that lived on the down OSD is now under-replicated, reducing
fault tolerance and risking data unavailability if a second copy fails before
recovery completes. A single down OSD is recoverable; multiple simultaneous
downs in the same failure domain can mean data loss.

## Common Causes

1. The OSD process crashed or was OOM-killed on the host (check the daemon log
   and `dmesg`).
2. Underlying disk failure or I/O errors — the device returned read/write errors
   and BlueStore aborted.
3. Network partition or flapping: the OSD is alive but heartbeats can't reach
   peers/mons, so it is wrongly reported down.
4. Host down — node reboot, power loss, or kernel panic took the OSD with it.
5. Clock skew or an overloaded host causing heartbeat timeouts.

## Root Cause Analysis

OSDs exchange heartbeats with peers over the cluster (back-side) network and
report to the monitors over the public network. If `mon_osd_min_down_reporters`
peers report an OSD as unresponsive — or the OSD stops checking in — the monitors
mark it `down` in the OSD map and propagate the new map cluster-wide. Clients and
peers stop directing I/O to it. The PGs it hosted drop a replica and become
`degraded`. If the OSD does not come back within `mon_osd_down_out_interval`, it
is marked `out`; CRUSH recomputes placement without it and surviving OSDs backfill
the missing copies. The distinction matters: a network blip can mark a perfectly
healthy disk `down`, whereas a real disk failure will keep it down permanently.

## Diagnostic Commands

```bash
# Cluster view: which OSDs are up/in and which PGs are degraded
ceph status
ceph health detail

# Tree showing the down OSD, its host, and CRUSH placement
ceph osd tree

# Per-OSD state and last-known address (find when it went down)
ceph osd dump | grep -E '^osd\.5|osd.5'

# On the host owning osd.5 — read the daemon log for the crash/IO error
journalctl -u ceph-osd@5 --no-pager -n 200

# Kernel-level disk errors for the underlying device
dmesg -T | grep -iE 'error|i/o|sd[a-z]'
```

## Expected Results

```text
$ ceph osd tree
ID  CLASS  WEIGHT   TYPE NAME            STATUS  REWEIGHT  PRI-AFF
-1         12.0     root default
-5          4.0         host ceph-node03
 5  ssd     1.0             osd.5          down    1.00000  1.00000
...

# 'down' with REWEIGHT still 1.0 means it is down-but-in (no remap yet).
# journalctl will show either a clean stop, a panic/assert, or repeated
# 'bdev ... read error' lines pointing at a failing disk.
```

## Resolution

1. Identify *why* it is down from `journalctl -u ceph-osd@5` and `dmesg`.
2. If it is transient (network blip, host briefly busy) and the disk is healthy,
   restart the daemon:

   ```bash
   systemctl restart ceph-osd@5
   ceph osd tree   # confirm it returns to 'up'
   ```
3. If the disk has failed, do **not** force it back in. Mark it out and let
   recovery proceed (it may already be out after 10 minutes), then replace the
   device and re-provision the OSD:

   ```bash
   ceph osd out 5            # if not already out — triggers backfill
   # ... physically replace disk, then redeploy the OSD via your orchestrator
   ```
4. If the host is down, recover the host; OSDs rejoin automatically once it boots
   and heartbeats resume.
5. For network-caused flapping, fix the cluster network first; restarting before
   that just makes the OSD flap again.

## Validation

```bash
ceph status
# Expect: all OSDs "up" and "in", and degraded objects trending to 0.

ceph health detail
# Expect: no OSD_DOWN check; HEALTH_OK once recovery finishes.
```

## Prevention

- Monitor disk SMART and OSD daemon liveness; alert on the first OSD_DOWN.
- Separate and size the cluster (replication) network so heartbeats aren't starved
  under recovery load.
- Spread OSDs across failure domains (host/rack) in CRUSH so one node failure
  never crosses your replica count.
- Keep NTP healthy to avoid skew-induced false-down reports.

## Related Errors

- [Ceph PG Degraded / Undersized](./ceph-pg-degraded-undersized.md)
- [Ceph Slow Ops / Blocked Requests](./ceph-slow-ops-osd-blocked-requests.md)

## References

- [Ceph: Monitoring OSDs and PGs](https://docs.ceph.com/en/latest/rados/operations/monitoring-osd-pg/)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`ceph` · `osd` · `availability` · `recovery` · `production`
