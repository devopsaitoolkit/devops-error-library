---
title: "Prometheus TSDB No Space Left on Device"
slug: prometheus-tsdb-no-space-left-on-device
technologies: [prometheus]
severity: critical
tags: [prometheus, tsdb, storage, disk, production]
related: [prometheus-too-many-open-files, prometheus-oomkilled-high-cardinality]
last_reviewed: 2026-06-27
---

# Prometheus TSDB No Space Left on Device

## Error Message

```text
level=error component=tsdb msg="Failed to write to WAL" err="write /prometheus/wal/00001234: no space left on device"
```

A compaction variant:

```text
level=error component=tsdb msg="compaction failed" err="... no space left on device"
```

## Description

Prometheus continuously writes incoming samples to a write-ahead log (WAL) and
periodically compacts the head block into persistent blocks under its data
directory. When the filesystem holding that directory fills up, every WAL append
and compaction fails with `no space left on device` (ENOSPC). Ingestion stalls,
the head can no longer be flushed, and if the WAL cannot be written the process
may crash on restart. This is one of the few Prometheus failures that risks
actual data loss.

## Technologies

- prometheus (TSDB, WAL, compactor)

## Severity

**critical** — sample ingestion stops, alerting may go silent, and unflushed
head data can be lost if the process dies before space is recovered. A full
monitoring disk during an incident leaves you blind.

## Common Causes

1. Retention (`--storage.tsdb.retention.time` / `.size`) is larger than the disk
   can hold given current ingestion volume.
2. A cardinality explosion grew the head and blocks far beyond the planned size.
3. The volume was sized for old traffic and series count has since grown.
4. A failed compaction left temporary `*.tmp` directories consuming space.

## Root Cause Analysis

Disk usage is driven by `bytes_per_sample × samples_per_second × retention`,
plus WAL and compaction overhead. Compaction needs free headroom to write a new
block before deleting the old ones, so the practical ceiling is below 100% — a
disk that is "only" 90% full can still fail compaction. When `write()` returns
ENOSPC, the TSDB cannot durably record samples; it logs the error and, depending
on the failing path, either drops the write or halts. Retention deletion only
runs after compaction, so a wedged compactor cannot free space on its own.

## Diagnostic Commands

```bash
# Filesystem usage for the data directory
df -h /prometheus

# Where the space went: blocks, WAL, chunks
du -sh /prometheus/* 2>/dev/null | sort -h | tail

# TSDB head stats and on-disk status
curl -s http://localhost:9090/api/v1/status/tsdb | jq '.data.headStats'

# Recent storage errors from the journal
journalctl -u prometheus --since "-30min" | grep -i "no space\|compaction\|wal"
```

## Expected Results

```text
Filesystem      Size  Used Avail Use% Mounted on
/dev/nvme1n1    200G  200G     0 100% /prometheus
```

`Use% 100%` (or high enough to block compaction) with ENOSPC lines in the
journal confirms the cause. `du` typically shows the bulk under `/prometheus`
block directories or a large `wal/`.

## Resolution

1. Free space immediately. The safe lever is to lower retention so old blocks
   are deleted on the next compaction:
   `--storage.tsdb.retention.time=15d` (or set `.size` below disk capacity).
2. If space is critically gone, expand the volume (grow the disk and
   filesystem) — preferred over deleting blocks by hand.
3. Reduce ingestion: drop high-cardinality series via `metric_relabel_configs`
   so the head and future blocks shrink.
4. Avoid manually deleting block directories while Prometheus runs; use the
   admin delete API or let retention reclaim space.

## Validation

```bash
# Disk should have headroom and ingestion resume
df -h /prometheus
curl -s 'http://localhost:9090/api/v1/query?query=rate(prometheus_tsdb_head_samples_appended_total[1m])' \
  | jq '.data.result[].value[1]'   # Expect a non-zero append rate
```

## Prevention

- Set `--storage.tsdb.retention.size` to ~80% of the volume so compaction always
  has headroom.
- Alert on `(node_filesystem_avail_bytes / node_filesystem_size_bytes) < 0.2`
  for the Prometheus mount.
- Monitor head series count to catch cardinality growth before it fills disk.

## Related Errors

- [Prometheus Too Many Open Files](./prometheus-too-many-open-files.md)
- [Prometheus OOMKilled from High Cardinality](./prometheus-oomkilled-high-cardinality.md)

## References

- [Prometheus: Storage operational aspects](https://prometheus.io/docs/prometheus/latest/storage/#operational-aspects)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`prometheus` · `tsdb` · `storage` · `disk` · `production`
