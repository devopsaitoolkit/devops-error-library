---
title: "RabbitMQ Mnesia Network Partition"
slug: rabbitmq-mnesia-network-partition
technologies: [rabbitmq]
severity: critical
tags: [rabbitmq, clustering, network-partition, split-brain, production]
related: [rabbitmq-missed-heartbeats, rabbitmq-connection-refused]
last_reviewed: 2026-06-27
---

# RabbitMQ Mnesia Network Partition

## Error Message

```text
=ERROR REPORT==== 27-Jun-2026::03:18:42 ===
Mnesia(rabbit@node1): ** ERROR ** mnesia_event got
  {inconsistent_database, running_partitioned_network, rabbit@node2}
```

```text
Network partition detected
Mnesia reports that this RabbitMQ cluster has experienced a network partition.
There is a partition between nodes [rabbit@node2] and [rabbit@node1].
```

## Description

RabbitMQ clusters share metadata (queues, exchanges, bindings, users) through
Mnesia, Erlang's distributed database. When nodes lose contact with each other
for longer than `net_ticktime`, Erlang declares the peers down. If they later
reconnect, Mnesia may find that *both* sides accepted writes while separated —
an `inconsistent_database` / `running_partitioned_network` condition, commonly
called split-brain. Depending on the configured partition-handling strategy, the
broker may keep both halves running independently (divergent state) or shut down
the losing side.

## Technologies

- rabbitmq (Mnesia metadata store, Erlang distribution / clustering)

## Severity

**critical** — the cluster's metadata can diverge. Queues and messages may exist
on only one side, clients connected to different nodes see different state, and
resolving it can require discarding one partition's data. This risks message loss
and inconsistent routing across the cluster.

## Common Causes

1. Transient network loss between nodes (cloud AZ blip, switch reboot, packet
   loss) exceeding `net_ticktime`.
2. Long stop-the-world pauses (GC, swapping under memory pressure) that make a
   node unresponsive to Erlang ticks.
3. An overly aggressive `net_ticktime`, or clustering across high-latency links
   (cross-region) that should not be a single cluster.
4. A node being paused/throttled (CPU steal, container resource limits) so it
   misses ticks.

## Root Cause Analysis

Erlang's distribution sends periodic *tick* messages between connected nodes. If
`4 * net_ticktime / 4` ticks are missed (≈60s by default), the node is declared
down and the cluster splits. While split, classic queues and metadata on each
side accept changes locally. On reconnect, Mnesia detects the two diverged
copies and refuses to silently merge them, emitting `inconsistent_database`. The
`cluster_partition_handling` setting decides the outcome: `ignore` leaves both
halves up (you must fix it), `pause_minority`/`autoheal` automatically pick a
winner and restart the loser.

## Diagnostic Commands

```bash
# Are partitions currently reported? (key field: "partitions")
sudo rabbitmqctl cluster_status

# Dedicated partition check (non-zero exit if a partition is detected)
sudo rabbitmq-diagnostics check_if_node_is_quorum_critical
sudo rabbitmq-diagnostics cluster_status

# Partition entries in the broker log
sudo journalctl -u rabbitmq-server --since today --no-pager \
  | grep -iE "partition|inconsistent_database"

# Confirm inter-node reachability on the Erlang distribution port (25672)
ss -tnp '( dport = :25672 or sport = :25672 )'
```

## Expected Results

```text
# Healthy: empty partitions list
Network Partitions
(none)

# Partitioned:
Network Partitions
 Node rabbit@node1 cannot communicate with rabbit@node2
```

A non-empty `Network Partitions` section, or `inconsistent_database` in the log,
confirms split-brain.

## Resolution

1. Decide the authoritative side (usually the larger partition or the one with
   the most recent valid data).
2. Restart the nodes on the **losing** side so they rejoin and resync from the
   winner. Restart, don't just reconnect — this discards their diverged copy:

   ```bash
   sudo systemctl restart rabbitmq-server   # on each losing node
   ```
3. Configure automatic handling so future partitions self-resolve:

   ```ini
   cluster_partition_handling = pause_minority
   ```
4. Migrate classic mirrored queues to **quorum queues**, which use Raft and
   tolerate partitions without split-brain on the queue contents.

## Validation

```bash
sudo rabbitmqctl cluster_status
# Expect: "Network Partitions (none)" and all nodes listed as running.
```

## Prevention

- Use `pause_minority` with an odd number of nodes so a clear majority survives.
- Prefer quorum queues and quorum-based metadata over classic mirroring.
- Never cluster across high-latency/unreliable links; federate or shovel instead.
- Give nodes adequate CPU/memory so they never miss ticks under load.

## Related Errors

- [RabbitMQ Missed Heartbeats](./rabbitmq-missed-heartbeats.md)
- [RabbitMQ Connection Refused](./rabbitmq-connection-refused.md)

## References

- [RabbitMQ Clustering and Network Partitions](https://www.rabbitmq.com/docs/partitions)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`rabbitmq` · `clustering` · `network-partition` · `split-brain` · `production`
