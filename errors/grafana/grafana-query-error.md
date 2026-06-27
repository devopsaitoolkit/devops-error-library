---
title: "Grafana Query Error"
slug: grafana-query-error
technologies: [grafana]
severity: medium
tags: [grafana, query, datasource, promql, production]
related: [grafana-panel-no-data, grafana-datasource-proxy-error]
last_reviewed: 2026-06-27
---

# Grafana Query Error

## Error Message

```text
Query error
```

```text
1:8: parse error: unexpected identifier "by" in aggregation expression
```

```text
{"error":"expanding series: query timed out in expression evaluation","errorType":"timeout","status":"error"}
```

## Description

A **query error** is shown on a panel when the data source executes the query and
returns an explicit error (HTTP 400/422/500 with an error body), as opposed to an
empty result ("No data") or an unreachable backend ("Bad Gateway"). The message
comes from the data source — Prometheus PromQL parse errors, Loki LogQL errors,
InfluxQL/Flux errors, SQL syntax errors — and Grafana surfaces it on the panel
and in the query inspector. The fix is in the query or the source, not in
Grafana's networking.

## Technologies

- grafana (query path) + the backing data source (Prometheus, Loki, SQL, …)

## Severity

**medium** — the affected panel(s) and any alert rules built on that query fail
to evaluate; the rest of Grafana and the data source remain healthy.

## Common Causes

1. Invalid query syntax (PromQL/LogQL/SQL parse error), often after a manual edit
   or a template variable that expanded into malformed text.
2. Referencing a metric, field, label, table, or column that does not exist.
3. Query is too expensive and the source aborts it (`query timed out`,
   `too many samples`, exceeded `max_samples`).
4. Type mismatch — e.g. applying a range function to an instant vector, or
   comparing incompatible types in SQL.
5. Missing permissions on the data source (e.g. SQL user lacks SELECT).

## Root Cause Analysis

Grafana posts the query to the data source via `/api/ds/query`. The source parses
and executes it; on failure it returns a structured error
(`status:"error", errorType:"bad_data"|"timeout"`) which Grafana renders verbatim
on the panel. Because the error text is the source's own, the most reliable fix
is to take the fully-resolved query from the inspector and run it directly
against the source to reproduce and iterate.

## Diagnostic Commands

```bash
# Pull the panel's raw expression (admin, read-only)
curl -s -H "Authorization: Bearer $GRAFANA_TOKEN" \
  "http://localhost:3000/api/dashboards/uid/<dash-uid>" \
  | jq -r '.dashboard.panels[].targets[].expr'

# Reproduce the PromQL directly to see the source's parse/eval error
curl -s 'http://prometheus.monitoring.svc:9090/api/v1/query' \
  --data-urlencode 'query=sum by (instance) rate(http_requests_total[5m])' | jq '{status, error, errorType}'

# Grafana-side log for query handler errors
journalctl -u grafana-server --since "10 min ago" | grep -i "query error\|tsdb\|eval"
```

## Expected Results

```text
{
  "status": "error",
  "errorType": "bad_data",
  "error": "1:18: parse error: unexpected identifier \"rate\""
}
```

`errorType: bad_data` is a syntax/semantic problem (fix the query). `errorType:
timeout` means the query is too heavy (optimize it / raise limits). A valid query
returns `"status":"success"`.

## Resolution

1. Open the panel **Query inspector → Query** to get the fully expanded
   expression (after variables), then fix the syntax the source reported. For the
   example above:

   ```promql
   sum by (instance) (rate(http_requests_total[5m]))   # parentheses around rate()
   ```
2. Correct any non-existent metric/label/column names.
3. For timeouts / `too many samples`, narrow the range, increase the step,
   pre-aggregate with recording rules, or raise the source's query limits.
4. For permission errors on SQL sources, grant the data source user read access
   to the referenced tables.

## Validation

```bash
# Corrected query returns success from the source
curl -s 'http://prometheus.monitoring.svc:9090/api/v1/query' \
  --data-urlencode 'query=sum by (instance) (rate(http_requests_total[5m]))' \
  | jq '.status'   # Expect: "success"
```

## Prevention

- Lint/validate queries (e.g. `promtool query` or CI checks) before committing
  dashboards.
- Prefer recording rules for expensive expressions used on dashboards.
- Constrain template variables so they cannot expand into invalid query fragments.

## Related Errors

- [Grafana Panel No Data](./grafana-panel-no-data.md)
- [Grafana Data Source Proxy Error](./grafana-datasource-proxy-error.md)

## References

- [Grafana query and transform data](https://grafana.com/docs/grafana/latest/panels-visualizations/query-transform-data/)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`grafana` · `query` · `promql` · `datasource` · `production`
