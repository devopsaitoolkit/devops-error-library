---
title: "PostgreSQL Relation Does Not Exist"
slug: postgresql-relation-does-not-exist
technologies: [postgresql]
severity: medium
tags: [postgresql, schema, search-path, migrations, production]
related: [postgresql-database-does-not-exist, postgresql-role-does-not-exist]
last_reviewed: 2026-06-27
---

# PostgreSQL Relation Does Not Exist

## Error Message

```text
ERROR:  relation "orders" does not exist
LINE 1: SELECT * FROM orders WHERE status = 'open';
                      ^
```

```text
ERROR:  relation "public.orders" does not exist
```

## Description

In PostgreSQL a *relation* is a table, view, materialized view, sequence, or
index. This `ERROR` is the planner reporting that an unqualified or qualified
name in a query does not resolve to any relation visible to the session. The
caret (`^`) points at the offending name. Crucially, "does not exist" often means
"not found on the current `search_path`" rather than "absent from the database" —
the object may exist in a schema the session is not looking in. It is one of the
most common errors after a missed migration or a schema/`search_path` mismatch.

## Technologies

- postgresql (query planner, schema/search_path resolution)

## Severity

**medium** — the failing query (and the feature behind it) breaks, but the
database and other queries are unaffected. High if it blocks a core code path on
every request.

## Common Causes

1. The migration that creates the table has not run in this environment — the most
   common cause.
2. `search_path` does not include the schema the object lives in (e.g. object is
   in `app` but `search_path` is `"$user", public`).
3. Schema-qualification mismatch: the object is `reporting.orders` but the query
   says just `orders`.
4. Case sensitivity: the table was created as `"Orders"` (quoted) but queried as
   `orders`, which folds to lower case.
5. Connected to the wrong database where the table does not exist.

## Root Cause Analysis

When the planner sees an unqualified relation name, it walks the session's
`search_path` schema by schema and uses the first matching relation; if none
matches, it raises this error. A schema-qualified name is resolved directly and
fails only if that exact schema.relation pair is absent. Because object names are
folded to lower case unless double-quoted at creation time, `CREATE TABLE
"Orders"` produces a relation that an unquoted `SELECT ... FROM Orders` cannot
find. The practical first question is always: *does the relation exist somewhere,
and is its schema on my search_path?*

## Diagnostic Commands

```bash
# Where (which schema) does the relation actually live?
psql -d appdb -c "SELECT schemaname, tablename FROM pg_tables WHERE tablename = 'orders';"

# Broader: any relation by this name across schemas, with type
psql -d appdb -c "SELECT n.nspname AS schema, c.relname, c.relkind
                  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
                  WHERE c.relname = 'orders';"

# What is the session's search_path?
psql -d appdb -c "SHOW search_path;"

# List tables visible in the current schema scope
psql -d appdb -c "\dt"
```

## Expected Results

```text
 schema    | relname | relkind
-----------+---------+---------
 reporting | orders  | r        <- exists in 'reporting', not on default search_path

# search_path:
 "$user", public                <- 'reporting' is missing here
```

If `pg_class` shows the relation under a schema absent from `search_path`, the
table exists — the session just is not looking there.

## Resolution

1. If the table is genuinely missing, run the migration that creates it (do not
   hand-create production schema):

   ```bash
   # run your migration tool, e.g.:
   # flyway migrate   /   alembic upgrade head   /   dbmate up
   ```
2. If it exists in another schema, either schema-qualify the query or set the
   role's `search_path` so the schema is found:

   ```sql
   ALTER ROLE app_user SET search_path = app, public;   -- persistent per role
   -- or qualify explicitly:
   SELECT * FROM reporting.orders;
   ```
3. For a case-sensitivity mismatch, quote the name to match how it was created, or
   recreate it unquoted (lower case) and update queries.
4. Confirm you are connected to the correct database before deeper digging.

## Validation

```bash
psql -d appdb -c "SELECT to_regclass('orders');"   -- non-null when resolvable
psql -d appdb -c "SELECT count(*) FROM orders;"     -- query now succeeds
```

## Prevention

- Apply schema changes only through versioned migrations run in every environment.
- Set a deterministic `search_path` per role rather than relying on the default.
- Use lower-case, unquoted identifiers consistently.
- Add a post-migration smoke test that selects from the tables the app needs.

## Related Errors

- [PostgreSQL database does not exist](./postgresql-database-does-not-exist.md)
- [PostgreSQL role does not exist](./postgresql-role-does-not-exist.md)

## References

- [PostgreSQL: Schemas and the search_path](https://www.postgresql.org/docs/current/ddl-schemas.html)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`postgresql` · `schema` · `search-path` · `migrations` · `production`
