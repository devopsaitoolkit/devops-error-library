---
title: "Redis NOAUTH Authentication Required"
slug: redis-noauth-authentication-required
technologies: [redis]
severity: medium
tags: [redis, authentication, security, acl, production]
related: [redis-wrongpass-invalid-password, redis-connection-refused]
last_reviewed: 2026-06-27
---

# Redis NOAUTH Authentication Required

## Error Message

```text
(error) NOAUTH Authentication required.
```

```text
redis.exceptions.AuthenticationError: Authentication required.
```

## Description

`NOAUTH Authentication required.` is returned when a client issues a command on a
connection that has not authenticated, but the server has a password configured
(`requirepass`) or the default user requires a password via the ACL system. Until
the client sends a valid `AUTH` (or `AUTH <user> <pass>` for ACL users), every
command except `AUTH`, `HELLO`, `RESET`, and `QUIT` is rejected.

This is normal and expected on a secured instance — it usually surfaces when an
application's Redis client is misconfigured with no password, or when someone
runs `redis-cli` without `-a`/`AUTH`.

## Technologies

- redis (authentication / ACL)

## Severity

**medium** — the instance is healthy and secured; the affected client simply
cannot run commands until it authenticates. Impact scales with how many clients
are misconfigured.

## Common Causes

1. The application's Redis client was configured without the password (or with an
   empty one) while `requirepass` is set.
2. An operator ran `redis-cli` without `-a <password>` (or didn't run `AUTH`).
3. A password was rotated on the server but not in the client/secret store.
4. The connection was reset/reconnected and the client library failed to re-send
   `AUTH` on the new connection.

## Root Cause Analysis

When `requirepass` (or an ACL rule for the `default` user) is in effect, every
new connection starts in an unauthenticated state. The server tracks
authentication per connection, not per client process. The first non-`AUTH`
command on such a connection triggers the `NOAUTH` guard. So intermittent
`NOAUTH` errors after a network blip usually mean the client library reconnected
but did not replay `AUTH` on the fresh socket.

## Diagnostic Commands

```bash
# Confirm a password is required (returns NOAUTH if so, PONG if not)
redis-cli PING

# Is requirepass set on the server? (run on an authenticated session)
redis-cli -a <password> CONFIG GET requirepass

# Inspect the default user's ACL rules and whether it needs a password
redis-cli -a <password> ACL WHOAMI
redis-cli -a <password> ACL LIST

# Authentication failure counters and connected clients
redis-cli -a <password> INFO stats | grep -E 'total_connections_received|rejected_connections'
redis-cli -a <password> CLIENT LIST
```

## Expected Results

```text
$ redis-cli PING
(error) NOAUTH Authentication required.

$ redis-cli -a <password> ACL LIST
1) "user default on #<sha256...> ~* &* +@all"
```

The `on` flag with a password hash (`#...`) on the `default` user, or a non-empty
`requirepass`, confirms authentication is mandatory. After a correct `AUTH`,
`PING` returns `PONG`.

## Resolution

1. Supply the password in the client. For `redis-cli`:

   ```bash
   redis-cli -a '<password>' PING
   # or, interactively:
   redis-cli
   127.0.0.1:6379> AUTH <password>
   ```
2. Fix the application configuration / secret so the client connects with the
   password (and the correct ACL username if not `default`):

   ```text
   redis://default:<password>@redis-host:6379/0
   ```
3. If using ACL users, authenticate with both username and password:

   ```bash
   redis-cli -u 'redis://appuser:<password>@redis-host:6379'
   ```
4. Ensure the client library is configured to re-authenticate automatically on
   reconnect (most modern clients do this when given a password).

## Validation

```bash
redis-cli -a '<password>' PING
# Expect: PONG  (no NOAUTH)
```

## Prevention

- Store the Redis password in your secret manager and inject it into every
  client; never commit it.
- Rotate the password in the secret store and the server together, ideally with
  an ACL user per service so rotation is scoped.
- Test the connection string (with auth) in CI before deploy.
- Avoid passing passwords on the CLI in shared shells (use `REDISCLI_AUTH` or an
  interactive `AUTH`) to keep them out of process listings.

## Related Errors

- [Redis WRONGPASS Invalid Username-Password Pair](./redis-wrongpass-invalid-password.md)
- [Redis Connection Refused](./redis-connection-refused.md)

## References

- [Redis: ACL and authentication](https://redis.io/docs/management/security/acl/)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`redis` · `authentication` · `security` · `acl` · `production`
