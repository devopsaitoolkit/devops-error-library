---
title: "RabbitMQ Queue Not Found 404"
slug: rabbitmq-queue-not-found-404
technologies: [rabbitmq]
severity: medium
tags: [rabbitmq, queues, not-found, routing, production]
related: [rabbitmq-precondition-failed-inequivalent-arg, rabbitmq-no-route-unroutable-message]
last_reviewed: 2026-06-27
---

# RabbitMQ Queue Not Found 404

## Error Message

```text
=ERROR REPORT==== 27-Jun-2026::08:55:13 ===
operation basic.consume caused a channel exception not_found:
NOT_FOUND - no queue 'orders' in vhost '/'
```

```text
amqp.exceptions.NotFound: (404) NOT_FOUND - no queue 'orders' in vhost '/'
```

## Description

`NOT_FOUND` (AMQP reply-code `404`) is raised when an operation references a
queue (or exchange) that does not exist in the target vhost — for example a
`basic.consume`, `queue.bind`, or a passive `queue.declare`. The broker closes
the channel. It differs from `NO_ROUTE` (the exchange exists but routes nowhere)
and from `PRECONDITION_FAILED` (it exists but with different args): here the named
entity is simply absent in that vhost.

## Technologies

- rabbitmq (queue lookup, channel exceptions, virtual hosts)

## Severity

**medium** — the consuming or binding operation fails and its channel closes, so
that consumer cannot start. Impact is scoped to clients referencing the missing
queue; producers to a still-valid exchange may be unaffected.

## Common Causes

1. The consumer references a queue that was never declared, or that the producer
   side is responsible for creating but hasn't yet.
2. An **auto-delete** or **exclusive** queue disappeared when its last consumer
   or its declaring connection went away.
3. Wrong **vhost** — the queue exists in `/prod` but the client connects to `/`.
4. A typo in the queue name, or environment drift (queue name differs per env).
5. A `queue.declare` with `passive=true` against a queue that hasn't been created.

## Root Cause Analysis

Queues are scoped to a vhost and must exist before they can be consumed from or
bound. RabbitMQ does not auto-create a queue on `basic.consume`; only an active
`queue.declare` creates one. If the client assumes the queue exists (passive
declare or direct consume) and it does not — because nobody declared it, it was
auto-deleted, or the client is in the wrong vhost — the broker returns `404
NOT_FOUND`. Auto-delete/exclusive lifecycles are a frequent surprise: the queue
vanishes the instant its last consumer/owner disconnects, so a reconnecting
client finds it gone.

## Diagnostic Commands

```bash
# Does the queue exist, and in which vhost?
sudo rabbitmqctl list_queues name messages --vhost /
sudo rabbitmqctl list_queues name messages --vhost /prod

# Is the queue auto-delete or exclusive (so it may vanish)?
sudo rabbitmqctl list_queues name auto_delete exclusive durable

# Which vhosts exist (catch wrong-vhost mistakes)?
sudo rabbitmqctl list_vhosts

# NOT_FOUND occurrences in the log
sudo journalctl -u rabbitmq-server --since "20 min ago" --no-pager \
  | grep -i "not_found"
```

## Expected Results

```text
# Queue absent in the vhost the client uses:
Listing queues for vhost / ...
name    messages
# (orders not listed)

# But present in another vhost, revealing a wrong-vhost connection:
Listing queues for vhost /prod ...
orders  142
```

## Resolution

1. Declare the queue (actively) before consuming, ideally as durable so it
   survives restarts:

   ```bash
   # Declarations are normally done by the app; for a quick fix you can use the
   # management HTTP API or have the owning service create it on startup.
   ```
2. Connect to the correct vhost — fix the connection URI/vhost in the client
   config (`amqp://user:pass@host/%2fprod`).
3. For `auto-delete`/`exclusive` queues, ensure the declaring connection stays up
   for the queue's lifetime, or make the queue durable and non-exclusive.
4. Align queue names across environments and remove typos.

## Validation

```bash
sudo rabbitmqctl list_queues name --vhost /
# Expect: the queue appears in the vhost the client connects to; the consumer
# starts without a NOT_FOUND channel exception.
```

## Prevention

- Have the owning service declare durable queues at startup before consumers run.
- Avoid auto-delete/exclusive queues for shared, long-lived workloads.
- Pin the vhost explicitly per environment and validate it in config.
- Provision queues from a definitions file / operator so they always exist.

## Related Errors

- [RabbitMQ PRECONDITION_FAILED Inequivalent Arg](./rabbitmq-precondition-failed-inequivalent-arg.md)
- [RabbitMQ No Route Unroutable Message](./rabbitmq-no-route-unroutable-message.md)

## References

- [RabbitMQ Queues](https://www.rabbitmq.com/docs/queues)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`rabbitmq` · `queues` · `not-found` · `routing` · `production`
