---
title: "Redis max number of clients reached"
slug: redis-max-number-of-clients-reached
technologies: [redis]
severity: high
tags: [redis, connections, maxclients, limits, production]
related: [redis-connection-refused, redis-oom-command-not-allowed-maxmemory]
last_reviewed: 2026-06-27
---

# Redis max number of clients reached

## Error Message

```text
(error) ERR max number of clients reached
```

```text
1:M 27 Jun 2026 11:42:08.331 # Error registering fd event for the new client:
Too many open files (errno=24)
```

## Description

Redis rejects new connections with `ERR max number of clients reached` once the
number of connected clients hits the effective `maxclients` limit. The limit is
the configured `maxclients` (default 10000), capped by the process's file
descriptor limit (`ulimit -n`) minus a reserve Redis keeps for internal use. When
the cap is reached, existing connections keep working but every new connection is
refused — which clients usually surface as connection errors.

## Technologies

- redis (connection handling / file descriptors)

## Severity

**high** — new clients (including new app pods scaling up) cannot connect. Under
a connection leak this escalates to a full outage as healthy connections churn.

## Common Causes

1. A client-side connection leak — connections opened but never closed/returned
   to the pool.
2. Connection pools sized too large across many application instances, summing to
   more than `maxclients`.
3. The OS file-descriptor limit (`ulimit -n`) is low, so the *effective*
   `maxclients` is far below the configured value.
4. Many idle connections held open without `timeout` configured.
5. A traffic spike or a thundering herd of reconnects after a blip.

## Root Cause Analysis

Each client connection consumes one file descriptor. At startup Redis reconciles
the requested `maxclients` against the process's `RLIMIT_NOFILE`; if the fd limit
is too low, Redis lowers `maxclients` accordingly and logs a warning. When live
connection count reaches that effective ceiling, the event loop can't register an
fd for a new socket and the connection is rejected. The two levers are therefore
*how many connections clients hold* and *how high the fd ceiling is*.

## Diagnostic Commands

```bash
# Current connected clients, blocked clients, and the effective maxclients
redis-cli INFO clients

# Configured limit and idle timeout
redis-cli CONFIG GET maxclients
redis-cli CONFIG GET timeout

# Per-connection detail: addr, age, idle time, last command — find the leaker
redis-cli CLIENT LIST | awk '{print $2, $17, $18}' | sort | uniq -c | sort -rn | head

# Rejected connections counter (rises when the cap is hit)
redis-cli INFO stats | grep -E 'rejected_connections|total_connections_received'

# OS file-descriptor limit for the running redis process
cat /proc/$(pgrep -o redis-server)/limits | grep 'Max open files'
```

## Expected Results

```text
# Clients
connected_clients:10000
blocked_clients:0
maxclients:10000

rejected_connections:5821
```

`connected_clients` at (or just under) `maxclients` with a rising
`rejected_connections` confirms the cap is hit. In `CLIENT LIST`, many
connections from one `addr` with a high `idle` value points to a leak or oversized
pool. A `Max open files` value near the connection count means the fd limit is the
real ceiling.

## Resolution

1. Find and fix the client connection leak first — ensure pools close idle
   connections and that code returns connections after use.
2. Raise the OS file-descriptor limit for the Redis service so `maxclients` can
   actually be honored:

   ```ini
   # /etc/systemd/system/redis-server.service.d/limits.conf
   [Service]
   LimitNOFILE=65535
   ```
   Then `sudo systemctl daemon-reload && sudo systemctl restart redis-server`.
3. Set an idle `timeout` so abandoned connections are reaped (run as a tuning
   step, not a diagnostic):

   ```bash
   redis-cli CONFIG SET timeout 300
   ```
4. Right-size client connection pools so the total across all app instances stays
   well below `maxclients`.

## Validation

```bash
redis-cli INFO clients | grep -E 'connected_clients|maxclients'
redis-cli PING
# Expect: PONG, and connected_clients comfortably below maxclients.
```

## Prevention

- Alert on `connected_clients` approaching `maxclients` and on
  `rejected_connections`.
- Use bounded connection pools and ensure connections are released after use.
- Set `LimitNOFILE` high enough that the configured `maxclients` is the real cap.
- Configure a reasonable `timeout` to reap idle connections.

## Related Errors

- [Redis Connection Refused](./redis-connection-refused.md)
- [Redis OOM Command Not Allowed](./redis-oom-command-not-allowed-maxmemory.md)

## References

- [Redis clients documentation](https://redis.io/docs/reference/clients/)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`redis` · `connections` · `maxclients` · `limits` · `production`
