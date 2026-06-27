---
title: "Redis CLUSTERDOWN The Cluster Is Down"
slug: redis-cluster-down
technologies: [redis]
severity: critical
tags: [redis, cluster, slots, sharding, production]
related: [redis-crossslot-keys-dont-hash-to-same-slot, redis-readonly-cant-write-against-replica]
last_reviewed: 2026-06-27
---

# Redis CLUSTERDOWN The Cluster Is Down

## Error Message

```text
(error) CLUSTERDOWN The cluster is down
```

```text
(error) CLUSTERDOWN Hash slot not served
```

## Description

In Redis Cluster the 16384 hash slots are distributed across primary nodes. If
any slot has no responsible primary that is reachable, the cluster considers
itself unhealthy and — with the default `cluster-require-full-coverage yes` —
refuses to serve **any** command until full coverage is restored, returning
`CLUSTERDOWN`. The error means at least one shard's primary is down with no
replica promoted to cover its slots, or a partition has left part of the keyspace
unowned.

## Technologies

- redis (cluster mode / slot ownership)

## Severity

**critical** — with full-coverage required, the entire cluster stops serving
even keys on healthy shards. This is typically a full outage of the data tier.

## Common Causes

1. A primary node failed and no replica was available (or eligible) to take over
   its slots.
2. A network partition isolated nodes so a majority of primaries can't agree the
   cluster is healthy.
3. Slots were left unassigned after a botched `reshard`/`addslots`/node removal.
4. Too few primaries reachable to satisfy the cluster's quorum, marking it
   `fail`.
5. Replicas exist but `cluster-replica-validity-factor` ruled them too stale to
   promote.

## Root Cause Analysis

Each primary owns a contiguous set of slots; replicas of that primary can be
promoted on failure. The cluster bus gossips node health. When primaries
mutually agree (via failure reports and quorum) that a primary is unreachable and
no replica takes over, the slots it owned become unserved. Because the default
policy requires *full* slot coverage, the cluster transitions to state `fail` and
rejects commands cluster-wide — a deliberate safety choice to avoid serving a
partial, inconsistent keyspace.

## Diagnostic Commands

```bash
# Overall cluster health: state, slots assigned, known/size nodes
redis-cli -c CLUSTER INFO

# Node roles, link state, and which slots each primary owns
redis-cli CLUSTER NODES

# Quick coverage / consistency check across the cluster
redis-cli --cluster check <any-node-ip>:6379

# Slots currently served by this node (gaps reveal unowned ranges)
redis-cli CLUSTER SLOTS

# Why a node sees others as failing — link/fail flags in the logs
journalctl -u redis-server --since "15 min ago" | grep -iE 'cluster|fail|slot'
```

## Expected Results

```text
$ redis-cli CLUSTER INFO
cluster_state:fail
cluster_slots_assigned:16384
cluster_slots_ok:10923
cluster_slots_pfail:0
cluster_slots_fail:5461
cluster_known_nodes:6
```

`cluster_state:fail` with `cluster_slots_fail` greater than 0 (or
`cluster_slots_assigned` below 16384) confirms missing coverage. In
`CLUSTER NODES`, a primary marked `master,fail` with no promoted replica is the
offending shard. A healthy cluster shows `cluster_state:ok` and
`cluster_slots_ok:16384`.

## Resolution

1. Identify the failed shard from `CLUSTER NODES` (`master,fail`) and bring its
   primary or a replica back. If a replica is healthy, force promotion from a
   replica of that shard:

   ```bash
   redis-cli -h <replica-of-failed-shard> CLUSTER FAILOVER TAKEOVER
   ```
   Use `TAKEOVER` only when the primary is truly gone — it skips quorum.
2. If a partition caused it, restore network connectivity between nodes (the
   cluster usually self-heals once the bus reconnects).
3. If slots are genuinely unassigned after a bad reshard, re-assign them:

   ```bash
   redis-cli --cluster fix <any-node-ip>:6379
   ```
4. Add/replace the missing node and let it become a replica so the shard has
   redundancy again.

## Validation

```bash
redis-cli CLUSTER INFO | grep -E 'cluster_state|cluster_slots_ok'
# Expect: cluster_state:ok and cluster_slots_ok:16384
redis-cli --cluster check <any-node-ip>:6379
# Expect: "All 16384 slots covered."
```

## Prevention

- Run at least one replica per primary, spread across failure domains.
- Keep an odd number of primaries (>=3) so failover quorum is achievable.
- Monitor `cluster_state` and `cluster_slots_ok`; alert on any `fail`/`pfail`.
- Validate `--cluster check` after every reshard or topology change.

## Related Errors

- [Redis CROSSSLOT Keys Don't Hash to the Same Slot](./redis-crossslot-keys-dont-hash-to-same-slot.md)
- [Redis READONLY Can't Write Against a Replica](./redis-readonly-cant-write-against-replica.md)

## References

- [Redis Cluster specification](https://redis.io/docs/reference/cluster-spec/)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`redis` · `cluster` · `slots` · `sharding` · `production`
