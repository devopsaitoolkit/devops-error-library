---
title: "Grafana Data Source Bad Gateway"
slug: grafana-datasource-bad-gateway
technologies: [grafana]
severity: high
tags: [grafana, datasource, proxy, networking, production]
related: [grafana-datasource-proxy-error, grafana-query-error]
last_reviewed: 2026-06-27
---

# Grafana Data Source Bad Gateway

## Error Message

```text
Bad Gateway
```

```text
{"message":"Bad Gateway","traceID":""}
```

```text
t=2026-06-24T14:02:11+0000 lvl=eror msg="Data source proxy request error" logger=data-proxy-log error="dial tcp 10.0.3.21:9090: connect: connection refused"
```

## Description

Grafana shows **Bad Gateway** when its built-in data source proxy cannot reach
the upstream backend (Prometheus, Loki, InfluxDB, etc.) at the configured URL.
Browser requests to `/api/datasources/proxy/...` or `/api/ds/query` are relayed
by the Grafana server to the data source URL; when that outbound connection
fails, the proxy returns HTTP 502 and the panel/test fails. The error is emitted
by the Grafana server (`data-proxy-log` logger), not by the data source itself —
the data source is simply unreachable from Grafana's host.

## Technologies

- grafana (data source proxy / backend HTTP client)

## Severity

**high** — every panel using the affected data source returns no data, so
dashboards relying on it are effectively down even though Grafana itself is up.

## Common Causes

1. The upstream data source is down, restarting, or listening on a different
   port than the configured URL.
2. Wrong URL in the data source config: `localhost` instead of a service DNS
   name, missing/incorrect port, or `http` vs `https` mismatch.
3. Network policy / firewall / security group blocks Grafana's host from
   reaching the data source.
4. In Kubernetes, the backend Service name or namespace is wrong, or the pod is
   not Ready.
5. TLS handshake failure to an HTTPS backend (treated as a gateway error).

## Root Cause Analysis

The Grafana server performs a server-side HTTP request to the data source URL on
behalf of the browser (proxy mode). If `net.Dial` to that URL fails — connection
refused, no route to host, DNS failure, or TLS error — Grafana cannot complete
the upstream request and surfaces a generic `Bad Gateway` (502) to the client
while logging the concrete dial error server-side. Because the failure is on the
Grafana → backend hop, the browser dev-tools only show 502 with no detail; the
real cause is always in the Grafana server log.

## Diagnostic Commands

```bash
# Grafana server health (confirms Grafana itself is up)
curl -s http://localhost:3000/api/health

# Inspect the configured data source URL/type (admin token required)
curl -s -H "Authorization: Bearer $GRAFANA_TOKEN" \
  http://localhost:3000/api/datasources | jq '.[] | {name, type, url, access}'

# Grafana server logs showing the real dial/proxy error
journalctl -u grafana-server --since "10 min ago" | grep -i "data-proxy\|proxy request error"

# Reproduce the upstream hop FROM the Grafana host (read-only)
curl -sv http://10.0.3.21:9090/-/healthy
```

## Expected Results

```text
error="dial tcp 10.0.3.21:9090: connect: connection refused"
```

The dial error names the exact host:port Grafana tried. `connection refused`
means nothing is listening; `no route to host` / `i/o timeout` means a network
or firewall block; `no such host` means DNS/Service-name is wrong. A healthy
upstream returns `Prometheus Server is Healthy.` from `/-/healthy`.

## Resolution

1. From the Grafana host, `curl` the exact data source URL. Fix whichever hop
   fails:
   - Backend down → restart/repair the data source.
   - `access: proxy` requires the URL be reachable from the **server**; use the
     in-cluster Service DNS (e.g. `http://prometheus.monitoring.svc:9090`), not
     `localhost`.
2. Correct the URL/port/scheme in **Connections → Data sources**, or in the
   provisioning YAML, then **Save & test**.
3. Open the required egress in firewall/security-group/NetworkPolicy from
   Grafana to the backend.
4. For HTTPS backends, fix the CA/cert config (or, only in trusted networks,
   enable `tlsSkipVerify` temporarily to confirm TLS is the cause).

## Validation

```bash
# Save & test triggers this server-side health check; expect HTTP 200
curl -s -H "Authorization: Bearer $GRAFANA_TOKEN" \
  http://localhost:3000/api/datasources/uid/<uid>/health | jq .
# Expect: {"message":"...","status":"OK"}
```

## Prevention

- Provision data sources with in-cluster/service DNS URLs, never `localhost`.
- Add a synthetic check that hits `/api/datasources/uid/<uid>/health` and alerts
  on non-OK.
- Codify Grafana→backend egress in NetworkPolicy/firewall-as-code so it is not
  dropped by changes.

## Related Errors

- [Grafana Data Source Proxy Error](./grafana-datasource-proxy-error.md)
- [Grafana Query Error](./grafana-query-error.md)

## References

- [Grafana data sources](https://grafana.com/docs/grafana/latest/datasources/)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`grafana` · `datasource` · `proxy` · `networking` · `production`
