---
title: "MySQL Too Many Connections"
slug: mysql-too-many-connections
technologies: [mysql]
severity: critical
tags: [mysql, connections, capacity, outage, production]
related: [mysql-aborted-connection, mysql-access-denied-for-user]
last_reviewed: 2026-06-27
---

# MySQL Too Many Connections

## Error Message

```text
ERROR 1040 (HY000): Too many connections
```

```text
[Warning] [MY-010914] Too many connections, increase max_connections or fix the application
```

## Description

`ERROR 1040 (HY000)` means the server has reached `max_connections` and refuses
to open another client connection. MySQL reserves one extra slot above
`max_connections` for a user with the `CONNECTION_ADMIN`/`SUPER` privilege so an
operator can still log in to fix the problem — but every ordinary client is
turned away. This is almost always a symptom of connections being opened faster
than they are closed, not of genuine concurrency demand.

## Technologies

- mysql (connection handler / thread pool)

## Severity

**critical** — new application connections fail outright. For a stateless web
tier behind one database this is a site-wide outage until connections drain or
the limit is raised.

## Common Causes

1. A connection leak in the application — connections are checked out of a pool
   (or opened ad hoc) and never returned/closed.
2. Pool size summed across many app instances exceeds `max_connections`
   (e.g. 50 pods × 20 connections = 1000 against a limit of 500).
3. Long-running or stuck queries hold connections in `Sleep`/`Query` state.
4. `max_connections` is set far too low for the real workload.
5. A burst of traffic (deploy, cache stampede, cron storm) opens connections
   faster than the server can finish work.

## Root Cause Analysis

Each client connection consumes a server thread plus per-thread buffers, so the
limit exists to protect memory and CPU. When `Threads_connected` reaches
`max_connections`, the handler rejects new TCP/socket connects with 1040. A leak
shows up as a steadily climbing `Threads_connected` with most threads in the
`Sleep` command state — they are idle but still occupying a slot. Raising the
limit without fixing the leak only delays the next outage and risks an
out-of-memory condition.

## Diagnostic Commands

```bash
# Current vs configured connection counts
mysqladmin -u root -p extended-status | grep -E "Threads_connected|Max_used_connections"
mysql -u root -p -e "SHOW VARIABLES LIKE 'max_connections';"

# Who is connected, what state, how long idle — find the leak source
mysql -u root -p -e "SHOW PROCESSLIST;"

# Aggregate connections by host/user/state
mysql -u root -p -e "SELECT user, host, command, COUNT(*) \
  FROM information_schema.processlist GROUP BY user, host, command ORDER BY 4 DESC;"
```

## Expected Results

```text
| Threads_connected | 500 |
| Max_used_connections | 501 |
...
| app | 10.0.1.* | Sleep | 470 |
```

Hundreds of `Sleep` rows from one user/host is the signature of a leak or an
oversized pool. If most threads are in `Query` with high `Time`, the problem is
slow queries, not a leak.

## Resolution

1. Free capacity immediately by killing idle connections (use the reserved admin
   slot to log in):

   ```sql
   -- Generate and run KILL for connections idle > 600s
   SELECT CONCAT('KILL ', id, ';') FROM information_schema.processlist
   WHERE command='Sleep' AND time > 600;
   ```
2. Fix the application: ensure every connection is closed/returned to the pool in
   a `finally`/`defer`, and cap pool size so
   `instances × pool_max ≤ max_connections − headroom`.
3. If the limit is genuinely too low, raise it in `my.cnf` and reload (each slot
   costs memory, so size against RAM):

   ```ini
   [mysqld]
   max_connections = 1000
   ```
   Then `SET GLOBAL max_connections = 1000;` to apply without restart.
4. Add a shorter `wait_timeout` so abandoned idle connections self-close.

## Validation

```bash
mysql -u root -p -e "SHOW STATUS LIKE 'Threads_connected';"
# Expect Threads_connected to plateau well below max_connections under load.
```

## Prevention

- Always use a bounded connection pool with explicit max size and idle timeout.
- Alert on `Threads_connected / max_connections > 0.8`.
- Load-test the summed pool capacity of all app instances before scaling out.
- Set `wait_timeout`/`interactive_timeout` to reap abandoned connections.

## Related Errors

- [MySQL Aborted Connection](./mysql-aborted-connection.md)
- [MySQL Access Denied for User](./mysql-access-denied-for-user.md)

## References

- [MySQL: Too Many Connections](https://dev.mysql.com/doc/refman/8.0/en/too-many-connections.html)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`mysql` · `connections` · `capacity` · `outage` · `production`
