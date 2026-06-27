---
title: "MySQL Unknown Database"
slug: mysql-unknown-database
technologies: [mysql]
severity: medium
tags: [mysql, schema, configuration, database, production]
related: [mysql-table-doesnt-exist, mysql-access-denied-for-user]
last_reviewed: 2026-06-27
---

# MySQL Unknown Database

## Error Message

```text
ERROR 1049 (42000): Unknown database 'appdb'
```

## Description

`ERROR 1049 (42000)` is returned when a client tries to select (or connect to) a
schema that does not exist on the server. It is raised either at connection time
(the DSN names a default database that is missing) or when running
`USE appdb;`/`CREATE TABLE appdb.foo`. It is purely a naming/existence problem —
the server is reachable and the credentials are valid, but the requested schema
is not present.

Like table names, database names are case-sensitive on case-sensitive
filesystems unless `lower_case_table_names` is configured, so `AppDB` and `appdb`
can be different — or missing — depending on the server.

## Technologies

- mysql (data dictionary / schema resolution)

## Severity

**medium** — the connection or statement fails, but it is almost always a
configuration/bootstrapping issue (wrong DSN, un-created schema) rather than data
loss. It can escalate to high if it blocks a production deploy from starting.

## Common Causes

1. The database was never created in this environment (fresh server, missing
   bootstrap/migration step).
2. A typo or case mismatch between the connection string and the real schema
   name.
3. The application is pointed at the wrong host/cluster (staging DSN in prod, or
   vice versa).
4. The database was dropped (cleanup script, accidental `DROP DATABASE`).
5. A restore created the schema under a different name.

## Root Cause Analysis

When a client connects with a default database, or issues `USE`, the server
checks `information_schema.schemata` for that name. If there is no matching row it
returns 1049 immediately — no tables are consulted. Because the schema list is
small and explicit, this error is unambiguous: the named database simply is not
on the server you reached. The frequent trap is environment drift, where the
schema exists in one cluster but the app is unknowingly connected to another.

## Diagnostic Commands

```bash
# List all schemas on the server you actually connected to
mysql -u app -p -e "SHOW DATABASES;"

# Authoritative existence check (and exact case) for the target name
mysql -u app -p -e "SELECT schema_name FROM information_schema.schemata \
  WHERE schema_name LIKE 'app%';"

# Confirm WHICH server/host you are really talking to
mysql -u app -p -e "SELECT @@hostname, @@port, @@version;"
```

## Expected Results

```text
+--------------------+
| Database           |
+--------------------+
| information_schema |
| mysql              |
| performance_schema |
| sys                |
+--------------------+
```

If `appdb` is absent from `SHOW DATABASES`, it does not exist here. If a
differently-cased `AppDB` appears, you have a case mismatch. If `@@hostname` is
not the server you expected, the DSN points at the wrong cluster.

## Resolution

1. If the schema is genuinely missing, create it (then run migrations to
   populate it):

   ```sql
   CREATE DATABASE appdb CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
   ```
2. If it is a typo/case issue, correct the database name in the connection
   string / config to match `information_schema.schemata` exactly.
3. If the app is pointed at the wrong server, fix the host in the DSN/secret and
   redeploy.
4. If a restore used a different name, either rename via dump/reload into the
   expected name or update the app to use the restored name.

## Validation

```bash
mysql -u app -p -e "USE appdb; SELECT DATABASE();"
# Expect 'appdb' returned with no ERROR 1049.
```

## Prevention

- Create schemas as an explicit, idempotent bootstrap step in CI/CD.
- Source database names from a single config/secret, never hand-typed per env.
- Keep `lower_case_table_names` consistent across all servers.
- Add a startup check that asserts the configured database exists.

## Related Errors

- [MySQL Table Doesn't Exist](./mysql-table-doesnt-exist.md)
- [MySQL Access Denied for User](./mysql-access-denied-for-user.md)

## References

- [MySQL: Server Error Reference (1049)](https://dev.mysql.com/doc/mysql-errors/8.0/en/server-error-reference.html)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`mysql` · `schema` · `configuration` · `database` · `production`
