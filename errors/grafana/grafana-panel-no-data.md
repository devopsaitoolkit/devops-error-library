---
title: "Grafana Panel No Data"
slug: grafana-panel-no-data
technologies: [grafana]
severity: low
tags: [grafana, panel, query, dashboard, production]
related: [grafana-query-error, grafana-datasource-bad-gateway]
last_reviewed: 2026-06-27
---

# Grafana Panel No Data

## Error Message

```text
No data
```

```text
No data points (or "N/A")
```

## Description

**No data** is shown in a panel when the query executed successfully (HTTP 200,
no error) but returned an empty result set for the selected time range and
variables. Unlike a *query error* or *Bad Gateway*, the data source is reachable
and the query is valid — there simply are no matching series/points. It is one of
the most common "is it broken?" tickets, and the answer is usually the query,
the time range, or the labels rather than an outage.

## Technologies

- grafana (panel / query result handling)

## Severity

**low** — the panel is non-functional but Grafana, the data source, and the
query path are all healthy; it is usually a configuration or expectation issue,
not an outage. It becomes higher severity only if it masks genuinely missing
metrics.

## Common Causes

1. The selected **time range** is outside the window where data exists (e.g.
   "Last 5 minutes" but the series stopped reporting an hour ago).
2. A label/metric name typo, or a metric that the exporter no longer emits.
3. A dashboard **template variable** resolved to a value with no matching series
   (wrong `$instance`, empty `$namespace`).
4. The metric exists but was relabeled/renamed in the source, so the query no
   longer matches.
5. The data source genuinely has no samples (scrape target down at the source —
   verify before assuming the panel is at fault).

## Root Cause Analysis

Grafana sends the panel's query to the data source via `/api/ds/query`. A 200
response with an empty frame (no rows/series) renders as "No data". Because there
is no error, the cause is logical: the query plus the time range plus the
substituted template variables produced zero matches. Reproducing the exact
query with the panel's time range against the data source distinguishes "query
matches nothing" from "source has no data".

## Diagnostic Commands

```bash
# Inspect the panel's exact query + datasource via the dashboard JSON (admin)
curl -s -H "Authorization: Bearer $GRAFANA_TOKEN" \
  "http://localhost:3000/api/dashboards/uid/<dash-uid>" \
  | jq '.dashboard.panels[] | {title, targets: [.targets[].expr]}'

# Reproduce the query directly against Prometheus over the same range (read-only)
curl -s 'http://prometheus.monitoring.svc:9090/api/v1/query?query=up{job="api"}' | jq '.data.result | length'

# Confirm the metric/label values actually exist at the source
curl -s 'http://prometheus.monitoring.svc:9090/api/v1/label/__name__/values' \
  | jq '.data | map(select(test("http_requests")))'

# Query inspector data appears in browser; server logs rarely show empty results
journalctl -u grafana-server --since "5 min ago" | grep -i "query" | tail
```

## Expected Results

```text
.data.result | length  ->  0     # query matches nothing for that range
```

A length of `0` confirms the empty result is real for that query/time. If the
direct query returns series but the panel does not, the difference is the time
range or an unresolved template variable. The label-values check tells you
whether the metric name even exists.

## Resolution

1. Widen the dashboard time range to where data is expected (e.g. "Last 24h").
2. Use the **Query inspector** (panel → Inspect → Query) to see the fully
   resolved query after variable substitution, and fix any wrong `$variable`.
3. Correct metric/label names in the query to match what the source emits (check
   the label-values endpoint above).
4. If the metric is genuinely absent, fix it upstream (restart the exporter,
   repair the scrape target) — the panel is reporting the truth.

## Validation

```bash
# Same query now returns at least one series for the panel range
curl -s 'http://prometheus.monitoring.svc:9090/api/v1/query?query=up{job="api"}' \
  | jq '.data.result | length'   # Expect: >= 1
```

## Prevention

- Set sensible default time ranges and refresh on dashboards.
- Provide sane defaults / "All" guards for template variables so they can't
  resolve to empty.
- Add an alert on the underlying metric's absence so "no data" surfaces as a real
  alert, not a silently blank panel.

## Related Errors

- [Grafana Query Error](./grafana-query-error.md)
- [Grafana Data Source Bad Gateway](./grafana-datasource-bad-gateway.md)

## References

- [Grafana panel inspector](https://grafana.com/docs/grafana/latest/panels-visualizations/panel-inspector/)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`grafana` · `panel` · `query` · `dashboard` · `production`
