---
title: "Redis MISCONF Unable to Persist RDB Snapshot"
slug: redis-misconf-rdb-snapshot-error
technologies: [redis]
severity: high
tags: [redis, persistence, rdb, misconf, production]
related: [redis-oom-command-not-allowed-maxmemory, redis-readonly-cant-write-against-replica]
last_reviewed: 2026-06-27
---

# Redis MISCONF Unable to Persist RDB Snapshot

## Error Message

```text
(error) MISCONF Redis is configured to save RDB snapshots, but it's currently
not able to persist on disk. Commands that may modify the data set are disabled,
because this instance is configured to report errors during writes if RDB
snapshotting fails (stop-writes-on-bgsave-error option). Please check the Redis
logs for details about the RDB error.
```

```text
1:M 27 Jun 2026 09:14:02.118 # Background saving error
1:M 27 Jun 2026 09:14:02.118 # Write error saving DB on disk: No space left on device
```

## Description

By default Redis sets `stop-writes-on-bgsave-error yes`. When a background save
(`BGSAVE`, triggered by the `save` rules or `BGSAVE`/`BGREWRITEAOF`) fails, Redis
refuses every write command and returns `MISCONF` to protect you from running
blind with a data set that can no longer be durably persisted. The data already
in memory is still readable, but all mutating commands (`SET`, `LPUSH`, `INCR`,
etc.) are rejected until the underlying persistence problem is fixed.

The most common trigger is a failed `bgsave` caused by a full disk, wrong
permissions on the `dir` directory, or the kernel refusing the `fork()` needed to
snapshot.

## Technologies

- redis (persistence / RDB / forked child)

## Severity

**high** — the instance becomes effectively read-only: every write fails. For a
primary serving live traffic this is a write outage even though reads still work.

## Common Causes

1. The disk holding the RDB `dir` is full (`No space left on device`).
2. The Redis process lacks write permission on the `dir` directory or the
   `dbfilename` path.
3. `fork()` for the background save fails because the host is low on memory or
   overcommit is disabled (`vm.overcommit_memory=0`).
4. The configured `dir` does not exist or points at a read-only mount.

## Root Cause Analysis

`BGSAVE` forks a child process that serializes the keyspace to a temporary file
and atomically renames it into place. If the child cannot write the file —
because the filesystem is full, the directory is not writable, or the fork
itself failed — Redis records the failed background save. With
`stop-writes-on-bgsave-error yes`, the next write command checks the last bgsave
status, sees the failure, and returns `MISCONF` rather than accepting data it
cannot durably store. The error therefore reflects a *host/OS* problem surfaced
through Redis, not a Redis bug.

## Diagnostic Commands

```bash
# Last save status, last failed bgsave, and changes since last save
redis-cli INFO persistence | grep -E 'rdb_last_bgsave_status|rdb_last_save_time|rdb_changes_since_last_save|aof_last_write_status'

# Where Redis writes the RDB and what file name it uses
redis-cli CONFIG GET dir
redis-cli CONFIG GET dbfilename
redis-cli CONFIG GET stop-writes-on-bgsave-error

# Free space and permissions on the data directory
df -h "$(redis-cli CONFIG GET dir | tail -1)"
ls -ld "$(redis-cli CONFIG GET dir | tail -1)"

# Persistence errors in the Redis log
journalctl -u redis-server --since "15 min ago" | grep -iE 'bgsave|rdb|disk|fork'
```

## Expected Results

```text
rdb_last_bgsave_status:err
rdb_changes_since_last_save:48213
aof_last_write_status:ok
```

`rdb_last_bgsave_status:err` confirms the failed snapshot. A `df -h` line showing
`100%` use or an `ls -ld` showing a directory not owned/writable by the `redis`
user pinpoints the cause. A healthy instance shows `rdb_last_bgsave_status:ok`.

## Resolution

1. Fix the underlying storage problem first — free disk space, expand the volume,
   or correct directory ownership:

   ```bash
   sudo chown redis:redis /var/lib/redis
   sudo chmod 750 /var/lib/redis
   ```
2. If `fork()` is failing for memory reasons, enable overcommit on the host:

   ```bash
   echo 'vm.overcommit_memory = 1' | sudo tee /etc/sysctl.d/99-redis.conf
   sudo sysctl -p /etc/sysctl.d/99-redis.conf
   ```
3. Force a successful snapshot to clear the error state:

   ```bash
   redis-cli BGSAVE
   ```
4. Once `BGSAVE` succeeds, writes are accepted again automatically. Do **not**
   simply disable `stop-writes-on-bgsave-error` to "fix" this — that hides real
   durability loss.

## Validation

```bash
redis-cli INFO persistence | grep rdb_last_bgsave_status
# Expect: rdb_last_bgsave_status:ok
redis-cli SET diag:probe ok
# Expect: OK  (no MISCONF)
```

## Prevention

- Alert on `rdb_last_bgsave_status` and on disk free percentage for the Redis
  data volume.
- Size the data volume for the worst-case RDB (roughly the size of the dataset)
  plus headroom for the temp file written during save.
- Set `vm.overcommit_memory=1` on dedicated Redis hosts so forks don't fail.
- Run Redis as a dedicated user that owns its `dir`.

## Related Errors

- [Redis OOM Command Not Allowed](./redis-oom-command-not-allowed-maxmemory.md)
- [Redis READONLY Can't Write Against a Replica](./redis-readonly-cant-write-against-replica.md)

## References

- [Redis persistence documentation](https://redis.io/docs/management/persistence/)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`redis` · `persistence` · `rdb` · `misconf` · `production`
