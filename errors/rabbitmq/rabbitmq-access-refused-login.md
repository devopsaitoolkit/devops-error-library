---
title: "RabbitMQ ACCESS_REFUSED Login"
slug: rabbitmq-access-refused-login
technologies: [rabbitmq]
severity: high
tags: [rabbitmq, authentication, authorization, access-refused, production]
related: [rabbitmq-connection-refused, rabbitmq-queue-not-found-404]
last_reviewed: 2026-06-27
---

# RabbitMQ ACCESS_REFUSED Login

## Error Message

```text
=ERROR REPORT==== 27-Jun-2026::11:07:33 ===
operation Basic.publish caused a channel exception access_refused:
ACCESS_REFUSED - Login was refused using authentication mechanism PLAIN.
For details see the broker logfile.
```

```text
amqp.exceptions.AccessRefused: (0, 0): (403) ACCESS_REFUSED -
Login was refused using authentication mechanism PLAIN.
```

## Description

`ACCESS_REFUSED` during connection establishment is an authentication failure:
the broker reached the AMQP login phase but rejected the credentials. This is
distinct from `connection refused` (a TCP failure) — here the TCP connection
succeeded and RabbitMQ deliberately denied the login. It is emitted when the
username/password is wrong, the user does not exist, the user lacks access to the
requested virtual host, or the user is configured to deny remote logins.

## Technologies

- rabbitmq (authentication backend, access control / vhost permissions)

## Severity

**high** — the affected application cannot connect at all, so its publishers and
consumers are down. Scope is per-credential: a rotated secret or revoked user can
take an entire service offline.

## Common Causes

1. Wrong username or password (stale secret, typo, un-rotated credential).
2. The user does not exist or was deleted.
3. The user has no permission on the requested vhost (e.g. connecting to `/`
   without rights, or to a vhost that does not exist).
4. Using the `guest` user from a remote host — `guest` is restricted to
   `localhost` by default (`loopback_users`).
5. The user's tags/permissions were changed and the app still uses old access.

## Root Cause Analysis

On connection, the client sends credentials via the PLAIN (or other) SASL
mechanism. RabbitMQ's auth backend (internal database by default) validates them;
on mismatch it returns `ACCESS_REFUSED` and closes the connection. Even with
valid credentials, the broker then checks vhost access — a user with no
permission entry on the target vhost is refused at login. The default `guest`
account additionally appears in `loopback_users`, so the broker refuses it from
any non-loopback address regardless of password.

## Diagnostic Commands

```bash
# Does the user exist and what tags does it have?
sudo rabbitmqctl list_users

# What permissions does the user have, and on which vhosts?
sudo rabbitmqctl list_user_permissions <username>

# Which vhosts exist?
sudo rabbitmqctl list_vhosts

# Authentication attempt details in the log (reason for refusal)
sudo journalctl -u rabbitmq-server --since "15 min ago" --no-pager \
  | grep -iE "access_refused|authentication"
```

## Expected Results

```text
# list_users shows the user (or its absence):
Listing users ...
user    tags
appsvc  []

# list_user_permissions reveals missing vhost access:
Listing permissions for user "appsvc" ...
(empty)   <-- no permission on any vhost -> login to that vhost is refused
```

An empty permissions list, or a missing user, explains the refusal even when the
password is correct.

## Resolution

1. Verify the exact username/password the app is sending (check the secret store,
   not just the deployment manifest).
2. Create the user if missing and grant permissions on the target vhost:

   ```bash
   sudo rabbitmqctl add_user appsvc '<password>'
   sudo rabbitmqctl set_permissions -p / appsvc ".*" ".*" ".*"
   ```
3. If using `guest` remotely, switch to a dedicated user — do not loosen
   `loopback_users` in production.
4. After rotating a secret, restart/redeploy the client so it picks up the new
   credential.

## Validation

```bash
# Verify credentials authenticate without granting a session
sudo rabbitmq-diagnostics check_user_authentication appsvc '<password>'
# Expect: "Authentication succeeded" for user appsvc
```

## Prevention

- Manage users/permissions declaratively (definitions file or operator) so they
  match what apps expect.
- Use dedicated per-service users with least-privilege permissions, never `guest`.
- Rotate credentials through the secret store and redeploy clients atomically.
- Alert on spikes in `ACCESS_REFUSED` log lines.

## Related Errors

- [RabbitMQ Connection Refused](./rabbitmq-connection-refused.md)
- [RabbitMQ Queue Not Found 404](./rabbitmq-queue-not-found-404.md)

## References

- [RabbitMQ Access Control and Authentication](https://www.rabbitmq.com/docs/access-control)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`rabbitmq` · `authentication` · `authorization` · `access-refused` · `production`
