---
title: "Redis LOADING Redis Is Loading the Dataset in Memory"
slug: redis-loading-dataset-in-memory
technologies: [redis]
severity: medium
tags: [redis, startup, persistence, loading, production]
related: [redis-connection-refused, redis-misconf-rdb-snapshot-error]
last_reviewed: 2026-06-27
---

# Redis LOADING Redis Is Loading the Dataset in Memory

## Error Message

```text
(error) LOADING Redis is loading the dataset in memory
```

```text
redis.exceptions.BusyLoadingError: Redis is loading the dataset in memory
```

## Description

When Redis (re)starts, or when a replica performs a full resynchronization, it
loads the dataset from disk — the RDB file or the AOF — into memory before it can
serve normal traffic. During this window the server is up and accepts
connections, but most commands are rejected with `LOADING`. Only a few commands
(`INFO`, `SUBSCRIBE`, `AUTH`, etc.) are allowed. The error is transient and
clears automatically once loading finishes; how long it lasts depends on dataset
size and disk speed.

## Technologies

- redis (startup / replica full sync / persistence)

## Severity

**medium** — a temporary, self-clearing condition on startup or after a full
resync. It becomes higher impact when the dataset is huge (loading takes many
minutes) or when a replica repeatedly full-resyncs and stays in `LOADING`.

## Common Causes

1. Redis was just (re)started and is loading a large RDB/AOF from disk.
2. A replica triggered a full resynchronization (e.g., the replication backlog
   was exhausted) and is loading the primary's RDB snapshot.
3. Frequent restarts or crashes (OOM, host reboots) put the node back into
   loading repeatedly.
4. A very large dataset combined with slow disk makes the load window long enough
   that clients notice.

## Root Cause Analysis

The keyspace lives in memory, so on start Redis must rebuild it from the
persisted snapshot/log. Until that rebuild completes, answering data commands
would return incomplete results, so Redis guards them with `LOADING`. For
replicas, a full resync first copies the primary's RDB and then loads it — the
same guard applies. The error is therefore expected; the real concern is its
*duration* and any *repetition*, which point to dataset size, disk throughput, or
an unstable node that keeps restarting.

## Diagnostic Commands

```bash
# loading flag plus progress: bytes loaded, total, ETA
redis-cli INFO persistence | grep -E 'loading:|loading_start_time|loading_loaded_perc|loading_eta_seconds|rdb_last_load_keys_loaded'

# Confirm the server is up but loading (PING may still answer pre-load on replicas)
redis-cli PING

# Replication state — is a full sync in progress?
redis-cli INFO replication | grep -E 'role|master_link_status|master_sync_in_progress'

# Size of the RDB/AOF being loaded and how fast disk is
redis-cli CONFIG GET dir
journalctl -u redis-server --since "10 min ago" | grep -iE 'loading|sync|DB loaded'
```

## Expected Results

```text
loading:1
loading_start_time:1719484920
loading_loaded_perc:62.50
loading_eta_seconds:14
```

`loading:1` with a climbing `loading_loaded_perc` and a finite `loading_eta_seconds`
confirms a normal in-progress load. The Redis log printing
`DB loaded from disk: X seconds` marks completion. Once finished, `INFO
persistence` shows `loading:0` and commands succeed.

## Resolution

1. In most cases, simply wait — `LOADING` clears on its own. Make the client
   retry with backoff rather than failing the request:

   ```text
   On BusyLoadingError: retry the command after a short, increasing delay.
   ```
2. If loads are slow, speed them up: use faster disk for the data `dir`, and
   prefer RDB over a large AOF for faster startup, or enable
   `aof-use-rdb-preamble yes` so AOF loads start from a compact RDB.
3. If a replica keeps full-resyncing (and thus keeps loading), enlarge the
   replication backlog so partial resync succeeds instead:

   ```bash
   redis-cli CONFIG SET repl-backlog-size 256mb
   ```
4. If the node keeps restarting into `LOADING`, fix the crash cause (OOM, host
   instability) so it stays up.

## Validation

```bash
redis-cli INFO persistence | grep loading:
# Expect: loading:0
redis-cli GET diag:probe
# Expect: a value or (nil), but NOT a LOADING error.
```

## Prevention

- Configure clients to retry on `BusyLoadingError`/`LOADING` with backoff.
- Place the data directory on fast storage to shorten load times.
- Size `repl-backlog-size` so brief disconnects use partial (not full) resync.
- Keep nodes stable so they aren't repeatedly re-entering the loading phase.

## Related Errors

- [Redis Connection Refused](./redis-connection-refused.md)
- [Redis MISCONF Unable to Persist RDB Snapshot](./redis-misconf-rdb-snapshot-error.md)

## References

- [Redis persistence documentation](https://redis.io/docs/management/persistence/)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`redis` · `startup` · `persistence` · `loading` · `production`
