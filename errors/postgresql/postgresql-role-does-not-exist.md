---
title: "PostgreSQL Role Does Not Exist"
slug: postgresql-role-does-not-exist
technologies: [postgresql]
severity: medium
tags: [postgresql, authentication, roles, provisioning, production]
related: [postgresql-password-authentication-failed, postgresql-database-does-not-exist]
last_reviewed: 2026-06-27
---

# PostgreSQL Role Does Not Exist

## Error Message

```text
FATAL:  role "app_user" does not exist
```

```text
ERROR:  role "reporting" does not exist
```

## Description

PostgreSQL authenticates and authorizes via *roles* (the unified concept that
covers both users and groups). The `FATAL` form appears at connection time when
the login role named in the connection string has no matching entry in the
`pg_roles` catalog — the server rejects the session before any password check.
The `ERROR` form appears inside a session when a statement (`GRANT`, `ALTER`,
`SET ROLE`, `REASSIGN OWNED`) references a role that does not exist. In both
cases the named role was never created, was dropped, or is spelled/cased
differently than expected.

## Technologies

- postgresql (authentication, role catalog `pg_authid` / `pg_roles`)

## Severity

**medium** — the specific user or operation fails, but the server and other roles
are unaffected. It becomes high if it blocks a critical service account from
logging in.

## Common Causes

1. The role was never provisioned (new environment, missed migration/bootstrap
   step) — the most common case.
2. Case sensitivity: the role was created quoted as `"App_User"` but the client
   connects as `app_user`; unquoted identifiers fold to lower case.
3. The role was dropped (cleanup, a rerun of teardown scripts) and not recreated.
4. Connecting to the wrong cluster/instance where that role does not exist.
5. A typo in the username field of the connection string or `DATABASE_URL`.

## Root Cause Analysis

At connection time the postmaster looks up the supplied user name in
`pg_authid`. Because PostgreSQL folds unquoted identifiers to lower case but
preserves case for double-quoted ones, a role created as `CREATE ROLE "App"` is
named `App`, and connecting as `App` (which libpq passes verbatim) works while
`app` does not. This case mismatch is the most-missed cause. For the in-session
`ERROR`, the planner resolves the role name against the catalog when executing
the DDL, so any statement that names a non-existent role fails the same way.

## Diagnostic Commands

```bash
# Does the role exist at all? (exact, case-sensitive match)
psql -c "SELECT rolname, rolcanlogin, rolsuper FROM pg_roles WHERE rolname = 'app_user';"

# List all login-capable roles to spot casing/typos
psql -c "SELECT rolname, rolcanlogin FROM pg_roles ORDER BY rolname;"

# Confirm which cluster/database you are actually connected to
psql -c "SELECT current_database(), inet_server_addr(), inet_server_port();"

# \du equivalent for a quick human-readable list
psql -c "\du"
```

## Expected Results

```text
 rolname  | rolcanlogin | rolsuper
----------+-------------+----------
(0 rows)            <- role genuinely absent

 rolname  | rolcanlogin
----------+-------------
 App_User | t           <- exists, but mixed case: connect as "App_User", not app_user
```

## Resolution

1. Create the missing login role (use a secret-managed password, never a literal
   in shell history):

   ```sql
   CREATE ROLE app_user LOGIN PASSWORD 'redacted';
   GRANT CONNECT ON DATABASE appdb TO app_user;
   ```
2. If the cause is casing, either recreate the role unquoted, or connect using the
   exact quoted name the role was created with.
3. If the role should have been provisioned by a migration, run/repair the
   bootstrap that owns role creation rather than hand-creating it (keeps IaC the
   source of truth).
4. For dropped roles that owned objects, recreate then `REASSIGN OWNED` as needed.

## Validation

```bash
psql -c "SELECT 1 FROM pg_roles WHERE rolname = 'app_user';"
psql -U app_user -d appdb -c "SELECT current_user;"
# Expect the role to appear and the login to succeed.
```

## Prevention

- Provision roles through versioned migrations/IaC so every environment matches.
- Standardize on lower-case, unquoted role names to avoid case-sensitivity traps.
- Add a smoke test after deploy that logs in as each service role.

## Related Errors

- [PostgreSQL password authentication failed](./postgresql-password-authentication-failed.md)
- [PostgreSQL database does not exist](./postgresql-database-does-not-exist.md)

## References

- [PostgreSQL: Database Roles](https://www.postgresql.org/docs/current/user-manag.html)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`postgresql` · `authentication` · `roles` · `provisioning` · `production`
