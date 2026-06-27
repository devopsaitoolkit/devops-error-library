---
title: "MySQL Deadlock Found When Trying to Get Lock"
slug: mysql-deadlock-found-when-trying-to-get-lock
technologies: [mysql]
severity: high
tags: [mysql, innodb, deadlock, transactions, production]
related: [mysql-lock-wait-timeout-exceeded, mysql-too-many-connections]
last_reviewed: 2026-06-27
---

# MySQL Deadlock Found When Trying to Get Lock

## Error Message

```text
ERROR 1213 (40001): Deadlock found when trying to get lock; try restarting transaction
```

## Description

`ERROR 1213 (40001)` is raised when InnoDB's deadlock detector finds a *cycle* of
transactions each waiting on a lock the other holds, so none can ever proceed.
InnoDB resolves it instantly by choosing a victim — typically the transaction
that has done the least work — rolling it back, and returning 1213 to that
client. The other transactions in the cycle then continue. Unlike a lock-wait
timeout (1205), a deadlock is detected immediately rather than after a timeout,
and the SQLSTATE `40001` specifically signals "serialization failure, safe to
retry".

## Technologies

- mysql (InnoDB deadlock detector)

## Severity

**high** — the victim transaction is fully rolled back and must be retried.
Occasional deadlocks are normal under concurrency, but a high rate indicates a
locking-order problem and causes user-visible failures and wasted work.

## Common Causes

1. Inconsistent lock ordering — two code paths update the same rows/tables in the
   opposite order, forming a cycle.
2. Gap/next-key locks from range `UPDATE`/`DELETE`/`INSERT` under
   `REPEATABLE READ` colliding with concurrent inserts.
3. Hot rows updated by many transactions in interleaving order.
4. Secondary-index plus primary-key lock acquisition in differing sequences.
5. Long transactions that hold many locks, widening the window for cycles.

## Root Cause Analysis

InnoDB maintains a wait-for graph of which transaction waits on which lock. When
acquiring a lock would create a cycle in that graph, the detector fires
immediately and rolls back the cheapest victim to break it. The canonical
production cause is two transactions touching the same two rows in opposite
orders: T1 locks row A then waits for B; T2 locks B then waits for A. The
authoritative explanation of the *last* deadlock is always in
`SHOW ENGINE INNODB STATUS`, which prints both transactions, the exact locks, and
the rolled-back victim.

## Diagnostic Commands

```bash
# The LATEST DETECTED DEADLOCK section shows both transactions and the victim
mysql -u root -p -e "SHOW ENGINE INNODB STATUS\G" | sed -n '/LATEST DETECTED DEADLOCK/,/TRANSACTIONS/p'

# Cumulative deadlock count (rising rate = a real problem, not a one-off)
mysql -u root -p -e "SHOW GLOBAL STATUS LIKE 'Innodb_deadlocks';"

# Currently active transactions and their isolation context
mysql -u root -p -e "SELECT trx_id, trx_state, trx_isolation_level, trx_query \
  FROM information_schema.innodb_trx;"
```

## Expected Results

```text
LATEST DETECTED DEADLOCK
------------------------
*** (1) TRANSACTION: ... UPDATE accounts SET bal=bal-10 WHERE id=1
*** (1) WAITING FOR THIS LOCK TO BE GRANTED: ... record locks ... id=2
*** (2) TRANSACTION: ... UPDATE accounts SET bal=bal+10 WHERE id=2
*** (2) WAITING FOR THIS LOCK TO BE GRANTED: ... record locks ... id=1
*** WE ROLL BACK TRANSACTION (2)
```

This shows the two statements locking rows `id=1` and `id=2` in opposite order —
the classic cycle. A steadily climbing `Innodb_deadlocks` confirms it is
recurring, not incidental.

## Resolution

1. Make every transaction acquire locks in a single, consistent order (e.g.
   always update rows ordered by primary key ascending). This removes the cycle
   at the source:

   ```sql
   -- Touch rows in deterministic order so no two transactions cross
   SELECT id FROM accounts WHERE id IN (1,2) ORDER BY id FOR UPDATE;
   ```
2. Add application-level retry on SQLSTATE `40001` — deadlocks are expected and
   the documented fix is to replay the transaction.
3. Keep transactions short and small to shrink the lock window.
4. Narrow ranges and add covering indexes so range scans take fewer gap locks;
   consider `READ COMMITTED` where gap locks are unnecessary.

## Validation

```bash
mysql -u root -p -e "SHOW GLOBAL STATUS LIKE 'Innodb_deadlocks';"
# After fixing lock order, expect the counter to stop (or rarely) increment.
```

## Prevention

- Standardize lock/update ordering across all code paths.
- Always implement idempotent retry-on-deadlock in the data layer.
- Review range mutations for unnecessary gap locking.
- Track `Innodb_deadlocks` rate as a monitored metric.

## Related Errors

- [MySQL Lock Wait Timeout Exceeded](./mysql-lock-wait-timeout-exceeded.md)
- [MySQL Too Many Connections](./mysql-too-many-connections.md)

## References

- [MySQL: Deadlocks in InnoDB](https://dev.mysql.com/doc/refman/8.0/en/innodb-deadlocks.html)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`mysql` · `innodb` · `deadlock` · `transactions` · `production`
