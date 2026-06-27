---
title: "Redis OOM Command Not Allowed When Used Memory > maxmemory"
slug: redis-oom-command-not-allowed-maxmemory
technologies: [redis]
severity: high
tags: [redis, memory, maxmemory, eviction, production]
related: [redis-misconf-rdb-snapshot-error, redis-max-number-of-clients-reached]
last_reviewed: 2026-06-27
---

# Redis OOM Command Not Allowed When Used Memory > maxmemory

## Error Message

```text
(error) OOM command not allowed when used memory > 'maxmemory'.
```

```text
-OOM command not allowed when used memory > 'maxmemory'.
```

## Description

Redis returns this error when the dataset has reached the configured `maxmemory`
limit and the active `maxmemory-policy` cannot free enough memory to accept a new
write. With the default `noeviction` policy, Redis never deletes keys to make
room, so once memory is full every write command (`SET`, `LPUSH`, `HSET`, …) is
rejected with `OOM`. Read-only commands and commands that delete data (`DEL`,
`EXPIRE`, `TTL`) still work.

This is a configuration/capacity condition, not a crash: the instance is healthy
but intentionally protecting itself from exceeding its memory budget.

## Technologies

- redis (memory management / eviction)

## Severity

**high** — all writes fail while the limit is exceeded. For a cache this degrades
hit rate badly; for a primary data store it is a write outage.

## Common Causes

1. `maxmemory-policy noeviction` (the default) combined with a dataset that has
   grown to `maxmemory`.
2. The dataset legitimately exceeds the provisioned memory (under-provisioned).
3. Keys are written without TTLs, so a cache grows unbounded and an eviction
   policy like `allkeys-lru` was expected but `volatile-lru` is set (only keys
   with a TTL are eligible).
4. A large `replication backlog`, client output buffers, or AOF rewrite memory
   pushes `used_memory` past the limit.

## Root Cause Analysis

Before executing a write, Redis checks whether `used_memory` exceeds
`maxmemory`. If it does, it asks the eviction policy to free space. Under
`noeviction` nothing is evicted, so the check fails and the command is rejected
with `OOM`. Under a `volatile-*` policy, only keys that carry an expiration are
candidates — if most keys have no TTL, eviction frees nothing and you still get
`OOM`. The error is therefore the intersection of *how full memory is* and
*which keys the policy is allowed to evict*.

## Diagnostic Commands

```bash
# Used vs configured memory, peak, fragmentation, and eviction stats
redis-cli INFO memory | grep -E 'used_memory:|used_memory_human|maxmemory:|maxmemory_human|maxmemory_policy|mem_fragmentation_ratio'

# Eviction / keyspace-miss counters (rising evicted_keys means the policy is active)
redis-cli INFO stats | grep -E 'evicted_keys|keyspace_misses|expired_keys'

# Current policy and limit
redis-cli CONFIG GET maxmemory
redis-cli CONFIG GET maxmemory-policy

# How many keys exist and how many have a TTL set
redis-cli INFO keyspace

# Biggest keys driving memory use (read-only sampling scan)
redis-cli --bigkeys
```

## Expected Results

```text
used_memory_human:4.00G
maxmemory_human:4.00G
maxmemory_policy:noeviction
evicted_keys:0
```

`used_memory` at or above `maxmemory` with `maxmemory_policy:noeviction` and
`evicted_keys:0` confirms the cause. If the policy is `volatile-lru` but
`INFO keyspace` shows few keys with `expires`, eviction has nothing to remove. A
healthy cache shows `used_memory` below `maxmemory` and a rising `evicted_keys`.

## Resolution

1. If Redis is used purely as a cache, switch to an eviction policy that can
   reclaim memory (this is a `CONFIG SET`, run during a maintenance step, not a
   diagnostic):

   ```bash
   redis-cli CONFIG SET maxmemory-policy allkeys-lru
   ```
   Persist it in `redis.conf` so it survives restart.
2. If Redis is a system of record, do **not** enable eviction — instead raise
   `maxmemory` or add a replica/shard:

   ```bash
   redis-cli CONFIG SET maxmemory 8gb
   ```
3. Reclaim space immediately by deleting or expiring stale keys (`DEL`, `EXPIRE`,
   `UNLINK`).
4. Add TTLs to cache writes so keys self-expire.

## Validation

```bash
redis-cli INFO memory | grep -E 'used_memory_human|maxmemory_human'
redis-cli SET diag:probe ok
# Expect: OK  (no OOM), with used_memory comfortably below maxmemory.
```

## Prevention

- Choose `maxmemory-policy` deliberately: `allkeys-lru`/`allkeys-lfu` for caches,
  `noeviction` only for stores you never want silently trimmed.
- Always set TTLs on cache keys and monitor `evicted_keys` and `used_memory`.
- Provision `maxmemory` below the host's physical RAM to leave room for forks and
  buffers.

## Related Errors

- [Redis MISCONF Unable to Persist RDB Snapshot](./redis-misconf-rdb-snapshot-error.md)
- [Redis max number of clients reached](./redis-max-number-of-clients-reached.md)

## References

- [Redis: Key eviction](https://redis.io/docs/reference/eviction/)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`redis` · `memory` · `maxmemory` · `eviction` · `production`
