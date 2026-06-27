---
title: "RabbitMQ Connection Refused"
slug: rabbitmq-connection-refused
technologies: [rabbitmq]
severity: high
tags: [rabbitmq, connectivity, networking, connection-refused, production]
related: [rabbitmq-missed-heartbeats, rabbitmq-access-refused-login]
last_reviewed: 2026-06-27
---

# RabbitMQ Connection Refused

## Error Message

```text
com.rabbitmq.client.ShutdownSignalException: connection error; protocol method:
  #method<connection.close>(reply-code=...)
Caused by: java.net.ConnectException: Connection refused (Connection refused)
    at java.base/sun.nio.ch.Net.pollConnect(Native Method)
```

```text
socket error: econnrefused
amqp.exceptions.AMQPConnectionError: [Errno 111] Connection refused: localhost:5672
```

## Description

`Connection refused` is a TCP-level failure: the client's SYN packet reached the
host but nothing was listening on the target port (5672 for AMQP, 5671 for
AMQPS), so the kernel returned an RST. RabbitMQ itself never saw the connection —
this is *not* an authentication or protocol error. It is emitted by the client
library, not the broker, because the broker process is down, bound to a
different interface/port, or blocked by a firewall.

## Technologies

- rabbitmq (broker process, listener, TCP transport)

## Severity

**high** — clients cannot reach the broker at all. If this is the only node or
the load balancer points only here, every publisher and consumer is offline: a
full messaging outage.

## Common Causes

1. The `rabbitmq-server` process is stopped, crashed, or never started.
2. The broker is bound to `127.0.0.1` only, but clients connect over a remote
   interface (or vice-versa) — the listener address does not match.
3. A firewall, security group, or NetworkPolicy blocks TCP 5672/5671.
4. The client points at the wrong host or port (typo, stale DNS, wrong env var).
5. The node is still booting and has not opened its listeners yet.

## Root Cause Analysis

When RabbitMQ starts, the `rabbit` application opens TCP listeners defined by
`listeners.tcp.*` (default `0.0.0.0:5672`). If the OS process is not running, or
the listener bound to a narrower address than the client uses, the kernel has no
socket in `LISTEN` state for that address/port and immediately refuses the
connection. A firewall drop, by contrast, usually manifests as a *timeout* (no
RST) — so a fast "refused" points at the local listener/process, while a hang
points at the network path.

## Diagnostic Commands

```bash
# Is the broker process up and the node running?
sudo systemctl status rabbitmq-server
sudo rabbitmqctl status

# Which addresses/ports is RabbitMQ actually listening on?
sudo rabbitmq-diagnostics listeners

# Confirm a socket is in LISTEN state for 5672/5671
sudo ss -ltnp '( sport = :5672 or sport = :5671 )'

# Recent broker log lines around startup/crash
sudo journalctl -u rabbitmq-server --since "30 min ago" --no-pager
```

## Expected Results

```text
# Healthy: a listener is bound and accepting
Interface: [::], port: 5672, protocol: amqp, purpose: AMQP 0-9-1 and 1.0
LISTEN 0  128  *:5672  *:*  users:(("beam.smp",pid=8123,...))

# Problem: ss returns nothing for :5672, or rabbitmq-diagnostics listeners
# shows the listener bound only to 127.0.0.1 while clients are remote.
```

## Resolution

1. If the process is down, start it and check the logs for why it stopped:

   ```bash
   sudo systemctl start rabbitmq-server
   sudo journalctl -u rabbitmq-server -n 100 --no-pager
   ```
2. If it is bound to the wrong interface, set the listener explicitly in
   `rabbitmq.conf` and restart:

   ```ini
   listeners.tcp.default = 0.0.0.0:5672
   ```
3. Open the port in the host firewall / cloud security group / Kubernetes
   NetworkPolicy for the client CIDRs.
4. Verify the client's host, port, and TLS setting (5671 needs TLS) match the
   broker's actual listeners.

## Validation

```bash
# From the client host, confirm the port now accepts connections
nc -vz <broker-host> 5672
# Expect: "Connection to <broker-host> 5672 port [tcp/amqp] succeeded!"
```

## Prevention

- Run a readiness check (`rabbitmq-diagnostics check_port_connectivity`) before
  routing traffic to a node.
- Pin listener addresses in config rather than relying on defaults across
  environments.
- Alert on the broker process being down and on listener-port reachability.

## Related Errors

- [RabbitMQ Missed Heartbeats](./rabbitmq-missed-heartbeats.md)
- [RabbitMQ ACCESS_REFUSED Login](./rabbitmq-access-refused-login.md)

## References

- [RabbitMQ Networking and Connectivity](https://www.rabbitmq.com/docs/networking)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`rabbitmq` · `connectivity` · `networking` · `connection-refused` · `production`
