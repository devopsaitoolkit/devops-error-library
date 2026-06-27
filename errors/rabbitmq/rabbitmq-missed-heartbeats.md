---
title: "RabbitMQ Missed Heartbeats"
slug: rabbitmq-missed-heartbeats
technologies: [rabbitmq]
severity: medium
tags: [rabbitmq, connectivity, heartbeat, networking, production]
related: [rabbitmq-connection-refused, rabbitmq-memory-resource-alarm]
last_reviewed: 2026-06-27
---

# RabbitMQ Missed Heartbeats

## Error Message

```text
=ERROR REPORT==== 27-Jun-2026::09:41:55 ===
closing AMQP connection <0.27645.3> (10.0.4.18:54122 -> 10.0.1.7:5672):
missed heartbeats from client, timeout: 60s
```

```text
com.rabbitmq.client.MissedHeartbeatException: Heartbeat missing with heartbeat = 60 seconds
```

## Description

AMQP 0-9-1 uses a heartbeat to detect dead TCP connections that the OS has not
yet torn down. Client and broker negotiate an interval (default 60s); each side
must send a frame (or an empty heartbeat frame) within that window. If two
consecutive intervals pass with nothing received, the peer declares the
connection dead and closes it. The broker logs `missed heartbeats from client`;
the client library raises a `MissedHeartbeatException`. The connection drops,
in-flight publishes/consumes fail, and the client must reconnect.

## Technologies

- rabbitmq (AMQP connection layer, heartbeat frames)

## Severity

**medium** — individual connections are dropped and must reconnect, causing
transient publish/consume failures and consumer rebalancing. It is rarely a full
outage but, if widespread, signals a network or client-blocking problem that
degrades reliability.

## Common Causes

1. A blocked client event loop — the application thread is stuck (long
   synchronous work, GC pause, debugger breakpoint) and never sends heartbeats.
2. A stateful firewall, NAT, or load balancer with an idle-connection timeout
   shorter than the heartbeat interval silently drops the TCP flow.
3. Network congestion or packet loss between client and broker.
4. The heartbeat negotiated to `0` (disabled) on one side, so dead connections
   linger and surface as other errors instead.

## Root Cause Analysis

Heartbeats are sent on a timer independent of application traffic. If the
client's I/O thread is starved (CPU-bound work, a `Thread.sleep`, a stop-the-world
GC), it cannot emit the heartbeat frame even though the socket is fine, and the
broker times it out. Separately, idle middleboxes drop connections that send no
data; with no traffic and no heartbeat reaching the broker, the broker counts
missed beats and closes. The broker waits **two** intervals before closing, so a
60s heartbeat tolerates up to ~120s of silence.

## Diagnostic Commands

```bash
# Per-connection state, client properties, and timeout in effect
sudo rabbitmqctl list_connections name peer_host state timeout \
  client_properties

# Count and inspect recent heartbeat closures in the log
sudo journalctl -u rabbitmq-server --since "1 hour ago" --no-pager \
  | grep -i "missed heartbeats"

# Confirm sustained connectivity / latency to the broker port
ss -tnp dst :5672
```

## Expected Results

```text
# A healthy connection shows running state and the negotiated timeout:
amqp-consumer-1   10.0.4.18   running   60

# The log repeatedly shows the same client IPs being closed:
closing AMQP connection ... missed heartbeats from client, timeout: 60s
```

Repeated closures from the *same* client point at a blocked client; closures
across many clients at a fixed interval point at a middlebox idle timeout.

## Resolution

1. Keep the client's I/O thread free: never run long blocking work on the
   connection thread; move heavy processing to a worker pool.
2. Set the heartbeat interval **shorter** than any idle timeout on the network
   path (e.g. 30s if a load balancer idles at 60s). Negotiate it client-side:

   ```text
   amqp://user:pass@host:5672/%2f?heartbeat=30
   ```
3. Enable TCP keepalives as a backstop for middlebox idle drops.
4. Do not disable heartbeats (`heartbeat=0`) in production.

## Validation

```bash
sudo rabbitmqctl list_connections name state timeout
# Expect: state "running", connections stable; no new "missed heartbeats"
# entries in the broker log after the change.
```

## Prevention

- Standardize a 20-30s heartbeat across services and document the network idle
  timeouts so they never undercut it.
- Monitor connection churn and alert on spikes in connection close rate.
- Profile consumers for long blocking sections on the I/O thread.

## Related Errors

- [RabbitMQ Connection Refused](./rabbitmq-connection-refused.md)
- [RabbitMQ Memory Resource Alarm](./rabbitmq-memory-resource-alarm.md)

## References

- [RabbitMQ Heartbeats](https://www.rabbitmq.com/docs/heartbeats)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`rabbitmq` · `connectivity` · `heartbeat` · `networking` · `production`
