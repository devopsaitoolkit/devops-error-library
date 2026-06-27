---
title: "Ceph OSD Nearfull HEALTH_WARN"
slug: ceph-health-warn-osd-nearfull
technologies: [ceph]
severity: medium
tags: [ceph, osd, capacity, nearfull, production]
related: [ceph-pool-full-no-space, ceph-osd-down-and-out]
last_reviewed: 2026-06-27
---

# Ceph OSD Nearfull HEALTH_WARN

## Error Message

```text
cluster:
  id:     5b2a9c1e-7f3d-4a8b-9e6c-1d4f8a2b3c5e
  health: HEALTH_WARN
          1 nearfull osd(s)
          2 pool(s) nearfull
```

```text
$ ceph health detail
HEALTH_WARN 1 nearfull osd(s); 2 pool(s) nearfull
[WRN] OSD_NEARFULL: 1 nearfull osd(s)
    osd.7 is near full
[WRN] POOL_NEARFULL: 2 pool(s) nearfull
    pool 'rbd' is nearfull
    pool 'cephfs_data' is nearfull
```

## Description

Ceph raises `OSD_NEARFULL` when at least one OSD's utilization crosses the
`mon_osd_nearfull_ratio` threshold (default `0.85`, i.e. 85% full). This is an
early-warning state emitted by the monitors based on the OSDs' reported usage.
The cluster is still serving reads and writes normally, but it is telling you
that a single OSD is approaching the `backfillfull` (default `0.90`) and `full`
(default `0.95`) ratios, beyond which Ceph will block writes to protect data.

Because CRUSH placement is rarely perfectly even, one OSD often crosses
`nearfull` long before the cluster's average utilization looks alarming. The
warning is therefore about the *fullest* OSD, not aggregate free space.

## Technologies

- ceph (mon, OSD, CRUSH)

## Severity

**medium** — no outage yet and I/O continues, but you are one threshold away from
`backfillfull` (which stalls recovery/backfill) and two thresholds from `full`
(which blocks all writes cluster-wide). Treat it as an actionable capacity
warning, not noise.

## Common Causes

1. Genuine capacity growth — the cluster is simply filling up and needs more
   OSDs or larger devices.
2. Uneven data distribution: a low `pg_num`, imbalanced CRUSH weights, or
   mismatched device sizes push more PGs onto one OSD.
3. The automatic balancer is off or in `none` mode, so PGs never get evened out.
4. A reweight or a recently added/removed OSD left placement skewed mid-rebalance.

## Root Cause Analysis

Each OSD periodically reports its raw used/total bytes to the monitors. The
monitors compare per-OSD utilization against the configured ratios and flag any
OSD over `nearfull`. Because objects are placed into PGs and PGs are mapped to
OSDs by CRUSH, an OSD with more PGs — or larger PGs — accumulates more data. With
too few PGs per pool, the law of large numbers does not smooth out the variance,
so one OSD can be 88% full while the cluster average is 70%. The warning reflects
that worst-case OSD because the *fullest* OSD is what ultimately gates writes.

## Diagnostic Commands

```bash
# Overall status and which health checks are firing
ceph status
ceph health detail

# Per-OSD utilization — find the fullest OSD; watch the %USE and VAR columns
ceph osd df tree

# Current nearfull / backfillfull / full ratios in effect
ceph osd dump | grep -E 'full_ratio|nearfull_ratio'

# CRUSH weights and the OSD layout, to spot imbalance
ceph osd tree

# Is the balancer running, and in what mode?
ceph balancer status
```

## Expected Results

```text
$ ceph osd df tree
ID  CLASS  WEIGHT   REWEIGHT  SIZE     RAW USE  %USE   VAR   PGS  STATUS  TYPE NAME
 7  ssd    1.00000   1.00000  1.0 TiB  883 GiB  86.21  1.18  142  up          osd.7
 3  ssd    1.00000   1.00000  1.0 TiB  701 GiB  68.45  0.94  119  up          osd.3
...

# A %USE above ~85 with a VAR (variance vs. average) well over 1.0 confirms
# that osd.7 is overloaded relative to peers. A healthy cluster keeps every
# OSD's %USE clustered and VAR close to 1.0.
```

## Resolution

1. Confirm whether this is real growth or imbalance via `ceph osd df tree`. If
   one OSD has a high `VAR` and `PGS` count, it is imbalance.
2. For imbalance, enable the balancer in `upmap` mode (safe, no data-movement
   beyond rebalancing):

   ```bash
   ceph balancer mode upmap
   ceph balancer on
   ceph balancer status
   ```
3. If `pg_num` is too low for the pool size, raise it (let the autoscaler handle
   it where possible). More PGs = smoother distribution.
4. For genuine capacity pressure, add OSDs or larger devices, then let backfill
   redistribute data. This is the durable fix.
5. As a last-resort stopgap while hardware ships, you may temporarily nudge the
   nearfull ratio, but understand this only moves the warning, not the risk:

   ```bash
   # Stopgap only — raises the warning threshold, does NOT add capacity
   ceph osd set-nearfull-ratio 0.87
   ```

## Validation

```bash
ceph health detail
# Expect: HEALTH_OK with no OSD_NEARFULL / POOL_NEARFULL checks.

ceph osd df tree
# Expect: every OSD's %USE below 85 and VAR values converging toward 1.0.
```

## Prevention

- Keep the balancer on (`upmap`) so distribution stays even automatically.
- Alert on per-OSD utilization at 80% — earlier than Ceph's 85% default.
- Size pools with the PG autoscaler enabled to avoid low `pg_num` skew.
- Capacity-plan to keep cluster utilization under ~70–75% so a single OSD or host
  failure does not push survivors past `nearfull`.

## Related Errors

- [Ceph Pool Full / No Space](./ceph-pool-full-no-space.md)
- [Ceph OSD Down and Out](./ceph-osd-down-and-out.md)

## References

- [Ceph: OSD Configuration — full ratios](https://docs.ceph.com/en/latest/rados/configuration/mon-osd-interaction/)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`ceph` · `osd` · `capacity` · `nearfull` · `production`
