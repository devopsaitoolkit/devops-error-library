---
title: "PostgreSQL Database Does Not Exist"
slug: postgresql-database-does-not-exist
technologies: [postgresql]
severity: medium
tags: [postgresql, provisioning, connectivity, configuration, production]
related: [postgresql-role-does-not-exist, postgresql-relation-does-not-exist]
last_reviewed: 2026-06-27
---

# PostgreSQL Database Does Not Exist

## Error Message

```text
FATAL:  database "appdb" does not exist
```

```text
psql: error: connection to server at "db.internal" (10.0.3.21), port 5432 failed:
FATAL:  database "appdb" does not exist
```

## Description

PostgreSQL is a multi-database server: a connection must target one specific
database, named in the connection string (or defaulting to the connecting user's
name). When the postmaster cannot find that database in the `pg_database`
catalog, it rejects the connection with `FATAL: database "..." does not exist`.
The role authenticated successfully and the server is reachable — only the target
database is missing, misnamed, or lives on a different cluster. A common surprise:
with no `dbname` given, `psql`/libpq defaults the database name to the **user
name**, producing this error for a user that has no like-named database.

## Technologies

- postgresql (postmaster, database catalog `pg_database`)

## Severity

**medium** — the targeted application cannot connect, but the server and other
databases keep running. High if it blocks a production service entirely.

## Common Causes

1. The database was never created in this environment (missed bootstrap/migration).
2. A typo or case mismatch in `dbname` / `DATABASE_URL` (`appdb` vs `app_db`).
3. No `dbname` supplied, so libpq defaulted to the user name, which has no DB.
4. Connecting to the wrong cluster/host where that database does not exist.
5. The database was dropped (teardown rerun, manual cleanup) and not recreated.

## Root Cause Analysis

After authentication, the backend resolves the requested database name against
`pg_database` to locate its files and OID. If the lookup returns nothing, the
session is refused before any SQL runs. Because the lookup is exact and
case-sensitive for quoted names, a database created as `"AppDB"` will not match a
client asking for `appdb`. The defaulting behavior is the most-missed cause:
omitting `dbname` is silently equivalent to `dbname=<username>`, so a `psql -U
deploy` with no database tries to open a `deploy` database that does not exist.

## Diagnostic Commands

```bash
# Does the database exist? (connect to the always-present 'postgres' db to ask)
psql -d postgres -c "SELECT datname FROM pg_database WHERE datname = 'appdb';"

# List every database to spot typos/casing
psql -d postgres -c "SELECT datname, datistemplate FROM pg_database ORDER BY datname;"
# or
psql -d postgres -c "\l"

# Confirm which cluster you reached (host/port) and the default db being used
psql -d postgres -c "SELECT inet_server_addr(), inet_server_port();"
```

## Expected Results

```text
 datname
---------
(0 rows)              <- 'appdb' truly absent on this cluster

 datname    | datistemplate
------------+---------------
 app_db     | f             <- exists, but the client asked for 'appdb' (typo)
 postgres   | f
 template1  | t
```

## Resolution

1. Create the database (set the right owner so the app role can use it):

   ```sql
   CREATE DATABASE appdb OWNER app_user;
   ```
2. If it is a typo/case issue, correct `dbname`/`DATABASE_URL` to the exact
   existing name rather than creating a duplicate.
3. Always pass an explicit database to avoid the username-default trap:

   ```bash
   psql -h db.internal -U deploy -d appdb
   ```
4. If provisioning should be automated, run the migration/bootstrap that owns
   database creation instead of hand-creating it.

## Validation

```bash
psql -d postgres -c "SELECT 1 FROM pg_database WHERE datname = 'appdb';"
psql -h db.internal -U app_user -d appdb -c "SELECT current_database();"
# Expect the database to be listed and the connection to succeed.
```

## Prevention

- Create databases through versioned migrations/IaC so every environment matches.
- Always set an explicit `dbname` in connection strings; never rely on the default.
- Use lower-case unquoted database names to dodge case-sensitivity issues.
- Add a post-deploy smoke test that connects to each expected database.

## Related Errors

- [PostgreSQL role does not exist](./postgresql-role-does-not-exist.md)
- [PostgreSQL relation does not exist](./postgresql-relation-does-not-exist.md)

## References

- [PostgreSQL: Managing Databases](https://www.postgresql.org/docs/current/managing-databases.html)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`postgresql` · `provisioning` · `connectivity` · `configuration` · `production`
