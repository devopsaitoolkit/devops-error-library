---
title: "MySQL Can't Connect Through Socket"
slug: mysql-cant-connect-through-socket
technologies: [mysql]
severity: high
tags: [mysql, connectivity, socket, startup, production]
related: [mysql-access-denied-for-user, mysql-got-error-28-disk-full]
last_reviewed: 2026-06-27
---

# MySQL Can't Connect Through Socket

## Error Message

```text
ERROR 2002 (HY000): Can't connect to local MySQL server through socket '/var/run/mysqld/mysqld.sock' (2)
```

```text
ERROR 2002 (HY000): Can't connect to local MySQL server through socket '/tmp/mysql.sock' (111)
```

## Description

`ERROR 2002 (HY000)` is a *client-side* error: the client tried to reach the
server over a Unix domain socket and failed. When the client host is `localhost`,
MySQL connects via the socket file rather than TCP, so this error appears even
when the server's network port is fine. The trailing OS errno tells you why:
`(2)` is `ENOENT` (the socket file does not exist — server is down or writes its
socket elsewhere); `(111)` is `ECONNREFUSED` (a stale socket exists but nothing
is listening).

## Technologies

- mysql (client connector / Unix socket)

## Severity

**high** — no local client (including app processes on the DB host and admin
tooling) can connect. If the server itself is down, it is a full database outage.

## Common Causes

1. The MySQL server is not running (crashed, failed to start, or stopped).
2. The client and server disagree on the socket path — the client looks in
   `/tmp/mysql.sock` while the server created `/var/run/mysqld/mysqld.sock`.
3. The server failed to start (config error, disk full, corrupt InnoDB) and so
   never created the socket file.
4. Permissions on the socket file or its directory block the client user.
5. A stale socket file left after an unclean shutdown (errno 111).

## Root Cause Analysis

On startup the server creates the socket file at the path in its `socket`
variable. A `localhost` client reads *its own* `socket` setting (from
`/etc/mysql/my.cnf`, `~/.my.cnf`, or the compiled default) and `connect()`s to
that path. If the server is down the file is absent (errno 2). If the file path
differs between client and server, the client looks at the wrong place (errno 2).
If the file exists but the server died without cleaning up, the connect is
refused (errno 111). Distinguishing "server down" from "wrong path" is the key
diagnostic step.

## Diagnostic Commands

```bash
# Is the server process even up?
sudo systemctl status mysql

# Where does the SERVER put its socket (and is it listening on TCP)?
mysql --help 2>/dev/null | grep -A1 "Default options"   # shows config files read
ss -lnp | grep -E "mysqld|3306"

# Does the socket file actually exist, and with what permissions?
ls -l /var/run/mysqld/mysqld.sock /tmp/mysql.sock 2>&1

# Why did startup fail (disk, config, InnoDB)?
sudo journalctl -u mysql --since "15 min ago" | tail -n 40
```

## Expected Results

```text
● mysql.service - MySQL Community Server
     Active: failed (Result: exit-code)
...
ls: cannot access '/var/run/mysqld/mysqld.sock': No such file or directory
```

A `failed`/`inactive` service with no socket file means the server is down (fix
startup). An `active (running)` service plus a socket file at a *different* path
than the client expects means a path mismatch (fix the client config).

## Resolution

1. If the server is down, read the journal to find why (disk full, config typo,
   InnoDB corruption) and start it:

   ```bash
   sudo systemctl start mysql && sudo systemctl status mysql
   ```
2. If the server is up but paths differ, point the client at the real socket —
   either per command or in config:

   ```bash
   mysql --socket=/var/run/mysqld/mysqld.sock -u app -p
   ```
   ```ini
   # /etc/mysql/my.cnf — keep [client] and [mysqld] socket consistent
   [client]
   socket = /var/run/mysqld/mysqld.sock
   ```
3. Remove a stale socket only if the server is confirmed stopped, then restart.
4. Fix permissions so the client user can access the socket directory
   (`/var/run/mysqld` should be owned by `mysql`).
5. To bypass the socket entirely, connect over TCP: `mysql -h 127.0.0.1 -P 3306`.

## Validation

```bash
mysqladmin -u root -p status
# Expect "Uptime: ... Threads: ..." rather than ERROR 2002.
```

## Prevention

- Set the same `socket` path in `[client]` and `[mysqld]` and template it.
- Monitor the systemd unit and alert on `failed`/`inactive`.
- Catch startup failures (disk, config) in pre-deploy checks.
- Prefer `127.0.0.1` TCP connections from co-located apps to avoid path drift.

## Related Errors

- [MySQL Access Denied for User](./mysql-access-denied-for-user.md)
- [MySQL Got Error 28 From Storage Engine (Disk Full)](./mysql-got-error-28-disk-full.md)

## References

- [MySQL: Can't Connect to Local Server](https://dev.mysql.com/doc/refman/8.0/en/problems-with-mysql-sock.html)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`mysql` · `connectivity` · `socket` · `startup` · `production`
