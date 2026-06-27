---
title: "Ceph PG Inconsistent — Scrub Errors"
slug: ceph-pg-inconsistent-scrub-errors
technologies: [ceph]
severity: high
tags: [ceph, pg, scrub, data-integrity, production]
related: [ceph-pg-degraded-undersized, ceph-osd-down-and-out]
last_reviewed: 2026-06-27
---

# Ceph PG Inconsistent — Scrub Errors

## Error Message

```text
cluster:
  id:     5b2a9c1e-7f3d-4a8b-9e6c-1d4f8a2b3c5e
  health: HEALTH_ERR
          1 scrub errors
          Possible data damage: 1 pg inconsistent
```

```text
$ ceph health detail
HEALTH_ERR 1 scrub errors; Possible data damage: 1 pg inconsistent
[ERR] OSD_SCRUB_ERRORS: 1 scrub errors
[ERR] PG_DAMAGED: Possible data damage: 1 pg inconsistent
    pg 4.7c is active+clean+inconsistent, acting [3,8,5]
```

```text
# In the OSD log:
log_channel(cluster) log [ERR] : 4.7c shard 8: soid 4:3e... data_digest 0x2d4f != data_digest 0x9a1b from auth oi
log_channel(cluster) log [ERR] : 4.7c deep-scrub 1 errors
```

## Description

A PG goes `inconsistent` when a (usually deep) scrub finds that the replicas of an
object disagree — different data digests, mismatched object sizes, missing
objects, or omap/attr differences across the acting set. Ceph stores a checksum
("digest") per object and, during deep-scrub, reads every replica and compares.
When copies disagree, Ceph cannot safely decide which is correct on its own, so it
flags `PG_DAMAGED`/`OSD_SCRUB_ERRORS` and goes `HEALTH_ERR`. The PG often stays
`active+clean+inconsistent` — it still serves I/O, but Ceph is warning you there
is latent corruption that needs repair.

## Technologies

- ceph (OSD, scrub/deep-scrub, BlueStore)

## Severity

**high** — this is a data-integrity error, not a redundancy one. At least one
replica of some object is wrong. If the bad replica is read or the good replica is
lost before repair, you can serve or propagate corrupt data. It demands prompt,
careful action.

## Common Causes

1. Latent disk corruption / bit rot — a sector returned different bytes than were
   written (the most common cause; BlueStore checksums catch it on read/scrub).
2. A failing or flaky drive silently corrupting data on one OSD.
3. A previous crash, power loss, or BlueStore issue that left one replica with a
   torn/partial write.
4. Bad RAM or controller writing corrupt data to one OSD's device.

## Root Cause Analysis

Each object replica carries a stored checksum. During deep-scrub the primary OSD
reads all replicas and compares both the data digests and metadata (size, omap,
attrs). A mismatch means one or more shards diverged from the authoritative copy
since the last scrub. BlueStore's own per-block CRCs usually pinpoint *which* shard
is bad — a `read error` or a `data_digest != ... from auth oi` line in the OSD log
names the offending shard/OSD. If the cluster can identify a clear authoritative
copy, `pg repair` will overwrite the bad shard from the good one. The danger case
is `size>=2` with `min_size` met but no clear majority (e.g. a 2-replica pool where
both differ) — there `repair` may copy the *primary's* version, which might be the
corrupt one, so you must verify which shard is bad first.

## Diagnostic Commands

```bash
# Confirm HEALTH_ERR and which PG is inconsistent
ceph status
ceph health detail

# List inconsistent PGs explicitly
rados list-inconsistent-pg <pool>

# Per-object detail: which shard's digest/size disagrees (names the bad OSD)
rados list-inconsistent-obj 4.7c --format=json-pretty

# Confirm acting set and last (deep-)scrub times for the PG
ceph pg dump pgs | grep '^4.7c'

# OSD log on the shard that mismatched — look for read error vs digest mismatch
journalctl -u ceph-osd@8 --no-pager -n 200 | grep -iE 'scrub|digest|read error'
```

## Expected Results

```text
$ rados list-inconsistent-obj 4.7c --format=json-pretty
{
  "inconsistents": [
    {
      "object": { "name": "rbd_data.3e...", ... },
      "shards": [
        { "osd": 3, "data_digest": "0x9a1b", "errors": [] },
        { "osd": 8, "data_digest": "0x2d4f", "errors": ["data_digest_mismatch_info"] },
        { "osd": 5, "data_digest": "0x9a1b", "errors": [] }
      ]
    }
  ]
}

# Here osd.8 is the outlier (digest differs, error flagged). osd.3 and osd.5
# agree — a clear majority makes repair safe.
```

## Resolution

1. Run `rados list-inconsistent-obj` and identify the bad shard. Only proceed to
   repair once you know which copy is wrong and that a good authoritative copy
   exists.
2. Trigger the repair (Ceph overwrites the bad shard from the authoritative copy):

   ```bash
   ceph pg repair 4.7c
   ceph pg dump pgs | grep '^4.7c'   # watch state return to active+clean
   ```
3. If the same OSD (e.g. osd.8) repeatedly produces scrub errors, the disk is
   failing — drain and replace it:

   ```bash
   ceph osd out 8     # graceful drain; then replace the device
   ```
4. Investigate the host for bad RAM/controller if corruption spans multiple OSDs.
5. After repair, manually re-deep-scrub the PG to confirm it is clean.

## Validation

```bash
ceph pg deep-scrub 4.7c
ceph health detail
# Expect: no OSD_SCRUB_ERRORS / PG_DAMAGED; PG state active+clean; HEALTH_OK.
```

## Prevention

- Keep deep-scrubbing enabled and tuned so every PG is checked within
  `osd_deep_scrub_interval` — scrubs are how you catch bit rot early.
- Monitor SMART and replace disks that throw read errors before they corrupt data.
- Use ECC RAM on OSD hosts; bad memory silently corrupts replicas.
- Never run pools at `min_size=1`; you need a majority to identify the good copy.

## Related Errors

- [Ceph PG Degraded / Undersized](./ceph-pg-degraded-undersized.md)
- [Ceph OSD Down and Out](./ceph-osd-down-and-out.md)

## References

- [Ceph: Repairing PG inconsistencies](https://docs.ceph.com/en/latest/rados/operations/pg-repair/)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`ceph` · `pg` · `scrub` · `data-integrity` · `production`
