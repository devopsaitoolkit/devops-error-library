---
title: "RabbitMQ NO_ROUTE Unroutable Message"
slug: rabbitmq-no-route-unroutable-message
technologies: [rabbitmq]
severity: medium
tags: [rabbitmq, routing, bindings, unroutable, production]
related: [rabbitmq-precondition-failed-inequivalent-arg, rabbitmq-queue-not-found-404]
last_reviewed: 2026-06-27
---

# RabbitMQ NO_ROUTE Unroutable Message

## Error Message

```text
Basic.Return: reply-code=312 reply-text=NO_ROUTE
  exchange=orders.direct routing-key=order.created
```

```text
pika.exceptions.UnroutableError: 1 unroutable message(s) returned:
  (NO_ROUTE) exchange 'orders.direct' routing_key 'order.created'
```

## Description

When a message is published with the `mandatory` flag set and the exchange cannot
route it to *any* queue, the broker returns it to the publisher via
`basic.return` with reply-code `312 NO_ROUTE`. Without `mandatory`, the same
message is silently **dropped** — no error, no queue, gone. NO_ROUTE means the
exchange exists and accepted the publish, but no binding matched the routing key
(or no queue is bound at all), so there was nowhere to deliver it.

## Technologies

- rabbitmq (exchange routing, bindings, mandatory publishing)

## Severity

**medium** — messages are not delivered. With `mandatory` the publisher learns
and can react; without it, messages vanish silently, which can be a serious data-
loss bug discovered only when downstream data is missing.

## Common Causes

1. No binding exists between the exchange and any queue for that routing key.
2. A routing-key typo or mismatch (e.g. `order.created` vs `orders.created`),
   especially with `direct`/`topic` exchanges.
3. The consumer/queue was not declared/bound before the producer started
   publishing.
4. Publishing to the wrong exchange, or to a `topic` exchange with a pattern
   that doesn't match the binding key.
5. Bindings removed by a redeploy or auto-delete queue that disappeared.

## Root Cause Analysis

An exchange is a routing table, not a store. On `basic.publish`, the broker
matches the message's routing key against the exchange's bindings per the
exchange type: exact match for `direct`, pattern match for `topic`, header match
for `headers`, all-queues for `fanout`. If zero queues match, the exchange has
nowhere to put the message. The broker's only options are to drop it (default) or,
if `mandatory=true`, hand it back via `basic.return`. NO_ROUTE therefore always
points at a binding/routing-key mismatch, not a connectivity or auth problem.

## Diagnostic Commands

```bash
# What bindings exist from the exchange, and to which queues/keys?
sudo rabbitmqctl list_bindings source_name destination_name routing_key \
  --vhost /

# Does the target exchange exist and what type is it?
sudo rabbitmqctl list_exchanges name type durable

# Does the expected destination queue exist?
sudo rabbitmqctl list_queues name messages

# Unroutable/returned message indicators in the log
sudo journalctl -u rabbitmq-server --since "20 min ago" --no-pager \
  | grep -iE "no_route|unroutable"
```

## Expected Results

```text
# No binding matches the published routing key:
source_name    destination_name   routing_key
orders.direct  orders.q           order.shipped   <-- only 'shipped' bound

# Publisher uses 'order.created', which matches nothing -> NO_ROUTE.
```

A binding list with no entry for the routing key (or no binding at all) confirms
the message had nowhere to go.

## Resolution

1. Create the missing binding from the exchange to the queue with the correct
   key:

   ```bash
   sudo rabbitmqctl set_queue_binding   # (illustrative)
   # In application code / definitions, bind explicitly:
   #   queue.bind(exchange="orders.direct", routing_key="order.created")
   ```
2. Fix routing-key/pattern mismatches so producer keys match consumer bindings
   (mind `topic` wildcards `*` and `#`).
3. Ensure queues are declared and bound *before* producers publish.
4. Add an **alternate exchange** to capture unroutable messages so nothing is
   silently lost:

   ```ini
   # via policy: route otherwise-unroutable messages to a catch-all exchange
   ```
   ```bash
   sudo rabbitmqctl set_policy ae "^orders\.direct$" \
     '{"alternate-exchange":"unrouted"}' --apply-to exchanges
   ```

## Validation

```bash
sudo rabbitmqctl list_bindings source_name destination_name routing_key
# Expect: a binding whose routing_key matches what producers publish; test
# publish with mandatory=true returns no basic.return.
```

## Prevention

- Always publish critical messages with `mandatory=true` and handle returns.
- Configure an alternate exchange / dead-letter for unroutable messages.
- Declare and bind queues from a single source of truth before producing.
- Lint/contract-test routing keys between producers and consumers.

## Related Errors

- [RabbitMQ PRECONDITION_FAILED Inequivalent Arg](./rabbitmq-precondition-failed-inequivalent-arg.md)
- [RabbitMQ Queue Not Found 404](./rabbitmq-queue-not-found-404.md)

## References

- [RabbitMQ Exchanges and Routing](https://www.rabbitmq.com/tutorials/amqp-concepts)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`rabbitmq` · `routing` · `bindings` · `unroutable` · `production`
