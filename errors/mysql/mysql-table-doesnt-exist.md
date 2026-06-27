---
title: "MySQL Table Doesn't Exist"
slug: mysql-table-doesnt-exist
technologies: [mysql]
severity: high
tags: [mysql, schema, migrations, table, production]
related: [mysql-unknown-database, mysql-specified-key-was-too-long]
last_reviewed: 2026-06-27
---

# MySQL Table Doesn't Exist

## Error Message

```text
ERROR 1146 (42S02): Table 'appdb.orders' doesn't exist
```

```text
ERROR 1932 (42S02): Table 'appdb.orders' doesn't exist in engine
```

## Description

`ERROR 1146 (42S02)` is returned when a statement references a table the server
cannot find in the named (or default) schema. `ERROR 1932` is the closely related
"doesn't exist *in engine*" variant: the `.frm`/data dictionary entry says the
table should be there, but the storage engine (usually InnoDB) has no matching
tablespace — a sign of a partially restored or corrupted data directory.

Table identifiers are case-sensitive on case-sensitive filesystems (Linux)
unless `lower_case_table_names` is set, so `Orders` and `orders` can be two
different — or missing — tables depending on the server's configuration.

## Technologies

- mysql (parser / data dictionary / storage engine)

## Severity

**high** — every query touching the missing table fails. If it is a core table,
the dependent feature or the whole application is down until the schema is
restored.

## Common Causes

1. A migration did not run, ran against the wrong schema, or was rolled back so
   the table was never created in this environment.
2. Case mismatch between the query and the actual table name on a
   case-sensitive filesystem.
3. The query omits the schema and the session's default database lacks the table
   (you are connected to the wrong database).
4. InnoDB tablespace files (`.ibd`) were lost or not restored, leaving the data
   dictionary pointing at a non-existent table (1932).
5. The table was dropped (by a cleanup job, a bad deploy, or a manual mistake).

## Root Cause Analysis

At parse/resolve time the server looks up the fully-qualified table name in the
data dictionary. If no entry exists it raises 1146 before touching any data. The
1932 variant happens later: the dictionary has the table but InnoDB fails to open
its tablespace, which typically follows a file-level copy that missed `.ibd`
files or a crash during `IMPORT TABLESPACE`. Because environments diverge,
the most common production cause is simply that the migration history applied in
staging never reached this server.

## Diagnostic Commands

```bash
# Confirm which database the session defaults to and what tables exist
mysql -u app -p -e "SELECT DATABASE(); SHOW TABLES FROM appdb;"

# Authoritative table list straight from the data dictionary
mysql -u app -p -e "SELECT table_name, engine FROM information_schema.tables \
  WHERE table_schema='appdb' ORDER BY table_name;"

# Orphaned-tablespace / engine errors are logged here (1932 cases)
sudo journalctl -u mysql --since "1 hour ago" | grep -iE "tablespace|orders"

# Is the .ibd file actually present on disk?
sudo ls -l /var/lib/mysql/appdb/ | grep -i orders
```

## Expected Results

```text
+------------+--------+
| table_name | engine |
+------------+--------+
| customers  | InnoDB |
| products   | InnoDB |
+------------+--------+
```

If `orders` is absent from `information_schema.tables`, the migration never ran
(1146). If it appears in the dictionary but `ls` shows no `orders.ibd`, you have
a missing tablespace (1932).

## Resolution

1. Verify your migration tool's applied-versions table and run the pending
   migrations against the correct schema:

   ```bash
   # Example: check applied migrations, then apply the missing ones
   mysql -u app -p -e "SELECT version FROM appdb.schema_migrations ORDER BY version;"
   ```
2. If it is a case-mismatch, query the real name, or set
   `lower_case_table_names=1` consistently across all servers (this must be set
   at initialization, not changed on a populated data directory).
3. If the session is on the wrong database, qualify the table
   (`appdb.orders`) or `USE appdb;`.
4. For 1932, restore the missing `.ibd` from backup, or recreate the table and
   re-import data. Never copy InnoDB files between live servers by hand.

## Validation

```bash
mysql -u app -p -e "SELECT COUNT(*) FROM appdb.orders;"
# Expect a row count, not ERROR 1146/1932.
```

## Prevention

- Run migrations as a gated, idempotent CI/CD step before app rollout.
- Fix `lower_case_table_names` once at install and keep it identical everywhere.
- Back up and restore InnoDB with a consistent tool (mysqldump, Percona XtraBackup)
  rather than file copies.
- Add a startup health check that asserts critical tables exist.

## Related Errors

- [MySQL Unknown Database](./mysql-unknown-database.md)
- [MySQL Specified Key Was Too Long](./mysql-specified-key-was-too-long.md)

## References

- [MySQL: Server Error Reference (1146)](https://dev.mysql.com/doc/mysql-errors/8.0/en/server-error-reference.html)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`mysql` · `schema` · `migrations` · `table` · `production`
