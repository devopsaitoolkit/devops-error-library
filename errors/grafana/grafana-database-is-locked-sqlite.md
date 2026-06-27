---
title: "Grafana Database Is Locked (SQLite)"
slug: grafana-database-is-locked-sqlite
technologies: [grafana]
severity: high
tags: [grafana, database, sqlite, locking, production]
related: [grafana-failed-to-load-dashboards, grafana-invalid-username-or-password]
last_reviewed: 2026-06-27
---

# Grafana Database Is Locked (SQLite)

## Error Message

```text
t=2026-06-24T13:47:52+0000 lvl=eror msg="Failed to save dashboard" logger=context error="database is locked"
```

```text
[sqlite] database is locked (5) (SQLITE_BUSY)
```

```text
{"message":"database is locked","traceID":""}
```

## Description

Grafana's default backend store is a single SQLite file (`grafana.db`). SQLite
allows only one writer at a time and locks the whole database file during a write.
Under concurrent writes — many users saving dashboards, frequent alert-state
writes, an external process touching the file — writers that cannot acquire the
lock within the busy-timeout fail with **database is locked** (`SQLITE_BUSY`).
This manifests as failed dashboard saves, login/session writes, or alerting
errors. It is a scaling/concurrency limit of SQLite, not corruption.

## Technologies

- grafana (xorm / SQLite backend store)

## Severity

**high** — write operations (saving dashboards, sessions, alert state) fail
intermittently; under sustained load Grafana becomes unreliable. Read-only
viewing may still work, masking the problem.

## Common Causes

1. Multiple Grafana writers against one SQLite file — e.g. two replicas/pods
   sharing the same volume (SQLite does not support this).
2. High write concurrency from alerting state, annotations, or many simultaneous
   dashboard saves.
3. The DB file lives on slow or networked storage (NFS), where locks are slow or
   unreliable.
4. An external process (backup tool, manual `sqlite3` write session) holds a lock
   on the file.
5. `busy_timeout` / WAL mode not configured, so writers give up immediately.

## Root Cause Analysis

SQLite uses file-level locking. A write acquires an exclusive lock; any other
write must wait. Grafana retries for up to the configured busy-timeout, then
returns `SQLITE_BUSY` → "database is locked". The classic production trigger is
running more than one Grafana instance on a shared file (e.g. a scaled-up
Deployment on a single PVC): two processes contend for the same lock and both
intermittently fail. NFS makes it worse because POSIX locks are unreliable there.

## Diagnostic Commands

```bash
# Lock/SQLITE_BUSY errors in the log
journalctl -u grafana-server --since "30 min ago" | grep -i "database is locked\|SQLITE_BUSY"

# Confirm the configured database type and path (read-only)
grep -A6 "\[database\]" /etc/grafana/grafana.ini

# Which processes have the DB file open (more than one Grafana = the bug)
sudo lsof /var/lib/grafana/grafana.db

# Read-only integrity + journal mode check (does NOT take a write lock)
sqlite3 -readonly /var/lib/grafana/grafana.db "PRAGMA journal_mode; PRAGMA integrity_check;"

# Storage backing the DB (watch for nfs)
df -hT /var/lib/grafana
```

## Expected Results

```text
COMMAND   PID    USER   ...  NAME
grafana  1411  grafana  ...  /var/lib/grafana/grafana.db
grafana  3098  grafana  ...  /var/lib/grafana/grafana.db   <-- second writer = the problem
```

Two `grafana` processes holding the file confirms multi-writer contention. `df
-hT` showing `nfs` indicates unreliable locking. `integrity_check` returning `ok`
confirms the data is fine — this is a locking, not corruption, issue.

## Resolution

1. **Run exactly one Grafana writer per SQLite file.** Scale the Deployment to a
   single replica, or — the right long-term fix — migrate to an external,
   concurrent database (PostgreSQL or MySQL):

   ```ini
   [database]
   type = postgres
   host = grafana-db.internal:5432
   name = grafana
   user = grafana
   password = ${GF_DB_PASSWORD}
   ```
   Migrate the data, then restart. This removes the single-writer limit entirely.
2. If you must stay on SQLite, enable WAL and a busy timeout to absorb short
   contention:

   ```ini
   [database]
   wal = true
   ```
3. Move `grafana.db` off NFS onto local/block storage.
4. Ensure no external process writes to the file (back it up against a copy, not
   the live file).

## Validation

```bash
# Only one Grafana process holds the DB file
sudo lsof /var/lib/grafana/grafana.db | grep -c grafana   # Expect: 1 (SQLite mode)

# Saves succeed without lock errors afterward
journalctl -u grafana-server --since "5 min ago" | grep -i "database is locked" || echo "no lock errors"
```

## Prevention

- Use PostgreSQL/MySQL for any HA, multi-replica, or write-heavy Grafana.
- Never schedule more than one Grafana replica on a shared SQLite volume.
- Keep the Grafana DB on local/block storage with WAL enabled.

## Related Errors

- [Grafana Failed to Load Dashboards](./grafana-failed-to-load-dashboards.md)
- [Grafana Invalid Username or Password](./grafana-invalid-username-or-password.md)

## References

- [Grafana database configuration](https://grafana.com/docs/grafana/latest/setup-grafana/configure-grafana/#database)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`grafana` · `database` · `sqlite` · `locking` · `production`
