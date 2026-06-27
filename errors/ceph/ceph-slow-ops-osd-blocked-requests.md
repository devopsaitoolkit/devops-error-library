---
title: "Ceph Slow Ops / Blocked Requests"
slug: ceph-slow-ops-osd-blocked-requests
technologies: [ceph]
severity: high
tags: [ceph, osd, latency, slow-ops, production]
related: [ceph-osd-down-and-out, ceph-pg-degraded-undersized]
last_reviewed: 2026-06-27
---

# Ceph Slow Ops / Blocked Requests

## Error Message

```text
cluster:
  id:     5b2a9c1e-7f3d-4a8b-9e6c-1d4f8a2b3c5e
  health: HEALTH_WARN
          12 slow ops, oldest one blocked for 47 sec, osd.9 has slow ops
```

```text
$ ceph health detail
HEALTH_WARN 12 slow ops, oldest one blocked for 47 sec, daemons [osd.9,osd.4] have slow ops.
[WRN] SLOW_OPS: 12 slow ops, oldest one blocked for 47 sec, osd.9 has slow ops
```

```text
# Older / classic phrasing engineers still search for:
HEALTH_WARN 34 requests are blocked > 32 sec; 2 osds have blocked requests
```

## Description

Ceph reports `SLOW_OPS` (historically "blocked requests") when an OSD operation
sits in its queue longer than `osd_op_complain_time` (default 30s) without
completing. The named OSD is the bottleneck — it has accepted client or
peering/recovery ops but cannot finish them quickly enough. Because RBD/CephFS
clients wait synchronously on these ops, slow ops translate directly into
application-level latency spikes, stalled VMs, and timeouts.

This is a *performance* health check, not a redundancy one: the data is intact,
but I/O is being held up. It frequently precedes (or accompanies) an OSD going
down if the underlying device is failing.

## Technologies

- ceph (OSD, BlueStore, cluster network)

## Severity

**high** — client I/O on the affected PGs stalls for tens of seconds or longer.
For latency-sensitive workloads (databases on RBD, VM disks) this is effectively
an outage even though the cluster is technically `HEALTH_WARN`. Sustained slow
ops on one OSD often signal a dying disk.

## Common Causes

1. A failing or degraded device — high latency from a disk with reallocated
   sectors, a dying SSD, or a controller resetting.
2. Cluster network problems: packet loss, MTU mismatch, or a saturated/flapping
   NIC stalling peering and replication ops.
3. Resource saturation on the OSD host — CPU, memory pressure, or BlueStore DB/WAL
   on an overloaded device.
4. A recovery/backfill or deep-scrub storm competing with client I/O on the same
   spindles.
5. PG peering stuck waiting on a slow/unresponsive peer OSD.

## Root Cause Analysis

Every OSD runs op shards with bounded queues. When a request (client read/write,
sub-op replication, or peering message) is dequeued but its backend completion —
a BlueStore disk write/read or a network reply from a replica — does not return,
the op ages in flight. Once it exceeds `osd_op_complain_time`, the OSD logs it and
reports `SLOW_OPS` to the monitors with the op's current stage. The stage in
`dump_ops_in_flight` (e.g. `waiting for sub ops`, `waiting for rw locks`,
`reached_pg`, `started`) tells you *where* it is stuck: `waiting for sub ops`
implicates a slow replica/network; long `started`/commit stages implicate the
local disk. Thus slow ops are a symptom whose root cause is almost always a slow
disk or a slow network path on the named OSD.

## Diagnostic Commands

```bash
# Which OSDs have slow ops and for how long
ceph status
ceph health detail

# Per-OSD commit/apply latency — find the slow OSD objectively
ceph osd perf

# Inspect the actual stuck ops on the offending OSD (read-only admin socket)
ceph daemon osd.9 dump_ops_in_flight
ceph daemon osd.9 dump_historic_ops

# OSD daemon log for slow-op / disk / heartbeat warnings
journalctl -u ceph-osd@9 --no-pager -n 200 | grep -iE 'slow|blocked|heartbeat'

# Device-level latency and errors on the OSD's host
iostat -x 2 3
dmesg -T | grep -iE 'error|reset|i/o'
```

## Expected Results

```text
$ ceph osd perf
osd  commit_latency(ms)  apply_latency(ms)
  9                 612                 631
  4                  18                  19
  3                   5                   6

# osd.9's commit/apply latency is ~30x its peers — the device or its path is
# the bottleneck. dump_ops_in_flight will show ops parked at the same stage
# (e.g. 'waiting for sub ops' -> network/replica; 'started' -> local disk).
```

## Resolution

1. Identify the bottleneck OSD from `ceph osd perf` and the op stage from
   `dump_ops_in_flight`.
2. If it is a **disk**, confirm with `iostat`/SMART/`dmesg`. If the device is
   failing, drain it gracefully and replace it:

   ```bash
   # Gracefully stop directing I/O to the bad OSD, then replace the disk
   ceph osd out 9
   ```
3. If it is the **network**, fix MTU/packet loss/NIC issues on the cluster
   network; restarting the OSD won't help until the path is clean.
4. If a scrub or recovery storm is competing with client I/O, throttle it:

   ```bash
   ceph config set osd osd_max_backfills 1
   ceph config set osd osd_scrub_during_recovery false
   ```
5. If the host is resource-starved, relieve CPU/memory pressure or rebalance OSDs
   off an overloaded node.

## Validation

```bash
ceph health detail
# Expect: no SLOW_OPS check; HEALTH_OK.

ceph osd perf
# Expect: commit/apply latency for the former offender back in line with peers.
```

## Prevention

- Monitor `ceph osd perf` and alert on per-OSD latency outliers, not just health.
- Use SMART monitoring to catch dying disks before they cause slow ops.
- Keep BlueStore DB/WAL on fast media and size the cluster network for recovery.
- Cap `osd_max_backfills` and avoid scrubbing during recovery to protect client
  latency.

## Related Errors

- [Ceph OSD Down and Out](./ceph-osd-down-and-out.md)
- [Ceph PG Degraded / Undersized](./ceph-pg-degraded-undersized.md)

## References

- [Ceph: Health checks — SLOW_OPS](https://docs.ceph.com/en/latest/rados/operations/health-checks/#slow-ops)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`ceph` · `osd` · `latency` · `slow-ops` · `production`
