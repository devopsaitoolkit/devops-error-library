---
title: "Ceph PG Degraded and Undersized"
slug: ceph-pg-degraded-undersized
technologies: [ceph]
severity: high
tags: [ceph, pg, replication, recovery, production]
related: [ceph-osd-down-and-out, ceph-pg-inconsistent-scrub-errors]
last_reviewed: 2026-06-27
---

# Ceph PG Degraded and Undersized

## Error Message

```text
cluster:
  id:     5b2a9c1e-7f3d-4a8b-9e6c-1d4f8a2b3c5e
  health: HEALTH_WARN
          Degraded data redundancy: 41207/2750130 objects degraded (1.498%), 57 pgs degraded, 31 pgs undersized
  data:
    pgs:     31 active+undersized+degraded
             481 active+clean
```

```text
$ ceph health detail
HEALTH_WARN Degraded data redundancy: 57 pgs degraded, 31 pgs undersized
[WRN] PG_DEGRADED: Degraded data redundancy: 57 pgs degraded, 31 pgs undersized
    pg 4.1a is active+undersized+degraded, acting [3,8]
    pg 4.2f is active+undersized+degraded, acting [3,8]
```

## Description

A PG (placement group) is **degraded** when one or more of its replicas are
missing or out of date — Ceph knows the data exists but not enough up-to-date
copies are currently available. A PG is **undersized** when the acting set has
fewer OSDs than the pool's `size` (replication factor); for a `size=3` pool, an
acting set of `[3,8]` is undersized because only two of three copies are placed.
The two states usually appear together after an OSD or host failure: copies are
both missing (degraded) and there are fewer OSDs holding the PG than required
(undersized).

The PG is still `active`, so reads and writes continue — but redundancy is
reduced and Ceph is (or should be) recovering/backfilling the missing copies.

## Technologies

- ceph (PG, OSD, CRUSH, pool replication)

## Severity

**high** — data is being served from fewer copies than your durability policy
requires. Another failure in the affected PGs before recovery completes can cause
data unavailability (`incomplete`/`down` PGs) or, with `min_size` reached, blocked
I/O. This is a redundancy emergency, not a cosmetic warning.

## Common Causes

1. An OSD went down/out, dropping a replica from many PGs (most common).
2. CRUSH cannot place enough copies in distinct failure domains — too few
   hosts/OSDs for the requested `size` and CRUSH rule.
3. `pg_num` too low or a misconfigured CRUSH rule leaves PGs that can't satisfy
   `size`.
4. Recovery is stalled (backfill blocked by `nearfull` OSDs, or recovery limits
   throttled too aggressively).

## Root Cause Analysis

For each PG, Ceph maintains an *acting set* (the OSDs currently responsible) and
an *up set* (where CRUSH wants the data). When an OSD leaves, the acting set
shrinks; if CRUSH cannot immediately map a replacement OSD in a valid failure
domain, the PG stays undersized and degraded. Ceph then schedules recovery
(copying existing objects) and backfill (bulk rebuilding onto a new OSD). If the
cluster has fewer independent failure domains than `size` demands — say, `size=3`
across only two hosts — CRUSH can *never* place a third copy, so the PG remains
permanently undersized regardless of recovery. Likewise, if every candidate OSD
is `nearfull`/`backfillfull`, backfill won't start. Understanding whether the
shortage is *temporary* (OSD restart will fix it) or *structural* (not enough
hosts) determines the fix.

## Diagnostic Commands

```bash
# How many PGs are degraded/undersized and overall recovery progress
ceph status
ceph health detail

# State of every problem PG and its acting/up sets
ceph pg dump pgs_brief | grep -E 'undersized|degraded|backfill'

# Why is one PG stuck? Shows recovery_state and blocking peers
ceph pg 4.1a query

# OSD layout and how many independent hosts/failure domains exist
ceph osd tree

# Confirm no OSD is too full to accept backfill
ceph osd df tree
```

## Expected Results

```text
$ ceph pg dump pgs_brief | grep undersized
4.1a  active+undersized+degraded  [3,8]  3  [3,8]  3
4.2f  active+undersized+degraded  [3,8]  3  [3,8]  3

# acting set [3,8] for a size=3 pool = only 2 copies placed (undersized).
# If 'ceph osd tree' shows just 2 hosts up for a host-failure-domain,
# size=3 can never be satisfied — that is structural, not transient.
```

## Resolution

1. Find the trigger: usually a down/out OSD. Bring it back if the disk is healthy
   (`systemctl restart ceph-osd@N`) — that often re-fills the acting sets and
   clears the warning.
2. If an OSD failed permanently, ensure it is `out` so backfill onto survivors
   proceeds, then replace the device.
3. If PGs are stuck because `nearfull`/`backfillfull` OSDs block backfill, free
   space or rebalance first (see related nearfull doc).
4. If the shortage is structural (fewer failure domains than `size`), either add
   hosts/OSDs or, with full understanding of the durability trade-off, lower the
   pool's `size`:

   ```bash
   # Only if you genuinely cannot add capacity — reduces durability
   ceph osd pool set <pool> size 2
   ```
5. If recovery is just slow, you can temporarily raise recovery throughput, then
   revert once healthy:

   ```bash
   ceph config set osd osd_max_backfills 4
   ```

## Validation

```bash
ceph status
# Expect: pgs all "active+clean", degraded objects at 0.

ceph health detail
# Expect: no PG_DEGRADED check; HEALTH_OK.
```

## Prevention

- Run at least `size` independent failure domains (e.g. 3 hosts for `size=3`).
- Never let pools run with `min_size=1`; keep `min_size` at 2 for `size=3`.
- Alert on `PG_DEGRADED` and on recovery that stalls for more than a few minutes.
- Keep free space buffer so failures can backfill without hitting `backfillfull`.

## Related Errors

- [Ceph OSD Down and Out](./ceph-osd-down-and-out.md)
- [Ceph PG Inconsistent / Scrub Errors](./ceph-pg-inconsistent-scrub-errors.md)

## References

- [Ceph: Placement Group States](https://docs.ceph.com/en/latest/rados/operations/pg-states/)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`ceph` · `pg` · `replication` · `recovery` · `production`
