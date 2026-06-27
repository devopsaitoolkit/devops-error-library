---
title: "PostgreSQL Deadlock Detected"
slug: postgresql-deadlock-detected
technologies: [postgresql]
severity: medium
tags: [postgresql, concurrency, locking, transactions, production]
related: [postgresql-canceling-statement-due-to-statement-timeout, postgresql-too-many-connections]
last_reviewed: 2026-06-27
---

# PostgreSQL Deadlock Detected

## Error Message

```text
ERROR:  deadlock detected
DETAIL:  Process 18233 waits for ShareLock on transaction 994412; blocked by process 18301.
	Process 18301 waits for ShareLock on transaction 994410; blocked by process 18233.
HINT:  See server log for query details.
CONTEXT:  while updating tuple (0,17) in relation "accounts"
```

## Description

A deadlock occurs when two or more transactions each hold a lock the other needs,
forming a cycle that can never resolve on its own. PostgreSQL runs a deadlock
detector (after `deadlock_timeout`, default 1s, of waiting) that finds the cycle
and aborts one of the transactions — the *victim* — with `ERROR: deadlock
detected`. The aborted transaction is rolled back so the survivor can proceed.
Unlike a hung lock, a deadlock is self-healing at the cost of one rolled-back
transaction; the `DETAIL` lines name the exact processes and the relation/tuple
involved.

## Technologies

- postgresql (lock manager, deadlock detector)

## Severity

**medium** — one transaction is sacrificed and must be retried; the database
stays up. It becomes high if deadlocks are frequent enough to cause visible error
rates or data inconsistency from un-retried failures.

## Common Causes

1. Two code paths lock the *same rows in a different order* (e.g. one updates
   account A then B, another B then A) — the classic ordering deadlock.
2. Inconsistent lock ordering across tables touched in the same transaction.
3. Foreign-key contention: concurrent inserts/updates taking row locks on the
   referenced parent rows in conflicting orders.
4. Long transactions holding locks while doing slow work, widening the window.
5. Explicit `SELECT ... FOR UPDATE` / `LOCK TABLE` acquired in varying sequences.

## Root Cause Analysis

PostgreSQL uses row-level write locks and transaction-ID locks. When transaction
T1 holds a lock T2 wants, T2 waits. If T2 already holds a lock T1 now wants, a
wait-for cycle exists. The detector wakes after `deadlock_timeout` and scans the
wait-for graph; on finding a cycle it terminates the transaction it judges
cheapest to abort. The fundamental cause is almost always *non-deterministic lock
acquisition order* across concurrent transactions — fix the order and the cycle
cannot form. Frequent deadlocks therefore point to an application-level ordering
bug, not a database misconfiguration.

## Diagnostic Commands

```bash
# Pull deadlock reports straight from the server log
sudo journalctl -u postgresql --since "1 hour ago" --no-pager | grep -A6 "deadlock detected"

# Live blocking chains (who waits on whom, and the offending queries)
psql -c "SELECT blocked.pid AS blocked_pid, blocked.query AS blocked_query,
                blocking.pid AS blocking_pid, blocking.query AS blocking_query
         FROM pg_stat_activity blocked
         JOIN pg_stat_activity blocking
           ON blocking.pid = ANY(pg_blocking_pids(blocked.pid))
         WHERE cardinality(pg_blocking_pids(blocked.pid)) > 0;"

# Current locks held/awaited
psql -c "SELECT pid, locktype, mode, granted, relation::regclass
         FROM pg_locks WHERE NOT granted;"

# Confirm deadlocks are being logged
psql -c "SHOW log_lock_waits; SHOW deadlock_timeout;"
```

## Expected Results

```text
 blocked_pid |        blocked_query        | blocking_pid |       blocking_query
-------------+-----------------------------+--------------+----------------------------
       18233 | UPDATE accounts SET ... B   |        18301 | UPDATE accounts SET ... B
       18301 | UPDATE accounts SET ... A   |        18233 | UPDATE accounts SET ... A
```

The two queries touch the same rows (A and B) in opposite order — the signature
of an ordering deadlock.

## Resolution

1. Make every transaction acquire row locks in a **consistent, deterministic
   order** (e.g. always lock accounts by ascending `id`):

   ```sql
   -- Both code paths must lock in the same order:
   SELECT * FROM accounts WHERE id IN (101, 202) ORDER BY id FOR UPDATE;
   ```
2. Keep transactions short — do slow work (network calls, computation) outside the
   transaction so locks are held for the minimum time.
3. Add bounded retry-on-deadlock logic in the application; a retried victim
   usually succeeds because the conflicting transaction has finished.
4. Reduce lock scope: update only the rows you must, and avoid table-level locks.

## Validation

```bash
# After fixing lock order, the deadlock count should stop climbing
psql -c "SELECT datname, deadlocks FROM pg_stat_database WHERE datname = current_database();"
# Re-run twice under load; 'deadlocks' should not increase.
```

## Prevention

- Enforce a single canonical lock-ordering convention in code review.
- Set `log_lock_waits = on` to surface contention before it becomes a deadlock.
- Keep transactions small and short-lived; never wait on external I/O mid-transaction.
- Monitor `pg_stat_database.deadlocks` and alert on a rising rate.

## Related Errors

- [PostgreSQL canceling statement due to statement timeout](./postgresql-canceling-statement-due-to-statement-timeout.md)
- [PostgreSQL too many connections](./postgresql-too-many-connections.md)

## References

- [PostgreSQL: Explicit Locking & Deadlocks](https://www.postgresql.org/docs/current/explicit-locking.html#LOCKING-DEADLOCKS)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`postgresql` · `concurrency` · `locking` · `transactions` · `production`
