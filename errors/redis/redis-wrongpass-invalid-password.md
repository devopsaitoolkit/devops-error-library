---
title: "Redis WRONGPASS Invalid Username-Password Pair"
slug: redis-wrongpass-invalid-password
technologies: [redis]
severity: medium
tags: [redis, authentication, acl, security, production]
related: [redis-noauth-authentication-required, redis-connection-refused]
last_reviewed: 2026-06-27
---

# Redis WRONGPASS Invalid Username-Password Pair

## Error Message

```text
(error) WRONGPASS invalid username-password pair or user is disabled.
```

```text
redis.exceptions.AuthenticationError: WRONGPASS invalid username-password pair
or user is disabled.
```

## Description

`WRONGPASS` is returned by `AUTH` when the supplied credentials don't match — a
wrong password, a username that doesn't exist, or an ACL user that is disabled
(`off`). It differs from `NOAUTH`: `NOAUTH` means *you haven't authenticated yet*,
while `WRONGPASS` means *you tried and the credentials were rejected*. The
connection stays unauthenticated, so subsequent data commands fail too.

## Technologies

- redis (authentication / ACL)

## Severity

**medium** — the server is healthy and secured; affected clients can't
authenticate. Impact scales with how many clients carry the stale/wrong
credential. Repeated `WRONGPASS` from one source can also indicate a
brute-force attempt.

## Common Causes

1. The password was rotated on the server (`requirepass` or `ACL SETUSER`) but the
   client still uses the old one.
2. The client authenticates with a username that doesn't exist in the ACL.
3. The ACL user exists but is disabled (`off`).
4. A trailing space, quoting/escaping mistake, or wrong secret was injected into
   the client config.
5. Connecting to the wrong Redis instance that has a different password.

## Root Cause Analysis

Redis stores passwords as SHA-256 hashes per ACL user. On `AUTH <user> <pass>` it
looks up the user, checks the user is `on`, and compares the hash of the supplied
password against the stored set. Any mismatch — unknown user, disabled user, or
non-matching hash — yields `WRONGPASS`. Because credentials are checked per
connection, every connection using the stale secret fails identically, which is
why a single rotated-but-not-deployed secret can take down many clients at once.

## Diagnostic Commands

```bash
# Does the user exist, is it enabled, and what does its rule set look like?
redis-cli -a <admin-password> ACL LIST
redis-cli -a <admin-password> ACL GETUSER <username>

# Which user is the current (working) connection authenticated as?
redis-cli -a <admin-password> ACL WHOAMI

# Count of auth failures and a recent log of denied auth attempts
redis-cli -a <admin-password> ACL LOG 10

# Confirm you're hitting the intended instance (run_id / address)
redis-cli -a <admin-password> INFO server | grep -E 'run_id|tcp_port'
```

## Expected Results

```text
$ redis-cli -a <admin-password> ACL GETUSER appuser
 1) "flags"
 2) 1) "off"        # user disabled -> WRONGPASS for any password
 ...

$ redis-cli -a <admin-password> ACL LOG 1
1) 1) "count"
   2) (integer) 37
   3) "reason"
   4) "auth"
   5) "object"
   6) "AUTH"
   7) "username"
   8) "appuser"
```

An `off` flag, an `ACL LOG` entry with `reason: auth` for the username, or a
missing user all confirm why `AUTH` failed. A correct credential against an `on`
user returns `OK`.

## Resolution

1. Update the client with the current password from the secret store (most common
   fix after a rotation).
2. If the ACL user is disabled, re-enable it (this is a write/admin change, not a
   diagnostic):

   ```bash
   redis-cli -a <admin-password> ACL SETUSER appuser on
   ```
3. If the user doesn't exist, create it with least-privilege rules and a strong
   password, then update the client:

   ```bash
   redis-cli -a <admin-password> ACL SETUSER appuser on '>NEW_STRONG_PASSWORD' '~app:*' '+@read' '+@write'
   ```
4. Rule out quoting/whitespace issues by re-injecting the secret cleanly; verify
   you're targeting the intended instance via `run_id`.

## Validation

```bash
redis-cli -u 'redis://appuser:<NEW_PASSWORD>@redis-host:6379' PING
# Expect: PONG  (no WRONGPASS)
```

## Prevention

- Rotate the password in the secret manager and on the server in one coordinated
  step; roll clients immediately.
- Use one ACL user per service with least-privilege rules so rotation is scoped.
- Monitor `ACL LOG` / auth-failure counts to catch misconfig and brute-force.
- Keep credentials out of command lines (use `REDISCLI_AUTH` or URI from a file).

## Related Errors

- [Redis NOAUTH Authentication Required](./redis-noauth-authentication-required.md)
- [Redis Connection Refused](./redis-connection-refused.md)

## References

- [Redis: ACL documentation](https://redis.io/docs/management/security/acl/)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`redis` · `authentication` · `acl` · `security` · `production`
