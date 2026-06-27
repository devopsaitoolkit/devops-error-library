---
title: "RabbitMQ Memory Resource Alarm"
slug: rabbitmq-memory-resource-alarm
technologies: [rabbitmq]
severity: high
tags: [rabbitmq, memory, flow-control, resource-alarm, production]
related: [rabbitmq-disk-free-limit-alarm, rabbitmq-missed-heartbeats]
last_reviewed: 2026-06-27
---

# RabbitMQ Memory Resource Alarm

## Error Message

```text
=WARNING REPORT==== 27-Jun-2026::14:02:11 ===
memory resource limit alarm set on node rabbit@node1.

**********************************************************
*** Publishers will be blocked until this alarm clears ***
**********************************************************
```

```text
vm_memory_high_watermark set. Memory used:8231563264 allowed:8053063680
```

## Description

RabbitMQ continuously tracks the broker's memory usage against a high-watermark
(default 0.4 of installed RAM, or an absolute value). When usage crosses the
watermark, the broker raises a *memory resource alarm* and engages flow control:
it stops reading from the TCP sockets of **all publishing** connections across
the cluster until memory drops back below the limit. Consumers continue, which is
how the broker drains itself back to safety. Publishers appear to hang — this is
deliberate back-pressure, not a crash.

## Technologies

- rabbitmq (memory monitor, credit-based flow control)

## Severity

**high** — all publishers cluster-wide are blocked. Producing applications stall
or time out, and upstream systems back up. Consumers still run, so it is a
partial outage that degrades end-to-end throughput to zero on the publish side.

## Common Causes

1. Large backlogs in non-lazy/classic queues holding message bodies in RAM
   because consumers are too slow or absent.
2. Too many connections/channels, or many unacknowledged messages held in
   memory awaiting ack.
3. The high-watermark is set too high for the container's real memory limit, so
   the broker is OOM-pressured before its own alarm fires.
4. A memory leak or large messages (multi-MB payloads) inflating queue memory.

## Root Cause Analysis

The memory monitor polls RSS every few seconds. Crossing `vm_memory_high_watermark`
flips the alarm; the connection-tracking layer then withholds TCP read credit
from publishing channels, so producers' `basic.publish` calls block. Because the
alarm is cluster-wide, even nodes with free memory block publishers. The alarm
clears only when *all* alarmed nodes fall back below the watermark — usually by
consumers draining queues, by queues paging to disk, or by closing memory-hungry
connections.

## Diagnostic Commands

```bash
# Is a memory (or disk) alarm currently set?
sudo rabbitmq-diagnostics alarms

# Per-category memory breakdown for this node
sudo rabbitmq-diagnostics memory_breakdown

# Current watermark and memory used vs allowed
sudo rabbitmqctl status | grep -A20 memory

# Which queues hold the most messages/memory?
sudo rabbitmqctl list_queues name messages messages_ready memory \
  --sort-by memory
```

## Expected Results

```text
# Alarm active:
Alarms:
 * memory resource limit alarm on node rabbit@node1

# memory_breakdown reveals the dominant consumer, e.g.:
queue_procs: 5.9 gb (72.4%)
binary:      1.1 gb (13.5%)
```

A high `queue_procs`/`binary` share points at a message backlog; a high
`connection_*`/`channel_procs` share points at too many connections or unacked
messages.

## Resolution

1. Restore consumption: start/scale the consumers draining the backed-up queues
   so memory falls below the watermark and the alarm clears on its own.
2. Convert large classic queues to **quorum** queues or enable lazy/stream
   behavior so message bodies live on disk, not RAM.
3. Cap unacked messages with a sensible `basic.qos` prefetch on consumers.
4. Align the watermark with the real memory limit (especially in containers):

   ```ini
   # absolute is safest in containers with a cgroup memory limit
   vm_memory_high_watermark.absolute = 4GB
   ```
5. If runaway, temporarily raise the watermark to unblock publishers, but only
   as a stopgap:

   ```bash
   sudo rabbitmqctl set_vm_memory_high_watermark 0.6
   ```

## Validation

```bash
sudo rabbitmq-diagnostics alarms
# Expect: "No alarms" — publishers resume immediately once the alarm clears.
```

## Prevention

- Use quorum queues and set per-queue length limits / overflow policies.
- Enforce consumer `prefetch` and autoscale consumers on queue depth.
- Set `vm_memory_high_watermark.absolute` to a value below the container limit.
- Alert on `rabbitmq_alarms_memory_used_watermark` before it trips.

## Related Errors

- [RabbitMQ Disk Free Limit Alarm](./rabbitmq-disk-free-limit-alarm.md)
- [RabbitMQ Missed Heartbeats](./rabbitmq-missed-heartbeats.md)

## References

- [RabbitMQ Memory Alarms](https://www.rabbitmq.com/docs/memory)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`rabbitmq` · `memory` · `flow-control` · `resource-alarm` · `production`
