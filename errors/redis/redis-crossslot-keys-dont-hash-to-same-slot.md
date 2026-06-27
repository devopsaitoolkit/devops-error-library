---
title: "Redis CROSSSLOT Keys Don't Hash to the Same Slot"
slug: redis-crossslot-keys-dont-hash-to-same-slot
technologies: [redis]
severity: medium
tags: [redis, cluster, slots, hashtags, production]
related: [redis-cluster-down, redis-readonly-cant-write-against-replica]
last_reviewed: 2026-06-27
---

# Redis CROSSSLOT Keys Don't Hash to the Same Slot

## Error Message

```text
(error) CROSSSLOT Keys in request don't hash to the same slot
```

```text
redis.cluster.exceptions.RedisClusterException: CROSSSLOT Keys in request don't
hash to the same slot
```

## Description

In Redis Cluster a key maps to one of 16384 hash slots via `CRC16(key) mod
16384`, and each slot lives on exactly one primary. Multi-key commands
(`MGET`, `MSET`, `SINTERSTORE`, `RENAME`, `SUNIONSTORE`, Lua scripts touching
several keys, transactions, etc.) must operate on keys that all live in the same
slot, because a single node can't atomically act on keys it doesn't own. When the
keys in one command hash to different slots, the cluster rejects it with
`CROSSSLOT`.

## Technologies

- redis (cluster mode / slot hashing)

## Severity

**medium** — it's a correctness/usage error, not an outage: the affected
multi-key operations fail while single-key operations and properly-grouped
multi-key operations keep working. It typically surfaces when migrating a
standalone app to Cluster.

## Common Causes

1. A multi-key command (`MSET`, `MGET`, `SINTERSTORE`, `RENAME`, …) was issued
   with keys that hash to different slots.
2. A `MULTI`/`EXEC` transaction or Lua `EVAL` touches keys spread across slots.
3. Code written for standalone Redis assumed all keys are co-located and was
   moved to Cluster unchanged.
4. Hash tags were intended to co-locate keys but are inconsistent or missing
   (e.g., `{user:1}:a` vs `user:1:b`).

## Root Cause Analysis

Cluster shards data by slot, and atomic multi-key semantics only hold within a
single node. To let applications force related keys onto the same slot, Redis
uses **hash tags**: if a key contains a substring inside `{...}`, only that
substring is hashed. So `{user:1000}:profile` and `{user:1000}:sessions` both
hash on `user:1000` and land on the same slot, making multi-key ops legal.
`CROSSSLOT` simply means the keys in the command computed to more than one slot,
so no single node can serve the request atomically.

## Diagnostic Commands

```bash
# Which slot does each key hash to? (different numbers -> CROSSSLOT)
redis-cli CLUSTER KEYSLOT user:1000:profile
redis-cli CLUSTER KEYSLOT user:1000:sessions

# With hash tags, confirm they collapse to the same slot
redis-cli CLUSTER KEYSLOT '{user:1000}:profile'
redis-cli CLUSTER KEYSLOT '{user:1000}:sessions'

# Which node owns a given slot (to understand placement)
redis-cli CLUSTER NODES
redis-cli CLUSTER SLOTS

# Confirm the cluster itself is healthy (rule out CLUSTERDOWN)
redis-cli CLUSTER INFO | grep cluster_state
```

## Expected Results

```text
$ redis-cli CLUSTER KEYSLOT user:1000:profile
(integer) 1239
$ redis-cli CLUSTER KEYSLOT user:1000:sessions
(integer) 9544          # different slot -> CROSSSLOT on a multi-key command

$ redis-cli CLUSTER KEYSLOT '{user:1000}:profile'
(integer) 1393
$ redis-cli CLUSTER KEYSLOT '{user:1000}:sessions'
(integer) 1393          # same slot -> multi-key command is now allowed
```

Different `KEYSLOT` values for keys used together confirm the cause. After adding
a shared hash tag, both keys report the same slot.

## Resolution

1. Add a consistent **hash tag** to related keys so they co-locate on one slot:

   ```text
   Before:  MSET user:1000:profile "..."  user:1000:sessions "..."
   After:   MSET {user:1000}:profile "..." {user:1000}:sessions "..."
   ```
2. For Lua scripts and transactions, ensure every key passed touches the same
   slot (declare keys via `KEYS[]` and tag them).
3. Where co-location isn't possible, split the operation into per-slot commands
   and combine results in the application (you lose cross-key atomicity).
4. Use a cluster-aware client that can fan out `MGET`/pipelines across slots if
   atomicity isn't required.

## Validation

```bash
redis-cli CLUSTER KEYSLOT '{user:1000}:profile'
redis-cli CLUSTER KEYSLOT '{user:1000}:sessions'
# Expect: identical slot numbers.
redis-cli -c MSET '{user:1000}:profile' p '{user:1000}:sessions' s
# Expect: OK  (no CROSSSLOT)
```

## Prevention

- Design key schemas with hash tags up front for any keys used together.
- Lint/test multi-key commands against a cluster in CI, not just standalone Redis.
- Document which key groups must share a hash tag.
- Prefer single-key operations where atomic grouping isn't truly needed.

## Related Errors

- [Redis CLUSTERDOWN The Cluster Is Down](./redis-cluster-down.md)
- [Redis READONLY Can't Write Against a Replica](./redis-readonly-cant-write-against-replica.md)

## References

- [Redis Cluster specification: hash tags](https://redis.io/docs/reference/cluster-spec/#hash-tags)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`redis` · `cluster` · `slots` · `hashtags` · `production`
