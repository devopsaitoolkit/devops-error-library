---
title: "RabbitMQ PRECONDITION_FAILED Inequivalent Arg"
slug: rabbitmq-precondition-failed-inequivalent-arg
technologies: [rabbitmq]
severity: medium
tags: [rabbitmq, queues, declaration, precondition-failed, production]
related: [rabbitmq-queue-not-found-404, rabbitmq-no-route-unroutable-message]
last_reviewed: 2026-06-27
---

# RabbitMQ PRECONDITION_FAILED Inequivalent Arg

## Error Message

```text
=ERROR REPORT==== 27-Jun-2026::13:15:48 ===
operation queue.declare caused a channel exception precondition_failed:
PRECONDITION_FAILED - inequivalent arg 'durable' for queue 'orders' in vhost '/':
received 'true' but current is 'false'
```

```text
PRECONDITION_FAILED - inequivalent arg 'x-message-ttl' for queue 'orders'
in vhost '/': received '60000' but current is 'none'
```

## Description

`queue.declare` (and `exchange.declare`) is idempotent *only* if the requested
properties exactly match an existing entity. If a queue or exchange named the
same already exists with different attributes — `durable`, `auto-delete`,
`exclusive`, or any `x-arguments` like `x-message-ttl`, `x-max-length`,
`x-dead-letter-exchange`, or queue type — the broker raises
`PRECONDITION_FAILED - inequivalent arg ...` and closes the channel. It is a
declaration conflict: two clients (or two code versions) disagree about how the
entity should be defined.

## Technologies

- rabbitmq (queue/exchange declaration, channel exceptions)

## Severity

**medium** — the channel is closed and the declaring client cannot use that
queue/exchange until reconciled. Existing traffic on the already-declared entity
continues, so impact is scoped to the conflicting client, but it can block
deploys and consumer startup.

## Common Causes

1. A code change altered a queue's arguments (e.g. added `x-message-ttl` or
   switched `durable`) while the old queue still exists.
2. Two services declare the same queue with different settings (a quorum vs.
   classic type, different TTL or max-length).
3. A manually created queue (UI/CLI) differs from what the app declares.
4. Mismatched dead-letter or overflow arguments between producer and consumer
   code.

## Root Cause Analysis

RabbitMQ stores the canonical definition of a queue/exchange when it is first
declared. Every later `declare` is checked field-by-field against that stored
definition; any single mismatch — including queue type and each `x-argument` —
fails the precondition. The broker will not silently mutate an existing entity,
because doing so could break other clients relying on the original behavior.
Therefore the conflict persists until either the code matches the existing
entity or the entity is recreated with the new definition.

## Diagnostic Commands

```bash
# Inspect the existing queue's actual properties and arguments
sudo rabbitmqctl list_queues name durable auto_delete arguments type \
  --vhost /

# Same for exchanges, if the conflict is on an exchange.declare
sudo rabbitmqctl list_exchanges name type durable auto_delete arguments

# The precondition error lines in the broker log
sudo journalctl -u rabbitmq-server --since "20 min ago" --no-pager \
  | grep -i "precondition_failed"
```

## Expected Results

```text
# The stored definition differs from what the client sends:
name    durable  auto_delete  arguments                    type
orders  false    false        []                           classic

# Client is declaring durable=true with x-message-ttl=60000, which does
# not match -> PRECONDITION_FAILED.
```

## Resolution

1. Decide the correct, intended definition and make the application match the
   *existing* queue, or recreate the queue with the new definition.
2. To recreate (causes downtime for that queue — drains/deletes messages):

   ```bash
   # Confirm it is empty/drained first, then delete and let the app redeclare
   sudo rabbitmqctl list_queues name messages
   sudo rabbitmqctl delete_queue orders --vhost /
   ```
3. Prefer setting mutable behavior via **policies** (TTL, max-length, DLX)
   instead of declare-time `x-arguments`, so changes don't require recreation:

   ```bash
   sudo rabbitmqctl set_policy orders-ttl "^orders$" \
     '{"message-ttl":60000}' --apply-to queues
   ```
4. Roll out the matching client code everywhere so declarations agree.

## Validation

```bash
sudo rabbitmqctl list_queues name durable arguments type
# Expect: the queue's properties match what every client declares; no new
# PRECONDITION_FAILED entries appear in the log.
```

## Prevention

- Define queues/exchanges in one place (a definitions file or a single owner
  service); other clients declare passively or not at all.
- Use policies for TTL/length/DLX so operational changes don't conflict with
  declarations.
- Version and review any change to queue arguments as a breaking change.

## Related Errors

- [RabbitMQ Queue Not Found 404](./rabbitmq-queue-not-found-404.md)
- [RabbitMQ No Route Unroutable Message](./rabbitmq-no-route-unroutable-message.md)

## References

- [RabbitMQ Queues](https://www.rabbitmq.com/docs/queues)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`rabbitmq` · `queues` · `declaration` · `precondition-failed` · `production`
