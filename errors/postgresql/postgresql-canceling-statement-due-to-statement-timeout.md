---
title: "PostgreSQL Canceling Statement Due to Statement Timeout"
slug: postgresql-canceling-statement-due-to-statement-timeout
technologies: [postgresql]
severity: medium
tags: [postgresql, performance, timeout, queries, production]
related: [postgresql-deadlock-detected, postgresql-too-many-connections]
last_reviewed: 2026-06-27
---

# PostgreSQL Canceling Statement Due to Statement Timeout

## Error Message

```text
ERROR:  canceling statement due to statement timeout
```

```text
ERROR:  canceling statement due to statement timeout
STATEMENT:  SELECT * FROM events e JOIN sessions s ON s.id = e.session_id
            WHERE e.created_at > now() - interval '90 days';
```

## Description

`statement_timeout` is a per-session limit (in milliseconds) on how long a single
SQL statement may run. When a statement exceeds it, PostgreSQL cancels the query
and raises `ERROR: canceling statement due to statement timeout`, rolling back
that statement. It is a deliberate guardrail, not a database fault — it protects
the server from runaway queries that would otherwise hold locks and consume
resources. The error tells you a query was *too slow* for its budget; the cause
is either a genuinely slow query or a timeout set too aggressively for the work.

## Technologies

- postgresql (query executor, `statement_timeout`)

## Severity

**medium** — the individual query fails and must be retried or optimized; the
server stays healthy (this is the timeout working as intended). High if it breaks
a critical query path on every execution.

## Common Causes

1. A missing or unusable index forces a sequential scan that exceeds the timeout —
   the most common cause.
2. The query genuinely processes too much data (unbounded range, large join) for
   the allotted time.
3. The statement waited on a lock held by another transaction and the wait pushed
   it past the limit.
4. `statement_timeout` is set too low (globally or via a pooler) for legitimate
   reporting/batch queries.
5. Stale planner statistics produce a bad plan that is far slower than necessary.

## Root Cause Analysis

PostgreSQL arms a timer when a statement begins executing; if the timer fires
before the statement completes, the backend sends itself a cancel and the
executor aborts at the next interrupt check. The timeout is the *messenger* — the
real question is whether the statement is slow because of a poor plan
(missing/unused index, bad statistics), excessive data volume, or lock waiting.
Note that lock-wait time counts toward `statement_timeout`, so a query blocked
behind a long transaction can time out even though its own execution would be
fast. `EXPLAIN` (and `EXPLAIN ANALYZE` on a safe copy) distinguishes a slow plan
from a blocking problem.

## Diagnostic Commands

```bash
# Current timeout values (session/global and any per-role override)
psql -c "SHOW statement_timeout;"
psql -c "SELECT rolname, rolconfig FROM pg_roles WHERE rolconfig IS NOT NULL;"

# Plan WITHOUT running it — spot seq scans / missing-index estimates
psql -c "EXPLAIN SELECT * FROM events WHERE created_at > now() - interval '90 days';"

# Is the slow statement actually waiting on a lock?
psql -c "SELECT pid, wait_event_type, wait_event, now()-query_start AS runtime, query
         FROM pg_stat_activity WHERE state='active' ORDER BY runtime DESC LIMIT 10;"

# Index usage / unused indexes that hint at scan problems
psql -c "SELECT relname, seq_scan, idx_scan FROM pg_stat_user_tables ORDER BY seq_scan DESC LIMIT 10;"
```

## Expected Results

```text
# EXPLAIN revealing the problem:
 Seq Scan on events  (cost=0.00..184213.00 rows=120 width=72)
   Filter: (created_at > (now() - '90 days'::interval))

# vs. healthy after indexing:
 Index Scan using events_created_at_idx on events  (cost=0.43..812.10 rows=120 ...)
```

A `Seq Scan` with a huge cost on a large table, or a high `wait_event_type =
Lock`, points to the underlying cause.

## Resolution

1. If `EXPLAIN` shows a sequential scan on a filtered/joined column, add an index
   (build concurrently in production to avoid locking the table):

   ```sql
   CREATE INDEX CONCURRENTLY events_created_at_idx ON events (created_at);
   ```
2. Refresh stale statistics so the planner chooses a better plan:

   ```sql
   ANALYZE events;
   ```
3. If the timeout is too low for legitimate heavy queries, raise it *for that
   work only* — do not weaken the global guardrail:

   ```sql
   SET statement_timeout = '120s';   -- session-scoped, e.g. for a report job
   ```
4. If lock waiting is the cause, resolve the blocking transaction (see the
   deadlock/locking diagnostics) rather than just extending the timeout.

## Validation

```bash
psql -c "EXPLAIN ANALYZE SELECT * FROM events WHERE created_at > now() - interval '90 days';"
# Expect an Index Scan and an actual time well under statement_timeout; query completes.
```

## Prevention

- Keep `statement_timeout` set as a safety net (e.g. a few seconds for OLTP) and
  grant longer budgets only to report/batch roles.
- Index the columns your hot queries filter and join on; review `pg_stat_user_tables`.
- Keep autovacuum/auto-analyze healthy so plans stay accurate.
- Add query-latency monitoring so slow plans are caught before they time out.

## Related Errors

- [PostgreSQL deadlock detected](./postgresql-deadlock-detected.md)
- [PostgreSQL too many connections](./postgresql-too-many-connections.md)

## References

- [PostgreSQL: Client Connection Defaults (statement_timeout)](https://www.postgresql.org/docs/current/runtime-config-client.html)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`postgresql` · `performance` · `timeout` · `queries` · `production`
