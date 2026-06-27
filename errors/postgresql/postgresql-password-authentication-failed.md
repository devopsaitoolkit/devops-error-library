---
title: "PostgreSQL Password Authentication Failed"
slug: postgresql-password-authentication-failed
technologies: [postgresql]
severity: medium
tags: [postgresql, authentication, security, credentials, production]
related: [postgresql-role-does-not-exist, postgresql-no-pg-hba-conf-entry]
last_reviewed: 2026-06-27
---

# PostgreSQL Password Authentication Failed

## Error Message

```text
FATAL:  password authentication failed for user "app_user"
```

```text
FATAL:  password authentication failed for user "app_user"
DETAIL:  Connection matched pg_hba.conf line 92: "host all all 0.0.0.0/0 scram-sha-256"
```

## Description

This `FATAL` is raised when a connection matched a password-based rule in
`pg_hba.conf` (`scram-sha-256`, `md5`, or `password`), the role exists, but the
supplied credential did not verify. It is distinct from `role does not exist`
(the role is missing entirely) and from `no pg_hba.conf entry` (no rule matched
at all). When server logging is verbose, the `DETAIL` line tells you exactly
which `pg_hba.conf` line and authentication method were applied — invaluable for
debugging. For security, the client message never says *why* the password was
wrong.

## Technologies

- postgresql (authentication, SCRAM/MD5 password verification, `pg_hba.conf`)

## Severity

**medium** — the affected user cannot log in; other roles and the server are
unaffected. Escalates to high when it locks out a critical service account.

## Common Causes

1. Wrong or stale password — a secret rotated in the database but not in the app
   (or vice versa). The most common cause.
2. `md5` vs `scram-sha-256` mismatch: the password was stored as an MD5 hash but
   the client/driver expects SCRAM (or an old driver cannot do SCRAM).
3. The application is reading the password from the wrong env/secret, or it
   contains characters mangled by shell/URL encoding in `DATABASE_URL`.
4. Whitespace or a trailing newline in a secret file injected as the password.
5. Connecting as a different role than intended (default to OS username via peer).

## Root Cause Analysis

PostgreSQL stores a verifier (not the plaintext) in `pg_authid.rolpassword`. For
SCRAM it runs a challenge-response that proves the client knows the password
without sending it; for `md5` it compares a salted hash. Authentication fails if
the verifier was generated from a different password, or if the stored verifier's
*algorithm* does not match what the connection's `pg_hba.conf` method/driver can
perform. A frequent silent trap is `password_encryption`: if a role's password
was set while `password_encryption = md5` but the HBA rule now demands
`scram-sha-256`, no SCRAM verifier exists and authentication fails until the
password is reset.

## Diagnostic Commands

```bash
# Which auth method applied? (read-only inspection of HBA rules)
psql -c "SELECT line_number, type, database, user_name, address, auth_method
         FROM pg_hba_file_rules WHERE auth_method IN ('scram-sha-256','md5','password');"

# What verifier algorithm is stored for the role? (superuser; shows scram vs md5)
sudo -u postgres psql -c "SELECT rolname,
         CASE WHEN rolpassword LIKE 'SCRAM-SHA-256%' THEN 'scram'
              WHEN rolpassword LIKE 'md5%' THEN 'md5' ELSE 'other' END AS verifier
         FROM pg_authid WHERE rolname = 'app_user';"

# Current encryption setting used when passwords are set
psql -c "SHOW password_encryption;"

# Confirm the failures in the server log with the matched HBA line
sudo journalctl -u postgresql --since "20 min ago" --no-pager | grep "authentication failed"
```

## Expected Results

```text
 rolname  | verifier
----------+----------
 app_user | md5        <- but HBA rule demands scram-sha-256: reset the password

# password_encryption:
 scram-sha-256
```

A `verifier` of `md5` while the HBA line requires `scram-sha-256` (or an obviously
wrong app secret) pinpoints the cause.

## Resolution

1. If the password is simply wrong/stale, reset it and update the application
   secret in the same change (avoid drift). Set it via `\password` so it is not
   written to history:

   ```sql
   \password app_user
   ```
2. For an algorithm mismatch, ensure `password_encryption = 'scram-sha-256'`, then
   **re-set** the password so a SCRAM verifier is generated:

   ```sql
   SET password_encryption = 'scram-sha-256';
   ALTER ROLE app_user PASSWORD 'redacted';
   ```
3. Trim hidden whitespace/newlines from secret files before injecting them.
4. Verify the app is reading the intended secret and the username is correct.

## Validation

```bash
PGPASSWORD='...' psql -h db.internal -U app_user -d appdb -c "SELECT current_user;"
# Expect a successful connection returning app_user; no FATAL in the log.
```

## Prevention

- Rotate the database password and the application secret atomically.
- Standardize on `scram-sha-256` and ensure all drivers support it before cutover.
- Store secrets in a manager; never embed them in URLs or commit them.
- Alert on a spike of `authentication failed` log lines (also catches credential attacks).

## Related Errors

- [PostgreSQL role does not exist](./postgresql-role-does-not-exist.md)
- [PostgreSQL no pg_hba.conf entry](./postgresql-no-pg-hba-conf-entry.md)

## References

- [PostgreSQL: Password Authentication](https://www.postgresql.org/docs/current/auth-password.html)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`postgresql` · `authentication` · `security` · `credentials` · `production`
