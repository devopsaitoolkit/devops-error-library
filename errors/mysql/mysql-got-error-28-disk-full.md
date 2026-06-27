---
title: "MySQL Got Error 28 From Storage Engine (Disk Full)"
slug: mysql-got-error-28-disk-full
technologies: [mysql]
severity: critical
tags: [mysql, disk, storage, capacity, production]
related: [mysql-too-many-connections, mysql-aborted-connection]
last_reviewed: 2026-06-27
---

# MySQL Got Error 28 From Storage Engine (Disk Full)

## Error Message

```text
ERROR 1030 (HY000): Got error 28 from storage engine
```

```text
[ERROR] [MY-011953] InnoDB: Disk is full writing './ibtmp1' (Errcode: 28 - No space left on device)
```

## Description

`ERROR 1030 (HY000)` with OS errno **28** is the MySQL surfacing of the system
`ENOSPC` ("No space left on device"). The storage engine tried to write — a row,
an index page, a temporary file, a binary log, or the redo/undo log — and the
underlying filesystem had no free space (or no free inodes). Because MySQL needs
scratch space for sorts, temp tables, and the binary log even for read-heavy
workloads, a full disk can break `SELECT`s as well as writes.

## Technologies

- mysql (storage engine / filesystem)

## Severity

**critical** — writes fail, temp-table queries fail, and replication can stall
when the binary log cannot grow. A full data disk risks a hard stop and, in the
worst case, corruption on an unclean shutdown.

## Common Causes

1. The data directory (`/var/lib/mysql`) filled with table and InnoDB data.
2. Binary logs (`binlog.*`) accumulated because `binlog_expire_logs_seconds` /
   `expire_logs_days` was never set or is too long.
3. A runaway query built a huge on-disk temporary table or sort file in `tmpdir`.
4. The general/slow query log or error log grew unbounded.
5. Inode exhaustion — space appears free but `df -i` shows 100% inodes used
   (many tiny files).

## Root Cause Analysis

Every engine write ultimately becomes a `write()`/`pwrite()` syscall; when the
filesystem returns `ENOSPC`, the engine propagates errno 28 up as 1030. InnoDB
also pre-allocates and grows shared files (`ibtmp1`, redo logs, the system
tablespace), so it can hit `ENOSPC` even when individual tables are small.
Binary logs are the most common silent space consumer: they grow with write
volume and are only removed by an explicit expiry policy or `PURGE BINARY LOGS`.

## Diagnostic Commands

```bash
# Free space and free inodes on the MySQL data filesystem
df -h /var/lib/mysql
df -i /var/lib/mysql

# Where the data dir and tmpdir actually live
mysql -u root -p -e "SHOW VARIABLES WHERE Variable_name IN ('datadir','tmpdir','log_bin_basename');"

# Largest consumers under the data directory
sudo du -h --max-depth=1 /var/lib/mysql | sort -rh | head

# Confirm the disk-full message in the log
sudo journalctl -u mysql --since "30 min ago" | grep -i "No space left"
```

## Expected Results

```text
Filesystem      Size  Used Avail Use% Mounted on
/dev/nvme1n1    100G  100G   20K 100% /var/lib/mysql
```

`Use% 100%` confirms space exhaustion; if `df -h` shows space but `df -i` shows
`IUse% 100%`, the problem is inodes, not bytes. A large `binlog.*` total in
`du` points at log accumulation.

## Resolution

1. Reclaim space *safely* — never delete raw `.ibd`/`ibdata` files. Purge old
   binary logs through MySQL so the index stays consistent:

   ```sql
   PURGE BINARY LOGS BEFORE NOW() - INTERVAL 3 DAY;
   ```
2. Truncate or rotate oversized text logs (general/slow log) and old error logs.
3. Set an expiry policy so binlogs are reclaimed automatically:

   ```ini
   [mysqld]
   binlog_expire_logs_seconds = 259200   # 3 days
   ```
4. If the data set legitimately outgrew the disk, grow the volume / migrate
   `datadir` to a larger filesystem during a maintenance window.
5. Reclaim space from a bloated tablespace with `OPTIMIZE TABLE` (rebuilds; needs
   temporary free space) once headroom exists.

## Validation

```bash
df -h /var/lib/mysql && mysql -u root -p -e "SELECT 1 INTO @x; CREATE TEMPORARY TABLE t(i INT); DROP TABLE t;"
# Expect free space restored and the write/temp-table test to succeed (no error 28).
```

## Prevention

- Alert on filesystem usage at 75%/85% for the data and binlog volumes.
- Always configure `binlog_expire_logs_seconds`.
- Cap `tmpdir` growth and watch for queries spilling large temp tables to disk.
- Monitor inodes, not just bytes.

## Related Errors

- [MySQL Too Many Connections](./mysql-too-many-connections.md)
- [MySQL Aborted Connection](./mysql-aborted-connection.md)

## References

- [MySQL: Server Error Reference (1030)](https://dev.mysql.com/doc/mysql-errors/8.0/en/server-error-reference.html)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`mysql` · `disk` · `storage` · `capacity` · `production`
