---
title: "MySQL Lock Wait Timeout Exceeded"
slug: mysql-lock-wait-timeout-exceeded
technologies: [mysql]
severity: high
tags: [mysql, innodb, locking, transactions, production]
related: [mysql-deadlock-found-when-trying-to-get-lock, mysql-too-many-connections]
last_reviewed: 2026-06-27
---

# MySQL Lock Wait Timeout Exceeded

## Error Message

```text
ERROR 1205 (HY000): Lock wait timeout exceeded; try restarting transaction
```

## Description

`ERROR 1205 (HY000)` is raised by InnoDB when a transaction waited longer than
`innodb_lock_wait_timeout` (default 50 seconds) to acquire a row lock that
another transaction still holds, and gave up. Unlike a deadlock — where InnoDB
detects a cycle and rolls one victim back immediately — a lock-wait timeout means
no cycle exists; one transaction is simply holding a lock far too long
(frequently an idle transaction that started, locked rows, and never committed).

## Technologies

- mysql (InnoDB row-level locking)

## Severity

**high** — the blocked statement fails and its transaction may need a full retry.
Under contention this cascades: many transactions queue behind one stuck lock
holder, throughput collapses, and the application sees widespread timeouts.

## Common Causes

1. A long-running or *idle* transaction holds row locks without committing
   (often "open transaction" left by application code that forgot to commit).
2. A batch job locks many rows (large `UPDATE`/`DELETE`) and runs for minutes
   while OLTP traffic waits behind it.
3. Hot-row contention — many transactions update the same row (a counter, a
   single inventory record).
4. Lock-order differences between code paths increase contention windows.
5. `innodb_lock_wait_timeout` is set too low for a legitimately slow operation.

## Root Cause Analysis

InnoDB takes row (and gap/next-key) locks for writes and for locking reads
(`SELECT ... FOR UPDATE`). A second transaction needing the same lock blocks
until the holder commits or rolls back. If that does not happen within
`innodb_lock_wait_timeout`, InnoDB aborts the *waiter* (not the holder) with
1205. The classic production signature is an application connection that issued
a write inside a transaction and then went idle — `TRX_STATE: RUNNING` with no
recent query — pinning locks indefinitely.

## Diagnostic Commands

```bash
# Who is waiting on whom (the blocking/blocked relationship)
mysql -u root -p -e "SELECT * FROM sys.innodb_lock_waits\G"

# Active InnoDB transactions, their state, and how long they have run
mysql -u root -p -e "SELECT trx_id, trx_state, trx_started, trx_mysql_thread_id, \
  trx_query FROM information_schema.innodb_trx ORDER BY trx_started;"

# Specific locks currently held/requested (MySQL 8.0+)
mysql -u root -p -e "SELECT * FROM performance_schema.data_lock_waits\G"

# Find the idle-in-transaction connection
mysql -u root -p -e "SHOW PROCESSLIST;"
```

## Expected Results

```text
*************************** 1. row ***************************
waiting_trx_id: 4212
waiting_query: UPDATE inventory SET qty = qty-1 WHERE id = 7
blocking_trx_id: 4198
blocking_query: NULL            <- holder is idle, no current query
```

A `blocking_query: NULL` with an old `trx_started` is the smoking gun: the
blocker is idle inside an open transaction.

## Resolution

1. Identify and end the offending holder. Find its thread id from
   `innodb_trx`/`innodb_lock_waits`, then kill it (rolls its transaction back):

   ```sql
   KILL <blocking_trx_mysql_thread_id>;
   ```
2. Fix the application: commit/rollback promptly, keep transactions short, and
   never leave a transaction open across user think-time or network calls.
3. For large batch writes, chunk them (e.g. delete in batches of a few thousand
   rows, committing between chunks) so locks are released frequently.
4. Reduce hot-row contention by sharding the counter or using atomic
   single-statement updates instead of read-modify-write transactions.
5. If the operation is legitimately slow, raise `innodb_lock_wait_timeout` for
   that session only — do not raise it globally to mask a leak.

## Validation

```bash
mysql -u root -p -e "SELECT COUNT(*) AS waiters FROM sys.innodb_lock_waits;"
# Expect 0 waiters and the previously blocked statement now succeeding.
```

## Prevention

- Enforce short transactions; commit immediately after the write.
- Alert on transactions running longer than N seconds (`innodb_trx.trx_started`).
- Batch and throttle large mutations during off-peak windows.
- Use consistent lock ordering and atomic statements for hot rows.

## Related Errors

- [MySQL Deadlock Found When Trying to Get Lock](./mysql-deadlock-found-when-trying-to-get-lock.md)
- [MySQL Too Many Connections](./mysql-too-many-connections.md)

## References

- [MySQL: InnoDB Locking](https://dev.mysql.com/doc/refman/8.0/en/innodb-locking.html)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`mysql` · `innodb` · `locking` · `transactions` · `production`
