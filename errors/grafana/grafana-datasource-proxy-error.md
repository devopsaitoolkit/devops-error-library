---
title: "Grafana Data Source Proxy Error"
slug: grafana-datasource-proxy-error
technologies: [grafana]
severity: high
tags: [grafana, datasource, proxy, timeout, production]
related: [grafana-datasource-bad-gateway, grafana-query-error]
last_reviewed: 2026-06-27
---

# Grafana Data Source Proxy Error

## Error Message

```text
Data source proxy error
```

```text
t=2026-06-24T14:18:42+0000 lvl=eror msg="Data source proxy request error" logger=data-proxy-log error="http: proxy error: context deadline exceeded (Client.Timeout exceeded while awaiting headers)"
```

```text
Get "https://prometheus.monitoring.svc:9090/api/v1/query_range": net/http: TLS handshake timeout
```

## Description

`Data source proxy error` is the generic message Grafana returns when the
server-side proxy *connected* to the upstream but the request failed mid-flight —
typically a timeout, a TLS handshake failure, or the backend closing the
connection. It differs from `Bad Gateway`: there the dial never succeeds; here
the connection is established (or partly) but the response does not arrive within
the configured timeout. The error originates in Grafana's `data-proxy-log`
logger.

## Technologies

- grafana (data source proxy / backend HTTP client)

## Severity

**high** — affected panels error out or time out, so dashboards and any alert
rules evaluating against that data source are unreliable until resolved.

## Common Causes

1. The backend query takes longer than Grafana's `dataproxy.timeout` (default
   30s) — heavy Prometheus/Loki query over a wide time range.
2. TLS handshake timeout or certificate problem against an HTTPS backend.
3. An intermediate reverse proxy / load balancer in front of the data source
   closes idle or long-running connections.
4. Backend is overloaded and slow to respond (high cardinality, GC pauses).
5. `keep_alive_seconds` / `dataproxy.timeout` misconfigured for the workload.

## Root Cause Analysis

Grafana opens a server-side connection to the data source and waits up to
`dataproxy.timeout` for response headers. If the upstream is slow, an LB drops
the connection, or the TLS handshake stalls, Grafana aborts and wraps the Go
transport error as `Data source proxy request error`. The underlying Go error
(`context deadline exceeded`, `TLS handshake timeout`, `connection reset by
peer`) tells you whether the problem is duration (timeout), transport (TLS), or
the backend resetting the stream.

## Diagnostic Commands

```bash
# Server logs with the precise transport error
journalctl -u grafana-server --since "15 min ago" | grep -i "proxy request error"

# Current proxy timeout settings (read-only)
grep -A3 "\[dataproxy\]" /etc/grafana/grafana.ini

# Effective settings via API (admin)
curl -s -H "Authorization: Bearer $GRAFANA_TOKEN" \
  http://localhost:3000/api/admin/settings | jq '.dataproxy'

# Time the upstream query directly from the Grafana host
curl -s -o /dev/null -w "time_total=%{time_total} http=%{http_code}\n" \
  'http://prometheus.monitoring.svc:9090/api/v1/query?query=up'
```

## Expected Results

```text
error="http: proxy error: context deadline exceeded (Client.Timeout exceeded while awaiting headers)"
```

`context deadline exceeded` confirms a timeout; compare the upstream `time_total`
against `dataproxy.timeout`. `TLS handshake timeout` points to TLS/network on the
secure hop. A healthy direct query returns in well under the timeout with
`http=200`.

## Resolution

1. If the query is genuinely slow, raise the proxy timeout and reload:

   ```ini
   [dataproxy]
   timeout = 60
   keep_alive_seconds = 90
   ```
2. Optimize the underlying query (narrower range, lower resolution, recording
   rules) rather than only raising timeouts.
3. Align the upstream LB/ingress timeout with Grafana's (the LB must allow the
   longest expected query).
4. For TLS handshake timeouts, fix the certificate/CA chain or correct the
   `https`/port settings on the data source.

## Validation

```bash
# After restart, re-run the panel/query; server log should be clean
sudo systemctl restart grafana-server
journalctl -u grafana-server --since "2 min ago" | grep -i "proxy request error" || echo "no proxy errors"
```

## Prevention

- Size `dataproxy.timeout` to the slowest legitimate query and match it across
  every proxy layer in the path.
- Use Prometheus recording rules / Loki query optimization to keep dashboard
  queries fast.
- Alert on rising data source query latency before it crosses the timeout.

## Related Errors

- [Grafana Data Source Bad Gateway](./grafana-datasource-bad-gateway.md)
- [Grafana Query Error](./grafana-query-error.md)

## References

- [Grafana configuration: dataproxy](https://grafana.com/docs/grafana/latest/setup-grafana/configure-grafana/#dataproxy)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`grafana` · `datasource` · `proxy` · `timeout` · `production`
