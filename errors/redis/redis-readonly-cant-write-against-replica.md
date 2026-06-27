---
title: "Redis READONLY You Can't Write Against a Read Only Replica"
slug: redis-readonly-cant-write-against-replica
technologies: [redis]
severity: high
tags: [redis, replication, replica, failover, production]
related: [redis-cluster-down, redis-misconf-rdb-snapshot-error]
last_reviewed: 2026-06-27
---

# Redis READONLY You Can't Write Against a Read Only Replica

## Error Message

```text
(error) READONLY You can't write against a read only replica.
```

```text
redis.exceptions.ReadOnlyError: READONLY You can't write against a read only
replica.
```

## Description

A Redis replica defaults to `replica-read-only yes`. When a client sends a write
command (`SET`, `INCR`, `DEL`, …) to a replica, the server rejects it with
`READONLY` because accepting writes on a replica would diverge it from its
primary. The error means the connection landed on a replica rather than the
current primary — usually after a failover changed which node is the primary, or
because the client is configured to talk to a replica address.

## Technologies

- redis (replication / Sentinel / Cluster)

## Severity

**high** — writes from the affected client(s) all fail. After an unhandled
failover this can mean a write outage until clients re-discover the new primary.

## Common Causes

1. A Sentinel or Cluster failover promoted a different node; clients still point
   at the old primary, which is now a replica.
2. The application is hard-coded to a node that is (or became) a replica.
3. A load balancer fronting Redis spreads writes across primary and replicas.
4. The client library isn't topology-aware and doesn't follow `-MOVED`/Sentinel
   primary lookups.

## Root Cause Analysis

Replication in Redis is asynchronous and single-primary: the primary streams its
write stream to replicas, which apply it. To keep that stream authoritative,
replicas refuse direct writes by default. After a failover, the old primary is
reconfigured as a replica of the new one (`REPLICAOF <new-primary>`). Any client
that cached the old primary's address now sends writes to a replica and receives
`READONLY`. The fix is to make clients discover and follow the *current* primary,
not to disable read-only mode.

## Diagnostic Commands

```bash
# Is this node a master or a replica, and who is its master?
redis-cli -h <node> INFO replication

# Read-only flag on the node
redis-cli -h <node> CONFIG GET replica-read-only

# Ask Sentinel which node is the current primary for the monitored set
redis-cli -h <sentinel-host> -p 26379 SENTINEL get-master-addr-by-name <master-name>

# In Cluster mode, see roles and which node owns the slot you're writing
redis-cli -h <node> CLUSTER NODES
redis-cli -h <node> ROLE
```

## Expected Results

```text
$ redis-cli -h <node> INFO replication
# Replication
role:slave
master_host:10.0.1.20
master_port:6379
master_link_status:up
slave_read_only:1
```

`role:slave` (replica) with `slave_read_only:1` confirms the client is talking to
a replica. `SENTINEL get-master-addr-by-name` returns the IP/port of the *real*
primary — compare it to where the client is connecting. The current primary shows
`role:master`.

## Resolution

1. Point the client at the current primary. With Sentinel, configure the client
   to query Sentinel for the master address rather than a fixed host:

   ```text
   Sentinels: sentinel-1:26379, sentinel-2:26379, sentinel-3:26379
   Master name: mymaster
   ```
2. In Cluster mode, use a cluster-aware client that follows `-MOVED` redirects so
   writes always reach the slot's primary.
3. Only as a deliberate, documented choice (e.g., a standalone node mistakenly
   left in replica mode) detach it from replication — never to "allow writes" on
   an actual replica:

   ```bash
   redis-cli -h <node> REPLICAOF NO ONE
   ```
   Do this only if you are certain the node should be the primary, or you risk
   split-brain.
4. After a failover, ensure connection pools are reset so stale primary
   connections are dropped.

## Validation

```bash
redis-cli -h <discovered-primary> ROLE
# Expect: first element "master"
redis-cli -h <discovered-primary> SET diag:probe ok
# Expect: OK  (no READONLY)
```

## Prevention

- Use a Sentinel-aware or Cluster-aware client so primary discovery is automatic.
- Never put primary and replicas behind a write load balancer.
- Test failover regularly (game days) and confirm clients recover writes.
- Keep `replica-read-only yes` — it is a safety guardrail, not the bug.

## Related Errors

- [Redis CLUSTERDOWN The Cluster Is Down](./redis-cluster-down.md)
- [Redis MISCONF Unable to Persist RDB Snapshot](./redis-misconf-rdb-snapshot-error.md)

## References

- [Redis replication documentation](https://redis.io/docs/management/replication/)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`redis` · `replication` · `replica` · `failover` · `production`
