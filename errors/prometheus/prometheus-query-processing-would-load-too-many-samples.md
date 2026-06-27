---
title: "Prometheus Query Processing Would Load Too Many Samples"
slug: prometheus-query-processing-would-load-too-many-samples
technologies: [prometheus]
severity: medium
tags: [prometheus, promql, query, cardinality, production]
related: [prometheus-context-deadline-exceeded, prometheus-oomkilled-high-cardinality]
last_reviewed: 2026-06-27
---

# Prometheus Query Processing Would Load Too Many Samples

## Error Message

```text
query processing would load too many samples into memory in query execution
```

As returned by the HTTP query API:

```text
{"status":"error","errorType":"execution","error":"query processing would load too many samples into memory in query execution"}
```

## Description

Prometheus caps how many samples a single query may pull into memory at once via
`--query.max-samples` (default 50,000,000). Before and during evaluation the
engine counts the samples it must materialize; if a step would exceed the limit,
it aborts the whole query with this error rather than risk an OOM. The limit is a
safety valve — it protects the server from a single pathological query taking it
down, at the cost of failing that query.

## Technologies

- prometheus (PromQL engine, query layer)

## Severity

**medium** — the offending query fails, but Prometheus itself stays healthy and
keeps serving other queries. Dashboards or alerts that issue the query break
until it is narrowed.

## Common Causes

1. A query with no label matchers over a high-cardinality metric (e.g.
   `sum(http_requests_total)` across millions of series).
2. A very long range selector combined with a short resolution
   (`metric[30d]` at 15s scrape interval).
3. A regex matcher (`=~".*"`) that matches far more series than intended.
4. `--query.max-samples` lowered below what legitimate dashboards need.

## Root Cause Analysis

The PromQL engine estimates the working set as roughly
`series_selected × points_per_series_in_range`. For an instant query the points
are bounded, but a range query over `[d]` at interval `i` loads about `d / i`
points per series. Multiply by the number of series the selector matches and the
total can explode. The engine checks this running total against
`maxSamples` and, if exceeded, returns the error before allocating the chunks —
which is why the query fails fast rather than slowly degrading.

## Diagnostic Commands

```bash
# What is the configured limit?
curl -s http://localhost:9090/api/v1/status/flags | jq '.data["query.max-samples"]'

# How many series does the selector match? (cardinality of the offending metric)
curl -s 'http://localhost:9090/api/v1/query?query=count(http_requests_total)' \
  | jq '.data.result[].value[1]'

# TSDB cardinality overview — biggest metrics and label churn
curl -s http://localhost:9090/api/v1/status/tsdb \
  | jq '.data.seriesCountByMetricName[0:10]'
```

## Expected Results

```text
"50000000"      # the max-samples limit
"1830000"       # series matched by the bare metric — far too many
```

A series count that, multiplied by the range's points-per-series, exceeds the
limit confirms the cause. The TSDB status will usually show the same metric near
the top of `seriesCountByMetricName`.

## Resolution

1. Add label matchers to narrow the selector before aggregating:
   `sum by (job) (rate(http_requests_total{job="api"}[5m]))`.
2. Use recording rules to pre-aggregate expensive high-cardinality queries so
   dashboards read a small derived series instead.
3. Shorten the range or coarsen the step for wide historical queries.
4. If the limit is genuinely too low for valid workloads, raise it
   deliberately and watch memory: `--query.max-samples=100000000`.

## Validation

```bash
# The narrowed query should now succeed
curl -s 'http://localhost:9090/api/v1/query?query=sum%20by%20(job)%20(rate(http_requests_total%7Bjob%3D%22api%22%7D%5B5m%5D))' \
  | jq '.status'
# Expect: "success"
```

## Prevention

- Build dashboards on recording rules, not raw high-cardinality selectors.
- Educate teams to always scope metrics with label matchers.
- Track `count by (__name__)({__name__=~".+"})` to catch cardinality growth
  early.

## Related Errors

- [Prometheus Context Deadline Exceeded](./prometheus-context-deadline-exceeded.md)
- [Prometheus OOMKilled from High Cardinality](./prometheus-oomkilled-high-cardinality.md)

## References

- [Prometheus: Querying basics](https://prometheus.io/docs/prometheus/latest/querying/basics/)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`prometheus` · `promql` · `query` · `cardinality` · `production`
