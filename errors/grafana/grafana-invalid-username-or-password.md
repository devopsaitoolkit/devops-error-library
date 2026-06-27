---
title: "Grafana Invalid Username or Password"
slug: grafana-invalid-username-or-password
technologies: [grafana]
severity: medium
tags: [grafana, authentication, login, access, production]
related: [grafana-database-is-locked-sqlite, grafana-failed-to-load-dashboards]
last_reviewed: 2026-06-27
---

# Grafana Invalid Username or Password

## Error Message

```text
Invalid username or password
```

```text
t=2026-06-24T09:31:05+0000 lvl=info msg="invalid username or password" logger=authn.service error="user authentication failed: invalid password"
```

## Description

Grafana returns **Invalid username or password** from the login form (`POST
/login`) when the supplied credentials do not match a user in Grafana's internal
user table, or when an external auth provider (LDAP/OAuth) rejects them. Grafana
deliberately returns the same generic message whether the user does not exist or
the password is wrong, to avoid user-enumeration. The relevant detail is in the
server log under the `authn` logger.

## Technologies

- grafana (authn service / user store)

## Severity

**medium** — a single user is locked out (login annoyance), but if it affects the
`admin` account or an SSO integration it can block all operator access and become
high severity.

## Common Causes

1. Wrong password, caps-lock, or a recently rotated password not yet propagated.
2. The user logs in with email when only username matches (or vice versa) and
   `login_hint`/`oauth_allow_insecure_email_lookup` is misconfigured.
3. The admin password was never changed from default or was reset incorrectly.
4. LDAP/OAuth bind or attribute mapping is broken, so external auth fails and
   Grafana reports it as invalid credentials.
5. Too many failed attempts triggered brute-force protection / login throttling.

## Root Cause Analysis

On login, Grafana hashes the submitted password (PBKDF2/bcrypt) with the stored
salt and compares it to the `password` column in the `user` table. A mismatch, a
non-existent login, or a rejection from the configured external auth provider all
funnel into the same `authn.service` failure path and the generic UI message. The
server log distinguishes `user not found` from `invalid password` and from
LDAP/OAuth bind errors — that distinction is what you need to fix it.

## Diagnostic Commands

```bash
# Auth failure detail (user-not-found vs invalid-password vs LDAP/OAuth)
journalctl -u grafana-server --since "10 min ago" | grep -i "authn\|invalid username\|login attempt"

# Confirm the user/login exists and is not disabled (admin token, read-only)
curl -s -H "Authorization: Bearer $GRAFANA_TOKEN" \
  "http://localhost:3000/api/users/lookup?loginOrEmail=alice" | jq '{login, email, isDisabled}'

# Read-only check that the user row exists in the internal DB (sqlite)
sqlite3 -readonly /var/lib/grafana/grafana.db \
  "SELECT login, email, is_disabled FROM user WHERE login='alice';"

# Which auth providers are enabled
curl -s -H "Authorization: Bearer $GRAFANA_TOKEN" \
  http://localhost:3000/api/admin/settings | jq '{auth_ldap: .["auth.ldap"], auth: .auth}'
```

## Expected Results

```text
error="user authentication failed: invalid password"   # password mismatch
error="user authentication failed: user not found"     # wrong/absent login
error="LDAP: bind failed"                               # external auth broken
```

A `lookup` that returns the user with `isDisabled: false` confirms the account
exists, narrowing the problem to the password or the external provider.

## Resolution

1. For a forgotten password on a local account, reset it with the CLI (run as the
   grafana user; it edits the internal DB):

   ```bash
   grafana-cli admin reset-admin-password '<new-strong-password>'
   ```
   (For non-admin users, reset via **Server Admin → Users** as an admin.)
2. If the user signs in by email, ensure they use the exact `login`, or enable
   the appropriate email-lookup setting for your auth method.
3. For LDAP/OAuth failures, fix the bind credentials / attribute mapping in
   `ldap.toml` or the OAuth section and reload Grafana.
4. If login throttling tripped, wait out the lockout window or restart the
   service after confirming credentials are correct.

## Validation

```bash
# A successful credentialed call confirms the account works
curl -s -u 'alice:<new-password>' http://localhost:3000/api/user | jq '{login, email}'
# Expect the user's profile JSON, not a 401.
```

## Prevention

- Change the default `admin` password at install and store it in a secret
  manager.
- Document the canonical login (username vs email) and keep auth mapping in code.
- Monitor `authn` failures; a spike can indicate a broken SSO change or an attack.

## Related Errors

- [Grafana Database Is Locked (SQLite)](./grafana-database-is-locked-sqlite.md)
- [Grafana Failed to Load Dashboards](./grafana-failed-to-load-dashboards.md)

## References

- [Grafana authentication](https://grafana.com/docs/grafana/latest/setup-grafana/configure-security/configure-authentication/)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`grafana` · `authentication` · `login` · `access` · `production`
