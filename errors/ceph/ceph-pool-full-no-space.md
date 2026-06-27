---
title: "Ceph Pool Full — No Space Left"
slug: ceph-pool-full-no-space
technologies: [ceph]
severity: critical
tags: [ceph, pool, capacity, full, production]
related: [ceph-health-warn-osd-nearfull, ceph-osd-down-and-out]
last_reviewed: 2026-06-27
---

# Ceph Pool Full — No Space Left

## Error Message

```text
cluster:
  id:     5b2a9c1e-7f3d-4a8b-9e6c-1d4f8a2b3c5e
  health: HEALTH_ERR
          1 full osd(s)
          2 pool(s) full
          Full ratio(s) out of order
```

```text
$ ceph health detail
HEALTH_ERR 1 full osd(s); 2 pool(s) full
[ERR] OSD_FULL: 1 full osd(s)
    osd.7 is full
[WRN] POOL_FULL: 2 pool(s) full
    pool 'rbd' is full (reached quota or full ratio)
```

```text
# What clients actually see:
rados put obj1 ./file -p rbd
error putting rbd/obj1: (28) No space left on device
```

## Description

When any OSD crosses the `full_ratio` (default `0.95`, 95% used), Ceph sets the
cluster `full` flag and **stops accepting writes** to protect against an OSD
running completely out of space — which could corrupt BlueStore metadata. The
health goes `HEALTH_ERR`, and clients writing to affected pools get `ENOSPC`
("No space left on device") or hang. Reads typically still work.

The same `POOL_FULL` state can also be reached via a per-pool **quota**
(`target_max_bytes`/`target_max_objects` or `max_bytes`), independent of physical
capacity. Distinguishing "physically full OSD" from "quota reached" is the first
diagnostic step.

## Technologies

- ceph (OSD, mon, pool quota, BlueStore)

## Severity

**critical** — this is a write outage. Every client (RBD volumes, CephFS, RGW
buckets) on the affected pools fails or stalls on write. VMs backed by RBD can go
read-only or crash; CephFS clients block. Recovery itself can also be blocked if
OSDs are past `backfillfull`, creating a deadlock that needs manual intervention.

## Common Causes

1. The cluster genuinely ran out of space — sustained growth with no headroom,
   often worsened by uneven OSD utilization (one OSD hits 95% first).
2. A backfill/recovery event pushed an already-full OSD over the edge.
3. A pool quota (`max_bytes`/`target_max_bytes`) was reached even though raw
   capacity remains.
4. Snapshots or orphaned/unreferenced objects consuming space that nobody is
   accounting for (RGW garbage not collected, RBD snapshots).

## Root Cause Analysis

The monitors track each OSD's utilization. Crossing `full_ratio` flips the global
`full` flag in the OSD map; OSDs then reject client writes for any pool whose data
maps to a full OSD, surfacing as `ENOSPC`. Because writes can't proceed and
backfill onto other OSDs may also be blocked once OSDs pass `backfillfull` (0.90),
the cluster can wedge: it can't free space by rebalancing and can't accept the
deletes that would free space if those deletes themselves require writes. A
pool-quota full is simpler — the monitors compare pool usage to the configured
quota and block writes to that pool only, regardless of raw free space.

## Diagnostic Commands

```bash
# Confirm HEALTH_ERR and which checks fired
ceph status
ceph health detail

# Raw capacity per pool and overall; %USED and MAX AVAIL per pool
ceph df detail

# Find the fullest OSD(s) and check VAR for imbalance
ceph osd df tree

# Is a pool quota the cause? Look for max_bytes / max_objects
ceph osd pool get-quota <pool>

# Current full/backfillfull/nearfull ratios in the OSD map
ceph osd dump | grep -E 'full_ratio'
```

## Expected Results

```text
$ ceph df detail
--- POOLS ---
POOL    ID  STORED   OBJECTS  %USED   MAX AVAIL
rbd      2  890 GiB   228.0k  98.21      0 B

# MAX AVAIL of 0 B and %USED ~95+ confirms physical fullness.
# If 'ceph osd pool get-quota rbd' shows max_bytes set and STORED >= that,
# the cause is a quota, not raw capacity.
```

## Resolution

1. Determine quota-vs-capacity. If it is a **quota**, raise or clear it:

   ```bash
   ceph osd pool set-quota <pool> max_bytes 0   # 0 = unlimited
   ```
2. If physically full, give recovery room to breathe by *temporarily* nudging the
   ratios up a hair so backfill/deletes can run — this is a release valve, not a
   fix:

   ```bash
   # Small temporary bump to un-wedge; revert after freeing space
   ceph osd set-full-ratio 0.97
   ceph osd set-backfillfull-ratio 0.92
   ```
3. Free real space: delete unused RBD images/snapshots, run RGW garbage
   collection (`radosgw-admin gc process`), remove stale CephFS data.
4. Add OSDs/capacity — the only durable fix for genuine growth. Then enable the
   `upmap` balancer so the new space is used evenly.
5. Once OSDs drop below `nearfull`, restore default ratios:

   ```bash
   ceph osd set-full-ratio 0.95
   ceph osd set-backfillfull-ratio 0.90
   ```

## Validation

```bash
ceph health detail
# Expect: no OSD_FULL / POOL_FULL; HEALTH_OK.

ceph df detail
# Expect: MAX AVAIL > 0 for every pool and %USED comfortably below 95.
```

## Prevention

- Alert at 80% OSD utilization and page at 85%; never let an OSD reach 95%.
- Run the `upmap` balancer so no single OSD fills far ahead of the others.
- Set pool quotas deliberately and monitor them; capacity-plan to keep the
  cluster under ~70–75% so failures can backfill without hitting full.
- Schedule RGW GC and audit RBD/CephFS snapshots regularly.

## Related Errors

- [Ceph OSD Nearfull HEALTH_WARN](./ceph-health-warn-osd-nearfull.md)
- [Ceph OSD Down and Out](./ceph-osd-down-and-out.md)

## References

- [Ceph: OSD full ratios and recovery](https://docs.ceph.com/en/latest/rados/operations/health-checks/#osd-full)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`ceph` · `pool` · `capacity` · `full` · `production`
