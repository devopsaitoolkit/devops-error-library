---
title: "RabbitMQ Disk Free Limit Alarm"
slug: rabbitmq-disk-free-limit-alarm
technologies: [rabbitmq]
severity: high
tags: [rabbitmq, disk, flow-control, resource-alarm, production]
related: [rabbitmq-memory-resource-alarm, rabbitmq-mnesia-network-partition]
last_reviewed: 2026-06-27
---

# RabbitMQ Disk Free Limit Alarm

## Error Message

```text
=WARNING REPORT==== 27-Jun-2026::21:44:02 ===
disk resource limit alarm set on node rabbit@node1.

**********************************************************
*** Publishers will be blocked until this alarm clears ***
**********************************************************
```

```text
disk_free_limit set. Free bytes:48234496 limit:50000000
```

## Description

RabbitMQ monitors free disk space on the partition holding its data directory.
When free space falls below `disk_free_limit` (default `50MB`, often configured
relative to RAM), the broker raises a *disk resource alarm* and blocks all
publishers cluster-wide — exactly like the memory alarm — to protect itself from
running out of space while persisting messages. Consumers keep running so the
broker can drain and reclaim space. The alarm clears automatically once free disk
rises back above the limit.

## Technologies

- rabbitmq (disk monitor, credit-based flow control)

## Severity

**high** — all publishers across the cluster are blocked; producing applications
stall. If the disk actually fills, persisted messages and Mnesia metadata are at
risk, so this can escalate from degraded throughput to data-integrity problems.

## Common Causes

1. A growing message backlog persisted to disk (durable/quorum queues, large
   bodies) consuming the data partition.
2. Log files (including `crash.log`/server logs) or unrelated files filling the
   same volume.
3. The data directory sharing a partition with other heavy writers.
4. `disk_free_limit` set too low for the workload, so the alarm trips late and
   close to a real full-disk condition.
5. An undersized PersistentVolume / disk in containerized deployments.

## Root Cause Analysis

The disk monitor checks free space on the volume of `RABBITMQ_MNESIA_BASE` every
few seconds. Crossing below `disk_free_limit` flips the alarm; flow control then
withholds read credit from publishing channels broker-wide. Because the limit is
about *headroom*, even a partition that isn't 100% full triggers it — the broker
wants enough room to flush in-flight persistent writes. The alarm is the safety
mechanism; the cause is whatever consumed the headroom (backlog, logs, or other
files on the same mount).

## Diagnostic Commands

```bash
# Is a disk (or memory) alarm currently set?
sudo rabbitmq-diagnostics alarms

# Current free disk vs configured limit, as RabbitMQ sees it
sudo rabbitmq-diagnostics disk_free

# Actual free space on the data partition
df -h "$(sudo rabbitmqctl eval 'rabbit_mnesia:dir().' | tr -d '"')"

# Largest queues by ready messages (disk-resident backlog)
sudo rabbitmqctl list_queues name messages_ready messages_persistent \
  --sort-by messages_ready
```

## Expected Results

```text
# Alarm active:
Alarms:
 * disk resource limit alarm on node rabbit@node1

# disk_free shows free below the limit:
Free disk space: 0.045 gb, low watermark: 0.05 gb
```

`df` confirming a nearly full mount, plus large `messages_ready`/persistent
counts, identifies the backlog as the consumer of space.

## Resolution

1. Free space immediately: drain backlogs by scaling consumers, and remove
   stale/rotated logs from the data volume (never delete RabbitMQ's own data
   files).
2. Move large or durable queues to dedicated/larger volumes; isolate logs onto a
   separate mount.
3. Right-size the limit relative to RAM so it warns with usable headroom:

   ```ini
   disk_free_limit.relative = 1.5
   ```
4. In containers/Kubernetes, expand the PersistentVolume backing the data
   directory.

## Validation

```bash
sudo rabbitmq-diagnostics alarms
# Expect: "No alarms" once free disk rises above the limit; publishers resume.
```

## Prevention

- Alert on free disk approaching `disk_free_limit` well before it trips.
- Cap queue length with policies (`max-length`/overflow) to bound disk growth.
- Keep server logs and message data on separate volumes with rotation.
- Provision disk for peak backlog, not steady-state, plus headroom.

## Related Errors

- [RabbitMQ Memory Resource Alarm](./rabbitmq-memory-resource-alarm.md)
- [RabbitMQ Mnesia Network Partition](./rabbitmq-mnesia-network-partition.md)

## References

- [RabbitMQ Disk Alarms](https://www.rabbitmq.com/docs/disk-alarms)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`rabbitmq` · `disk` · `flow-control` · `resource-alarm` · `production`
