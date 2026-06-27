---
title: "MySQL Specified Key Was Too Long"
slug: mysql-specified-key-was-too-long
technologies: [mysql]
severity: medium
tags: [mysql, schema, indexing, charset, migrations]
related: [mysql-table-doesnt-exist, mysql-unknown-database]
last_reviewed: 2026-06-27
---

# MySQL Specified Key Was Too Long

## Error Message

```text
ERROR 1071 (42000): Specified key was too long; max key length is 767 bytes
```

```text
ERROR 1071 (42000): Specified key was too long; max key length is 3072 bytes
```

## Description

`ERROR 1071 (42000)` is raised at DDL time when an index (`PRIMARY KEY`,
`UNIQUE`, or regular index) exceeds InnoDB's maximum index-key length. The limit
is per-index *in bytes*, and the byte cost of a character column depends on its
character set: `utf8mb4` charges up to **4 bytes per character**, so a
`VARCHAR(255)` index costs up to 1020 bytes. The two limits you will see are
**767 bytes** (older InnoDB with `innodb_large_prefix` off / `REDUNDANT` or
`COMPACT` row format) and **3072 bytes** (modern default with `DYNAMIC` row
format and `innodb_large_prefix` on). This is the classic failure when migrating
a schema to `utf8mb4`.

## Technologies

- mysql (InnoDB index / DDL)

## Severity

**medium** — it blocks a schema migration or table creation; existing data is
untouched. It becomes high when it stops a production deploy that gates on the
migration completing.

## Common Causes

1. Indexing a wide `VARCHAR` under `utf8mb4` (e.g. `VARCHAR(255)` × 4 bytes =
   1020 bytes, over the 767 limit).
2. A composite index whose columns' byte lengths sum past the limit.
3. An old/`REDUNDANT`/`COMPACT` row format or `innodb_large_prefix=OFF` capping
   the limit at 767 bytes.
4. Migrating a table from `utf8` (3 bytes/char) to `utf8mb4` (4 bytes/char) so a
   previously-valid index now overflows.
5. Indexing a `TEXT`/`BLOB` column without specifying a prefix length.

## Root Cause Analysis

InnoDB stores index keys with a hard maximum length per index. The server
computes the *maximum possible* byte size of the indexed column(s) from their
declared length and character set — not the current data — and rejects the DDL if
that exceeds the limit. Because `utf8mb4` reserves 4 bytes per character, a
column that fit comfortably under `utf8`/`latin1` can overflow after a charset
change even though every actual value is short. The fix is to reduce the indexed
byte length, not to shrink the data.

## Diagnostic Commands

```bash
# What row format and large-prefix setting govern the 767 vs 3072 limit?
mysql -u root -p -e "SHOW VARIABLES LIKE 'innodb_default_row_format'; \
  SHOW VARIABLES LIKE 'innodb_large_prefix';"

# The column's declared length and charset (the byte cost driver)
mysql -u root -p -e "SELECT column_name, character_maximum_length, character_set_name, data_type \
  FROM information_schema.columns WHERE table_schema='appdb' AND table_name='users';"

# Current table's row format and engine
mysql -u root -p -e "SELECT table_name, engine, row_format FROM information_schema.tables \
  WHERE table_schema='appdb' AND table_name='users';"
```

## Expected Results

```text
+-----------+--------------------------+--------------------+
| column    | character_maximum_length | character_set_name |
+-----------+--------------------------+--------------------+
| email     | 255                      | utf8mb4            |
+-----------+--------------------------+--------------------+
```

`255 × 4 = 1020` bytes confirms the column overflows the 767-byte limit. If
`row_format` is `COMPACT`/`REDUNDANT` you are on the 767 limit; switching to
`DYNAMIC` raises it to 3072.

## Resolution

1. Prefer reducing the indexed column width to fit. For an email/username,
   `VARCHAR(191)` is the well-known `utf8mb4` ceiling under the 767 limit
   (`191 × 4 = 764`):

   ```sql
   ALTER TABLE appdb.users MODIFY email VARCHAR(191) NOT NULL;
   ```
2. Or index only a prefix of the column rather than the whole value:

   ```sql
   CREATE INDEX idx_email ON appdb.users (email(191));
   ```
3. Raise the limit to 3072 by ensuring the modern format (default on MySQL 8.0):

   ```sql
   ALTER TABLE appdb.users ROW_FORMAT=DYNAMIC;
   ```
   ```ini
   [mysqld]
   innodb_default_row_format = DYNAMIC
   ```
4. For `TEXT`/`BLOB`, always specify a prefix length in the index definition.

## Validation

```bash
mysql -u root -p -e "SHOW INDEX FROM appdb.users WHERE Key_name='idx_email';"
# Expect the index to exist (Sub_part shows the prefix length if used), no ERROR 1071.
```

## Prevention

- Use `VARCHAR(191)` (or prefix indexes) for indexed `utf8mb4` string columns on
  servers limited to 767 bytes.
- Default new tables to `ROW_FORMAT=DYNAMIC` and `innodb_large_prefix` on.
- Plan charset migrations to recompute index byte budgets before applying.
- Add a schema-lint CI check that flags indexes exceeding the byte limit.

## Related Errors

- [MySQL Table Doesn't Exist](./mysql-table-doesnt-exist.md)
- [MySQL Unknown Database](./mysql-unknown-database.md)

## References

- [MySQL: InnoDB Limits on Index Prefix Length](https://dev.mysql.com/doc/refman/8.0/en/innodb-limits.html)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`mysql` · `schema` · `indexing` · `charset` · `migrations`
