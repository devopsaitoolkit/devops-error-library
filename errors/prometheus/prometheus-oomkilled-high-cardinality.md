---
title: "Prometheus OOMKilled from High Cardinality"
slug: prometheus-oomkilled-high-cardinality
technologies: [prometheus]
severity: critical
tags: [prometheus, tsdb, cardinality, memory, production]
related: [prometheus-query-processing-would-load-too-many-samples, prometheus-tsdb-no-space-left-on-device]
last_reviewed: 2026-06-27
---

# Prometheus OOMKilled from High Cardinality

## Error Message

```text
kernel: Out of memory: Killed process 2847 (prometheus) total-vm:38211940kB, anon-rss:31044120kB
```

As a Kubernetes pod status:

```text
Last State:  Terminated
  Reason:    OOMKilled
  Exit Code: 137
```

## Description

Prometheus keeps the active "head" of the TSDB — the most recent ~2 hours of
data plus the full in-memory index of every active series and label — resident in
RAM. Memory use scales primarily with the number of *active series*
(cardinality), not raw sample volume. When a label explosion pushes the series
count beyond what the host/limit can hold, the process's resident set grows until
the kernel (or the container runtime) kills it with `OOMKilled` / exit code 137.
On restart it must replay the WAL, briefly spiking memory again — sometimes into
a crash loop.

## Technologies

- prometheus (TSDB head, in-memory index)

## Severity

**critical** — an OOMKill takes monitoring fully offline, and WAL replay on
restart can re-trigger the kill, producing a crash loop with no metrics and no
alerting. This is a full observability outage.

## Common Causes

1. A label with unbounded values (user ID, full URL path, request ID, pod UID)
   creating a near-infinite number of series.
2. A new exporter or app version that adds high-cardinality labels.
3. A buggy client that mints a fresh label value per request.
4. Retention/ingestion grew faster than the memory budget.

## Root Cause Analysis

Active series = the cross-product of all label values currently being scraped.
Each unique series carries an in-memory entry in the head index plus head
chunks. A single label with 100k distinct values multiplied across other labels
can produce millions of series. The head memory is roughly proportional to that
count, so cardinality — not sample rate — dominates RAM. When RSS exceeds the
cgroup limit or host memory, the OOM killer reaps the process. WAL replay rebuilds
the same head, so the underlying cardinality must be cut or the kill repeats.

## Diagnostic Commands

```bash
# TSDB status: top metrics by series count and worst-offending labels
curl -s http://localhost:9090/api/v1/status/tsdb \
  | jq '{topMetrics: .data.seriesCountByMetricName[0:10], topLabels: .data.labelValueCountByLabelName[0:10]}'

# Total active head series
curl -s 'http://localhost:9090/api/v1/query?query=prometheus_tsdb_head_series' \
  | jq '.data.result[].value[1]'

# Resident memory trend
curl -s 'http://localhost:9090/api/v1/query?query=process_resident_memory_bytes' \
  | jq '.data.result[].value[1]'

# Confirm the OOM kill from the host journal
journalctl -k --since "-1h" | grep -i "out of memory\|oom-killer"
```

## Expected Results

```text
{
  "topLabels": [ { "name": "path", "value": 184203 } ],
  "topMetrics": [ { "name": "http_request_duration_seconds_bucket", "value": 2200000 } ]
}
```

A label like `path` or `id` with tens/hundreds of thousands of values, or a
single metric with millions of series, is the smoking gun. `prometheus_tsdb_head_series`
in the millions confirms the cardinality problem.

## Resolution

1. Drop the offending high-cardinality label at scrape time so it never enters
   the TSDB:

   ```yaml
   metric_relabel_configs:
     - source_labels: [__name__]
       regex: 'http_request_duration_seconds_bucket'
       action: keep
     - regex: 'path|request_id'
       action: labeldrop
   ```
2. Fix the source — bound the label (use a route template like `/users/:id`, not
   the raw path) in the application/exporter.
3. Give the process enough headroom to survive WAL replay temporarily (raise the
   memory limit) so you can break a crash loop while you cut cardinality.
4. After dropping series, allow head compaction so memory falls.

## Validation

```bash
# Head series should drop sharply and memory stabilize below the limit
curl -s 'http://localhost:9090/api/v1/query?query=prometheus_tsdb_head_series' \
  | jq '.data.result[].value[1]'
# Expect a much lower, stable count with no further OOMKilled events
```

## Prevention

- Forbid unbounded labels (IDs, raw paths, timestamps) in metric design reviews.
- Alert on `prometheus_tsdb_head_series` growth rate and on rising
  `process_resident_memory_bytes`.
- Use `metric_relabel_configs` allow/deny lists as a guardrail against new
  exporters introducing cardinality.

## Related Errors

- [Prometheus query processing would load too many samples](./prometheus-query-processing-would-load-too-many-samples.md)
- [Prometheus TSDB No Space Left on Device](./prometheus-tsdb-no-space-left-on-device.md)

## References

- [Prometheus: Cardinality and instrumentation best practices](https://prometheus.io/docs/practices/instrumentation/)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`prometheus` · `tsdb` · `cardinality` · `memory` · `production`
