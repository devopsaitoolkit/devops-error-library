---
title: "PostgreSQL Too Many Connections"
slug: postgresql-too-many-connections
technologies: [postgresql]
severity: high
tags: [postgresql, connections, pooling, capacity, production]
related: [postgresql-connection-refused, postgresql-canceling-statement-due-to-statement-timeout]
last_reviewed: 2026-06-27
---

# PostgreSQL Too Many Connections

## Error Message

```text
FATAL:  sorry, too many clients already
```

```text
FATAL:  remaining connection slots are reserved for non-replication superuser connections
```

## Description

PostgreSQL allocates a fixed number of backend slots at startup, governed by
`max_connections`. Each client connection consumes one slot (plus a small reserve
held back for superusers via `superuser_reserved_connections`). When all
non-reserved slots are in use, the postmaster refuses new connections with
`FATAL: sorry, too many clients already`. The second variant means only the
superuser-reserved slots remain, so ordinary roles are turned away while an admin
can still get in to investigate.

## Technologies

- postgresql (postmaster, backend process management)

## Severity

**high** — application requests that need a fresh connection fail immediately.
This is typically a partial-to-full outage that arrives suddenly under load and
often cascades as clients retry.

## Common Causes

1. No connection pooler (or a per-instance pool whose total fan-out exceeds
   `max_connections`) — the usual root cause in microservice fleets.
2. Connection leaks: application code opens connections and never closes them.
3. Long-running or idle-in-transaction sessions holding slots indefinitely.
4. `max_connections` set too low for the real concurrency the workload needs.
5. A traffic spike or a thundering herd of retries after a brief blip.

## Root Cause Analysis

Every backend is a separate OS process with its own memory footprint, so
`max_connections` cannot simply be raised without bound — high values waste RAM
and increase contention. The error is the postmaster enforcing that ceiling. The
real diagnostic question is *what is holding the slots*: genuine concurrent work,
idle sessions that should have been returned to a pool, or transactions stuck in
`idle in transaction` because the application forgot to commit/rollback. Counting
connections by state and by application name almost always reveals one offending
service or a missing pooler.

## Diagnostic Commands

```bash
# Configured ceiling and current count
psql -c "SHOW max_connections;"
psql -c "SELECT count(*) FROM pg_stat_activity;"

# Connections grouped by state — look for large 'idle' / 'idle in transaction'
psql -c "SELECT state, count(*) FROM pg_stat_activity GROUP BY state ORDER BY 2 DESC;"

# Who is holding slots, by app and user
psql -c "SELECT application_name, usename, count(*) FROM pg_stat_activity GROUP BY 1,2 ORDER BY 3 DESC;"

# Oldest idle-in-transaction sessions (slot leaks)
psql -c "SELECT pid, now()-state_change AS idle_for, query
         FROM pg_stat_activity
         WHERE state='idle in transaction' ORDER BY idle_for DESC LIMIT 10;"
```

## Expected Results

```text
 state                | count
----------------------+-------
 active               |    12
 idle                 |   180   <- pool not returning connections / no pooler
 idle in transaction  |    44   <- application leaking open transactions
```

A large `idle` or `idle in transaction` count next to a small `active` count
means the slots are wasted, not genuinely busy.

## Resolution

1. Immediate relief — terminate stuck idle-in-transaction sessions (verify before
   killing production work):

   ```sql
   SELECT pg_terminate_backend(pid)
   FROM pg_stat_activity
   WHERE state = 'idle in transaction'
     AND now() - state_change > interval '10 minutes';
   ```
2. Put a connection pooler in front of PostgreSQL (PgBouncer in `transaction`
   mode is the standard fix) so hundreds of client connections share a small set
   of server connections.
3. Cap `idle_in_transaction_session_timeout` so leaked transactions self-release:

   ```conf
   idle_in_transaction_session_timeout = '60s'
   ```
4. Only raise `max_connections` after sizing memory; a restart is required:

   ```conf
   max_connections = 300
   ```

## Validation

```bash
psql -c "SELECT count(*), (SELECT setting::int FROM pg_settings WHERE name='max_connections') AS max
         FROM pg_stat_activity;"
# Expect count comfortably below max with headroom; no new FATAL in the log.
```

## Prevention

- Always front PostgreSQL with a pooler; size app pools so their sum stays under
  `max_connections`.
- Set `idle_in_transaction_session_timeout` and `statement_timeout` as guardrails.
- Alert when `pg_stat_activity` count crosses ~80% of `max_connections`.
- Audit application code for connections opened outside `try/finally` close blocks.

## Related Errors

- [PostgreSQL Connection Refused](./postgresql-connection-refused.md)
- [PostgreSQL canceling statement due to statement timeout](./postgresql-canceling-statement-due-to-statement-timeout.md)

## References

- [PostgreSQL: Connection Settings](https://www.postgresql.org/docs/current/runtime-config-connection.html)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`postgresql` · `connections` · `pooling` · `capacity` · `production`
