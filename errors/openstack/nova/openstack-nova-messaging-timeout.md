---
title: "OpenStack Nova Messaging Timeout"
slug: openstack-nova-messaging-timeout
technologies: [openstack, nova]
severity: high
tags: [openstack, nova, rabbitmq, rpc, messaging, production]
related: [openstack-nova-exceeded-maximum-number-of-retries, openstack-nova-build-of-instance-aborted]
last_reviewed: 2026-06-27
---

# OpenStack Nova Messaging Timeout

## Error Message

```text
nova-api[2055]: ERROR nova.api.openstack.wsgi [req-7e1c...] \
oslo_messaging.exceptions.MessagingTimeout: Timed out waiting for a reply to \
message ID 9f2b4c... 
```

```text
nova-compute[1843]: ERROR oslo.messaging._drivers.impl_rabbit [req-...] \
[a1b2-...] AMQP server on 10.0.0.11:5672 is unreachable: \
[Errno 104] Connection reset by peer. Trying again in 1 seconds.
```

## Description

A `MessagingTimeout` (oslo.messaging over RabbitMQ, the default transport) means
one Nova service sent an RPC call and never received a reply within
`rpc_response_timeout`. Nova is heavily RPC-driven — API → conductor → compute,
scheduler, cells — so a broker problem or an overloaded/unresponsive consumer
surfaces as timeouts that can fail API requests, stall builds, or cause spurious
reschedules. The error points at the messaging layer, not at compute logic.

## Technologies

- openstack (nova-api, nova-conductor, nova-compute, oslo.messaging, RabbitMQ)

## Severity

**high** — control-plane operations time out; builds, migrations, and API calls
fail intermittently or fleet-wide if the broker is degraded.

## Common Causes

1. RabbitMQ is down, partitioned (clustered), or rejecting connections / out of
   memory or disk (free-disk alarm blocking publishes).
2. A target service (e.g. a `nova-compute` host) is down, hung, or far behind on
   its queue, so the reply never comes.
3. Network issues between services and the broker (drops, flapping, MTU).
4. `rpc_response_timeout` too low for a heavily loaded or large deployment.
5. Stale/duplicate queues or a misconfigured `transport_url` after an HA failover.

## Root Cause Analysis

oslo.messaging publishes an RPC `call` to a topic queue and blocks on a reply
queue until `rpc_response_timeout`. The expected consumer must be alive, connected
to the same broker/vhost, and processing its queue. If RabbitMQ is unreachable,
in a free-disk/memory alarm (which silently blocks publishers), partitioned, or
the consumer service is dead or backed up, no reply arrives and oslo raises
`MessagingTimeout`. The `impl_rabbit` "unreachable" lines distinguish a broker
problem from a healthy broker with a dead consumer.

## Diagnostic Commands

```bash
# Are Nova services reporting as up (a down agent = no RPC reply)?
openstack compute service list

# Nova RPC/AMQP errors across services
journalctl -u devstack@n-api -u devstack@n-cond -u devstack@n-cpu \
  --since "15 min ago" | grep -iE "MessagingTimeout|unreachable|AMQP"

# RabbitMQ broker health and alarms (free-disk/memory block publishing)
sudo rabbitmqctl status
sudo rabbitmqctl list_queues name messages consumers | sort -k2 -n -r | head

# Cluster partition check (HA RabbitMQ)
sudo rabbitmqctl cluster_status
```

## Expected Results

```text
# compute service list
| Binary       | Host       | State |
| nova-compute | compute-02 | down  |   <- consumer gone; calls to it time out

# rabbitmqctl status / list_queues
{alarms, [{resource_limit, disk, rabbit@ctrl1}]}   <- disk alarm blocks publishes
nova   12044   0                                    <- queue backed up, no consumers
```

A disk/memory alarm, a partitioned cluster, or a queue with `0 consumers` and a
high message count pinpoints the cause.

## Resolution

1. **Broker alarm:** clear the RabbitMQ disk/memory alarm (free disk, raise
   `disk_free_limit`); publishing resumes once the alarm clears.
2. **Partition:** recover the RabbitMQ cluster from the partition per your HA
   policy, then restart affected Nova services to re-establish channels.
3. **Dead/backed-up consumer:** restart the unresponsive `nova-compute`/service so
   it reconnects and drains its queue.
4. **Network/config:** verify `transport_url` points at the live broker/vhost and
   the path is healthy.
5. **Tuning:** raise `rpc_response_timeout` only if timeouts are due to genuine
   load, not a broken broker.

## Validation

```bash
openstack compute service list   # All services 'up'
# A simple API call that triggers RPC should return promptly
openstack server list --all-projects --limit 1
```

## Prevention

- Monitor RabbitMQ alarms, partitions, queue depth, and consumer counts.
- Alert on `nova-compute` services going `down` (often the real timeout cause).
- Keep RabbitMQ HA/quorum and `disk_free_limit` correctly sized.
- Set `rpc_response_timeout` appropriately for deployment scale.

## Related Errors

- [OpenStack Nova Exceeded Maximum Number of Retries](./openstack-nova-exceeded-maximum-number-of-retries.md)
- [OpenStack Nova Build of Instance Aborted](./openstack-nova-build-of-instance-aborted.md)

## References

- [oslo.messaging configuration](https://docs.openstack.org/oslo.messaging/latest/configuration/opts.html)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`openstack` · `nova` · `rabbitmq` · `rpc` · `messaging` · `production`
