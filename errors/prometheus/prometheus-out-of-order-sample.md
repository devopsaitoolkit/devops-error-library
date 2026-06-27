---
title: "Prometheus Out-of-Order Sample"
slug: prometheus-out-of-order-sample
technologies: [prometheus]
severity: medium
tags: [prometheus, tsdb, ingestion, timestamps, production]
related: [prometheus-duplicate-sample-for-timestamp, prometheus-remote-write-429]
last_reviewed: 2026-06-27
---

# Prometheus Out-of-Order Sample

## Error Message

```text
Error on ingesting out-of-order samples" num_dropped=1842 ...
```

From the scrape loop, per series:

```text
err="out of order sample" series="http_requests_total{job=\"api\",instance=\"a:80\"}"
```

## Description

By default the Prometheus TSDB requires that, for any given series, samples
arrive with strictly increasing timestamps. When a sample arrives whose
timestamp is older than (or equal to and conflicting with) the most recent
sample already stored for that series, the head block rejects it as
`out of order` and drops it. This protects the append-only, time-sorted chunk
format. The error is most common with custom timestamps in the exposition
format, federation/recording across clocks, or remote-write from agents whose
clocks drift.

## Technologies

- prometheus (TSDB head, append path)

## Severity

**medium** — affected samples are silently dropped, leaving gaps in the series.
Scraping of other series continues, so it is a data-quality problem rather than
an outage, but graphs and alerts on the affected metric become unreliable.

## Common Causes

1. The exporter sets explicit timestamps in the exposition format that go
   backwards between scrapes (clock skew, replayed data).
2. Two sources push the *same* series via remote-write with unsynchronized
   clocks.
3. Federation pulls already-timestamped samples that are older than what the
   local TSDB already holds.
4. A target's host clock jumped backwards (NTP correction).

## Root Cause Analysis

The TSDB head appends samples into per-series chunks that must remain
monotonically ordered by time. The appender compares each incoming sample's `t`
against the series' `maxTime`. If `t < maxTime` (or `t == maxTime` with a
different value), it returns `storage.ErrOutOfOrderSample` and increments
`prometheus_tsdb_out_of_order_samples_total`. Unless out-of-order ingestion is
explicitly enabled (`tsdb.out_of_order_time_window`), there is no reordering
buffer, so the sample is simply lost.

## Diagnostic Commands

```bash
# Count of dropped out-of-order samples over time
curl -s 'http://localhost:9090/api/v1/query?query=rate(prometheus_tsdb_out_of_order_samples_total[5m])' \
  | jq '.data.result'

# Is the out-of-order window enabled? (0s means strict ordering)
curl -s http://localhost:9090/api/v1/status/config \
  | jq -r '.data.yaml' | grep -A3 'out_of_order'

# Inspect target exposition for explicit timestamps (a trailing number after the value)
curl -s http://10.0.4.21:9100/metrics | grep ' [0-9]\{13\}$' | head
```

## Expected Results

```text
[ { "metric": {}, "value": [ 1719500000, "30.4" ] } ]
```

A non-zero `rate(...out_of_order_samples_total)` confirms active drops. If the
exposition lines carry a 13-digit millisecond timestamp that does not advance
between scrapes, the exporter's timestamps are the culprit.

## Resolution

1. Prefer letting Prometheus assign the scrape timestamp — remove explicit
   timestamps from the exposition format unless you genuinely need them.
2. Fix clock skew across sources with NTP/chrony so remote-write producers agree
   on time.
3. If you *must* accept slightly late samples (e.g. buffered agents), enable a
   bounded out-of-order window:

   ```yaml
   storage:
     tsdb:
       out_of_order_time_window: 30m
   ```
4. Reload Prometheus and confirm the drop rate falls to zero.

## Validation

```bash
# Drop counter should stop increasing
curl -s 'http://localhost:9090/api/v1/query?query=increase(prometheus_tsdb_out_of_order_samples_total[10m])' \
  | jq '.data.result[].value[1]'
# Expect: "0"
```

## Prevention

- Do not emit client-side timestamps unless the data genuinely originates from a
  past event; let Prometheus stamp scrapes.
- Keep all metric producers on synchronized clocks.
- Dashboard `prometheus_tsdb_out_of_order_samples_total` so silent drops are
  visible.

## Related Errors

- [Prometheus Duplicate Sample for Timestamp](./prometheus-duplicate-sample-for-timestamp.md)
- [Prometheus Remote Write 429](./prometheus-remote-write-429.md)

## References

- [Prometheus: TSDB storage](https://prometheus.io/docs/prometheus/latest/storage/)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`prometheus` · `tsdb` · `ingestion` · `timestamps` · `production`
