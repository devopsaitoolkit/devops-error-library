---
title: "PostgreSQL Could Not Extend File — No Space Left on Device"
slug: postgresql-could-not-extend-file-no-space
technologies: [postgresql]
severity: critical
tags: [postgresql, storage, disk, capacity, production]
related: [postgresql-too-many-connections, postgresql-canceling-statement-due-to-statement-timeout]
last_reviewed: 2026-06-27
---

# PostgreSQL Could Not Extend File — No Space Left on Device

## Error Message

```text
ERROR:  could not extend file "base/16384/24591": No space left on device
HINT:  Check free disk space.
```

```text
PANIC:  could not write to file "pg_wal/xlogtemp.18233": No space left on device
```

## Description

PostgreSQL stores tables and indexes as files under the data directory and grows
them in 8 KB blocks as data is inserted. When a write needs a new block and the
underlying filesystem reports `ENOSPC`, the `ERROR: could not extend file`
message is returned and the statement aborts. Far more dangerous is the WAL
variant: if the `pg_wal` directory cannot be written, PostgreSQL cannot guarantee
durability and will `PANIC` and shut down to protect data integrity. This is one
of the few errors that can take the whole cluster offline.

## Technologies

- postgresql (storage manager, WAL writer)

## Severity

**critical** — write transactions fail, and a full `pg_wal` partition crashes the
entire instance. Recovery may be blocked until space is freed, making this a
self-perpetuating outage.

## Common Causes

1. The data volume genuinely filled — organic growth without capacity alerting.
2. WAL accumulation: an inactive replication slot, failed archiving
   (`archive_command` returning non-zero), or `wal_keep_size` retaining segments.
3. A long-running transaction (or abandoned `idle in transaction`) blocking
   autovacuum, causing table/index bloat to consume the disk.
4. A runaway query writing massive temporary files to `base/pgsql_tmp`.
5. Logs, core dumps, or another service on the same partition eating the space.

## Root Cause Analysis

The block allocator calls into the OS to extend a relation's file; the kernel
returns `ENOSPC`, which the storage manager surfaces verbatim. For ordinary
relation files this is recoverable — the transaction rolls back and the server
keeps running. WAL is different: every committed change must reach `pg_wal`
before it is acknowledged, so an inability to write there violates the durability
contract, and PostgreSQL deliberately `PANIC`s rather than risk silent data loss.
The most common *hidden* cause is a stale replication slot: PostgreSQL refuses to
recycle WAL segments a slot still claims, so `pg_wal` grows without bound even
though everything looks healthy.

## Diagnostic Commands

```bash
# Filesystem usage — which mount is full?
df -h /var/lib/pgsql/data

# Largest space consumers under the data directory
sudo du -sh /var/lib/pgsql/data/* 2>/dev/null | sort -rh | head

# WAL directory size (does pg_wal dominate?)
sudo du -sh /var/lib/pgsql/data/pg_wal

# Inactive replication slots pinning WAL
psql -c "SELECT slot_name, active, restart_lsn,
         pg_size_pretty(pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn)) AS retained
         FROM pg_replication_slots ORDER BY retained DESC;"

# Largest databases / relations
psql -c "SELECT datname, pg_size_pretty(pg_database_size(datname)) FROM pg_database ORDER BY pg_database_size(datname) DESC;"
```

## Expected Results

```text
Filesystem      Size  Used Avail Use% Mounted on
/dev/nvme1n1    200G  200G    0G 100% /var/lib/pgsql/data   <- full

 slot_name   | active | retained
-------------+--------+----------
 old_replica | f      | 84 GB     <- inactive slot pinning 84 GB of WAL
```

## Resolution

1. Free space safely first. If `pg_wal` is the culprit and an inactive slot is
   pinning it, drop the obsolete slot (confirm the replica is truly gone):

   ```sql
   SELECT pg_drop_replication_slot('old_replica');
   ```
   PostgreSQL then recycles the orphaned WAL automatically.
2. If archiving is failing, fix `archive_command` so WAL can be released, and
   check the server log for the failure reason.
3. Remove non-database files on the partition (old logs, dumps) to buy headroom —
   never delete files inside `pg_wal` or the data directory by hand.
4. Expand the volume (grow the disk + filesystem) for genuine capacity growth.
5. After space is restored, if the server `PANIC`ed, start it; it will perform
   crash recovery and replay WAL.

## Validation

```bash
df -h /var/lib/pgsql/data   # Expect Use% well below 100%, free space available
pg_isready                  # Expect: accepting connections
psql -c "CREATE TEMP TABLE _t AS SELECT 1; DROP TABLE _t;"  # write succeeds
```

## Prevention

- Alert on disk usage at 75% / 85% with enough lead time to act before 100%.
- Monitor `pg_replication_slots` for inactive slots and `pg_stat_archiver` for
  archiving failures.
- Put `pg_wal` on its own volume so a WAL spike does not crash the whole instance.
- Keep autovacuum healthy so bloat does not silently consume the disk.

## Related Errors

- [PostgreSQL too many connections](./postgresql-too-many-connections.md)
- [PostgreSQL canceling statement due to statement timeout](./postgresql-canceling-statement-due-to-statement-timeout.md)

## References

- [PostgreSQL: Reliability and the Write-Ahead Log](https://www.postgresql.org/docs/current/wal-intro.html)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`postgresql` · `storage` · `disk` · `wal` · `production`
