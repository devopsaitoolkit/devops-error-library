---
title: "Prometheus Target Down: Connection Refused"
slug: prometheus-target-down-connection-refused
technologies: [prometheus]
severity: high
tags: [prometheus, scraping, targets, connectivity, production]
related: [prometheus-context-deadline-exceeded, prometheus-scrape-401-unauthorized]
last_reviewed: 2026-06-27
---

# Prometheus Target Down: Connection Refused

## Error Message

```text
Get "http://10.0.4.21:9100/metrics": dial tcp 10.0.4.21:9100: connect: connection refused
```

On the `/targets` page the endpoint shows:

```text
State   Endpoint                          Error
DOWN    http://10.0.4.21:9100/metrics     connection refused
```

## Description

Prometheus scrapes each target by issuing an HTTP `GET` to its `/metrics`
endpoint on the configured interval. `connection refused` means the TCP
handshake reached the host but nothing was listening on that port — the kernel
on the target host actively rejected the connection with an RST. This is
distinct from a timeout (nothing answered) or DNS failure (host not resolved).
The scrape manager marks the target `DOWN`, sets `up{job=...} == 0` for that
series, and any alerting rule built on `up` will start firing.

## Technologies

- prometheus (scrape manager, service discovery)

## Severity

**high** — the target produces no metrics, so dashboards and alerts that depend
on it go blind. If many targets in a job share the cause (a crashed exporter
rollout, a wrong port), an entire tier loses observability.

## Common Causes

1. The exporter/process on the target is not running or has crashed.
2. The scrape config points at the wrong port (e.g. `9090` instead of `9100`).
3. The exporter binds to `127.0.0.1` only, so it refuses connections from
   Prometheus on another host.
4. The target restarted and the exporter has not come back up yet.

## Root Cause Analysis

A refused connection is a Layer-4 signal: the route to the host works and the
host is up, but no socket is in the `LISTEN` state on the requested port, so the
host's TCP stack replies with an RST. Prometheus surfaces the raw `net/http`
dial error verbatim. The key discriminator versus other "down" states is the
phrase `connect: connection refused` — it proves the host is reachable, which
rules out routing, DNS, and firewall *drops* (those time out instead).

## Diagnostic Commands

```bash
# Ask Prometheus exactly which targets are down and why (read-only HTTP API)
curl -s http://localhost:9090/api/v1/targets \
  | jq '.data.activeTargets[] | select(.health=="down") | {url: .scrapeUrl, lastError}'

# Confirm whether anything is listening on the expected port, from a host that can reach the target
curl -sv http://10.0.4.21:9100/metrics 2>&1 | head -20

# On the target host: is the exporter actually listening, and on which address?
ss -ltnp | grep 9100
```

## Expected Results

```text
{
  "url": "http://10.0.4.21:9100/metrics",
  "lastError": "... connect: connection refused"
}
```

A healthy target reports `"health": "up"` with an empty `lastError`. If `ss`
shows `127.0.0.1:9100` instead of `0.0.0.0:9100` or the host IP, the exporter is
bound to loopback only and that is the bug.

## Resolution

1. Restart or fix the exporter so it listens again, and confirm the port:
   `systemctl status node_exporter` then `ss -ltnp | grep 9100`.
2. If the exporter is bound to loopback, change its listen address to the host
   IP or `0.0.0.0` (for `node_exporter`: `--web.listen-address=0.0.0.0:9100`).
3. If the scrape config has the wrong port, fix it and reload:

   ```yaml
   - job_name: node
     static_configs:
       - targets: ["10.0.4.21:9100"]   # match the exporter's real port
   ```
4. Reload Prometheus config (`curl -X POST http://localhost:9090/-/reload` or
   `SIGHUP`) so the corrected target is picked up.

## Validation

```bash
# Series should flip back to 1 once the scrape succeeds
curl -s 'http://localhost:9090/api/v1/query?query=up{instance="10.0.4.21:9100"}' \
  | jq '.data.result[].value[1]'
# Expect: "1"
```

## Prevention

- Run a synthetic blackbox probe of each exporter port so you detect a refused
  port before it removes a real target.
- Pin exporter listen addresses in config management; never default to loopback
  on multi-host setups.
- Alert on `up == 0 for: 5m` per job so a single flap does not page but a real
  outage does.

## Related Errors

- [Prometheus Context Deadline Exceeded](./prometheus-context-deadline-exceeded.md)
- [Prometheus Scrape 401 Unauthorized](./prometheus-scrape-401-unauthorized.md)

## References

- [Prometheus: Configuration](https://prometheus.io/docs/prometheus/latest/configuration/configuration/)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`prometheus` · `scraping` · `targets` · `connectivity` · `production`
