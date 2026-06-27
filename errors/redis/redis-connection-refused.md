---
title: "Redis Connection Refused"
slug: redis-connection-refused
technologies: [redis]
severity: critical
tags: [redis, connectivity, networking, startup, production]
related: [redis-max-number-of-clients-reached, redis-loading-dataset-in-memory]
last_reviewed: 2026-06-27
---

# Redis Connection Refused

## Error Message

```text
Could not connect to Redis at 127.0.0.1:6379: Connection refused
```

```text
redis.exceptions.ConnectionError: Error 111 connecting to redis:6379.
Connection refused.
```

## Description

`Connection refused` (errno 111, `ECONNREFUSED`) means the client reached the
target host and port but nothing was listening there, so the kernel actively
rejected the TCP handshake. This is distinct from a timeout (no route / dropped
packets). For Redis it almost always means the server isn't running, is bound to
a different interface or port, or a firewall is RST-ing the connection.

## Technologies

- redis (server process / network binding)

## Severity

**critical** — clients cannot reach Redis at all. Any service that depends on it
for cache, sessions, queues, or locks is degraded or fully down.

## Common Causes

1. The `redis-server` process is not running (crashed, OOM-killed, or never
   started).
2. Redis is bound to `127.0.0.1` only, but the client connects over the network
   to the host's external IP.
3. The client is using the wrong port (a non-default `port`, or `port 0` which
   disables the TCP listener in favor of a Unix socket).
4. A firewall, security group, or `iptables` rule rejects (RST) traffic to
   `6379`.
5. The container/pod exposing Redis is not yet ready or maps a different port.

## Root Cause Analysis

A TCP `RST` in response to `SYN` is what produces `ECONNREFUSED`. It happens only
when the packet reaches a host that has no socket in `LISTEN` on that port (or a
firewall configured to reject rather than drop). So the question is binary: is
there a Redis listening socket on the address/port the client targets, and can
the client's packets reach it? Confirming the process is up and inspecting its
`bind`/`port` and the listening sockets resolves nearly every case.

## Diagnostic Commands

```bash
# Is the server alive and answering on the loopback?
redis-cli -h 127.0.0.1 -p 6379 PING

# What address/port is Redis configured to listen on?
redis-cli CONFIG GET bind
redis-cli CONFIG GET port

# Is anything actually LISTENing on 6379? (shows the bound interface)
ss -ltnp | grep 6379

# Service state and recent startup/crash logs
systemctl status redis-server --no-pager
journalctl -u redis-server --since "10 min ago" --no-pager

# From a remote client, confirm reachability of the port
nc -vz <redis-host> 6379
```

## Expected Results

```text
$ redis-cli PING
Could not connect to Redis at 127.0.0.1:6379: Connection refused

$ ss -ltnp | grep 6379
(no output)        # nothing is listening -> server down or wrong port
```

When Redis is healthy and reachable you instead see:

```text
$ redis-cli PING
PONG
$ ss -ltnp | grep 6379
LISTEN 0 511 0.0.0.0:6379 0.0.0.0:* users:(("redis-server",pid=812,fd=6))
```

A `LISTEN` line showing only `127.0.0.1:6379` while a remote client fails points
to a `bind`/firewall issue rather than a dead process.

## Resolution

1. If `ss` shows nothing listening, start the server and check why it stopped:

   ```bash
   sudo systemctl start redis-server
   journalctl -u redis-server --since "10 min ago"
   ```
2. If it listens only on `127.0.0.1` but clients are remote, bind the right
   interface in `redis.conf` and **require authentication** before exposing it:

   ```conf
   bind 0.0.0.0 -::1
   requirepass <strong-password>
   protected-mode no
   ```
   Restart Redis after editing.
3. If a firewall is rejecting, allow the port only from trusted sources:

   ```bash
   sudo ufw allow from <app-subnet> to any port 6379 proto tcp
   ```
4. Correct the client's host/port if it targets the wrong endpoint.

## Validation

```bash
redis-cli -h <redis-host> -p 6379 PING
# Expect: PONG
```

## Prevention

- Run Redis under a process supervisor (systemd) with `Restart=on-failure`.
- Health-check the listening port from the application network in CI/CD.
- Never expose `6379` to the internet without `requirepass` and network ACLs.
- Monitor `redis_up`/`PING` from the consumer's vantage point, not just locally.

## Related Errors

- [Redis max number of clients reached](./redis-max-number-of-clients-reached.md)
- [Redis LOADING Dataset in Memory](./redis-loading-dataset-in-memory.md)

## References

- [Redis: Security and network configuration](https://redis.io/docs/management/security/)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`redis` · `connectivity` · `networking` · `startup` · `production`
