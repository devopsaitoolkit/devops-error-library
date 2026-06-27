---
title: "OpenStack Nova RabbitMQ Missed Heartbeats"
slug: openstack-nova-rabbitmq-missed-heartbeats
technologies: [openstack, nova]
severity: high
tags: [openstack, nova, rabbitmq, oslo-messaging, heartbeat, production]
related: [openstack-nova-no-valid-host-was-found]
last_reviewed: 2026-06-27
---

# OpenStack Nova RabbitMQ Missed Heartbeats

## Error Message

```text
nova-compute[2901]: ERROR oslo.messaging._drivers.impl_rabbit [req-...] \
Connection failed: [Errno 104] Connection reset by peer (retrying in 1.0 seconds): \
ConnectionResetError: [Errno 104] Connection reset by peer
```

```text
rabbitmq: missed heartbeats from client, timeout: 60s
nova-compute[2901]: WARNING oslo.messaging._drivers.impl_rabbit [req-...] \
Unexpected error during heartbeat thread processing, retrying...: \
AMQPError: Server unexpectedly closed connection
```

## Description

Nova services talk to each other over `oslo.messaging` using RabbitMQ (AMQP). Each
connection runs a heartbeat so both ends can detect a dead peer. "Missed
heartbeats" means RabbitMQ stopped receiving heartbeat frames from a Nova client
(or vice versa) within the timeout, so the broker tears the connection down. The
client then logs connection resets/AMQP errors and reconnects. Frequent
missed-heartbeat churn makes RPC calls (scheduling, instance actions, service
updates) slow, time out, or fail.

## Technologies

- openstack (nova-compute / nova-conductor / nova-scheduler via oslo.messaging, RabbitMQ broker)

## Severity

**high** — RPC instability shows up as compute services flapping to `down`,
instance operations timing out, and `NoValidHost` from a scheduler that cannot see
healthy computes. Sustained breakage is effectively a control-plane outage.

## Common Causes

1. The heartbeat thread is starved — a blocking/CPU-bound greenthread or eventlet
   monkey-patch issue prevents heartbeat frames from being sent in time.
2. Network problems between Nova hosts and RabbitMQ — packet loss, a firewall/NAT
   or load balancer idle-timeout dropping AMQP (5672/5671) connections.
3. RabbitMQ overload — high memory/disk alarm causing it to throttle or drop
   connections (broker blocked on `vm_memory_high_watermark`).
4. Mismatched `[oslo_messaging_rabbit] heartbeat_timeout_threshold` vs broker
   expectations, or `heartbeat_in_pthread` not enabled where it is needed.
5. RabbitMQ cluster partition/failover so clients keep getting reset.

## Root Cause Analysis

AMQP heartbeats are small frames exchanged on an interval (timeout/2). If a Nova
process is busy and its heartbeat greenthread cannot run, or if the network drops
the idle connection, RabbitMQ sees no heartbeat within the negotiated timeout and
closes the channel — logging "missed heartbeats from client." The client observes
a reset and reconnects, but in-flight RPCs are lost and service heartbeats to
nova-conductor lag, so the service can be marked `down`. Thus the symptom is
messaging-layer, but the root cause is CPU starvation, network, or broker
resource pressure.

## Diagnostic Commands

```bash
# Nova messaging errors and reconnect churn
journalctl -u devstack@n-cpu --since "20 min ago" | grep -iE "heartbeat|impl_rabbit|connection reset"

# RabbitMQ side: who is missing heartbeats / connection churn
journalctl -u rabbitmq-server --since "20 min ago" | grep -iE "missed heartbeats|closing|connection"

# Broker health, alarms, and partitions
rabbitmqctl status | grep -iE "alarm|memory|disk"
rabbitmqctl list_connections name peer_host state timeout | head
rabbitmqctl cluster_status

# Are compute services flapping to down because of RPC loss?
openstack compute service list --service nova-compute

# Network reachability/latency to the broker from a compute node
ping -c 5 <rabbit-host>
curl -s -o /dev/null -w "%{http_code}\n" http://<rabbit-host>:15672/api/healthchecks/node \
  -u guest:guest        # management API health (if enabled)
```

## Expected Results

```text
# RabbitMQ confirms the client is timing out:
=ERROR REPORT==== missed heartbeats from client, timeout: 60s

# A memory alarm means the broker is throttling everyone:
$ rabbitmqctl status | grep -i alarm
{alarms,[{resource_limit,memory,'rabbit@ctrl1'}]}

# Compute flapping as a consequence:
$ openstack compute service list --service nova-compute
| nova-compute | compute-3 | nova | enabled | down  | ...

# Healthy: no missed-heartbeat reports, no alarms, all computes State 'up'.
```

## Resolution

1. If RabbitMQ has a resource alarm, relieve it first — free memory/disk or raise
   `vm_memory_high_watermark`/`disk_free_limit`; the alarm blocks publishers
   cluster-wide.
2. Fix the network path — exclude AMQP (5672/5671) from aggressive idle timeouts
   on firewalls/LBs, or set the LB idle timeout above the heartbeat interval.
3. Run heartbeats in a real thread so they survive greenthread starvation:
   ```ini
   [oslo_messaging_rabbit]
   heartbeat_timeout_threshold = 60
   heartbeat_rate = 2
   heartbeat_in_pthread = true
   ```
   Restart the affected Nova services after changing config.
4. Heal a RabbitMQ partition/failover and ensure clients list all cluster nodes
   in `transport_url` for failover.
5. After RPC stabilizes, confirm flapped computes recover; restart `nova-compute`
   on any that stay `down`.

## Validation

```bash
openstack compute service list --service nova-compute    # all State 'up'
journalctl -u devstack@n-cpu --since "5 min ago" | grep -i heartbeat   # no new misses
openstack server create --flavor m1.small --image <img> --network <net> rpc-test
openstack server show rpc-test -c status -f value         # reaches ACTIVE
```

## Prevention

- Enable `heartbeat_in_pthread = true` on services prone to greenthread starvation.
- Keep AMQP connections off idle-timeout-killing middleboxes, or tune timeouts.
- Monitor RabbitMQ memory/disk alarms, connection churn, and queue depth.
- List all RabbitMQ nodes in `transport_url` and monitor cluster partitions.

## Related Errors

- [OpenStack Nova NoValidHost: No Valid Host Was Found](./openstack-nova-no-valid-host-was-found.md)

## References

- [oslo.messaging RabbitMQ driver](https://docs.openstack.org/oslo.messaging/latest/configuration/opts.html)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`openstack` · `nova` · `rabbitmq` · `oslo-messaging` · `heartbeat` · `production`
