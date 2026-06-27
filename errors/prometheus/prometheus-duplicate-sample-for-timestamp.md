---
title: "Prometheus Duplicate Sample for Timestamp"
slug: prometheus-duplicate-sample-for-timestamp
technologies: [prometheus]
severity: medium
tags: [prometheus, tsdb, ingestion, labels, production]
related: [prometheus-out-of-order-sample, prometheus-remote-write-429]
last_reviewed: 2026-06-27
---

# Prometheus Duplicate Sample for Timestamp

## Error Message

```text
Error on ingesting samples with different value but same timestamp" series="node_cpu_seconds_total{cpu=\"0\",mode=\"idle\",instance=\"a:9100\"}" ...
```

The shorter form engineers paste into search:

```text
duplicate sample for timestamp
```

## Description

Within a single scrape, every exposed time series must be unique by its full
label set. If two lines in the `/metrics` payload resolve to the *same* series
(same metric name and identical labels) but carry different values at the same
scrape timestamp, Prometheus cannot decide which is correct and rejects the
duplicate as `duplicate sample for timestamp`. The first sample for that series is
kept and the conflicting one is dropped. It is an exposition/relabeling problem,
not a clock problem (contrast with out-of-order samples, which are about time).

## Technologies

- prometheus (scrape parser, TSDB append)

## Severity

**medium** — the duplicate samples are dropped, so the affected series may show
wrong or missing values, but the scrape of other series succeeds. It is a
data-correctness issue rather than an outage.

## Common Causes

1. The exporter emits the same metric with identical labels twice in one scrape
   (a bug or double registration).
2. `relabel_configs` / `metric_relabel_configs` collapse two distinct series into
   one by dropping a distinguishing label (e.g. `labeldrop` of `cpu`).
3. `honor_labels` interaction or static `labels` overwrite a label so previously
   distinct series merge.
4. Two scraped sources are merged into one job and produce colliding series.

## Root Cause Analysis

After parsing and relabeling, Prometheus builds the final label set for each
sample and appends it to the head keyed by `(labels, timestamp)`. If two samples
in the same scrape produce the identical key with differing values, the appender
returns `storage.ErrDuplicateSampleForTimestamp`. The crucial insight is that
relabeling runs *before* the append, so a relabel rule that removes a
distinguishing label is a very common silent cause — the exporter is fine, but
your pipeline merged two series into one.

## Diagnostic Commands

```bash
# Count of dropped duplicates over time
curl -s 'http://localhost:9090/api/v1/query?query=rate(prometheus_target_scrapes_sample_duplicate_timestamp_total[5m])' \
  | jq '.data.result'

# Find duplicate lines in the raw exposition (same metric+labels appearing twice)
curl -s http://10.0.4.21:9100/metrics | grep -v '^#' | sed 's/ [^ ]*$//' | sort | uniq -d | head

# Inspect the relabel rules that might be collapsing labels
curl -s http://localhost:9090/api/v1/status/config | jq -r '.data.yaml' | grep -A8 'relabel_configs'
```

## Expected Results

```text
node_cpu_seconds_total{cpu="0",mode="idle",instance="a:9100"}
node_cpu_seconds_total{cpu="0",mode="idle",instance="a:9100"}
```

`uniq -d` printing two identical label sets confirms the exposition has true
duplicates. If the raw `/metrics` is clean but duplicates still appear, a
`labeldrop`/`replace` relabel rule is merging series — that is the cause.

## Resolution

1. If the exporter emits duplicates, fix it to register/expose each series once.
2. If a relabel rule collapses series, stop dropping the distinguishing label, or
   re-add an identifying label so the series stay distinct:

   ```yaml
   metric_relabel_configs:
     # WRONG: action: labeldrop  regex: cpu   <- merges per-cpu series
     # Keep the label, or aggregate intentionally with a recording rule instead.
   ```
3. If two sources were merged into one job, split them so their series do not
   collide, or add a `source`/`instance` label to differentiate.
4. Reload and confirm the duplicate counter stops rising.

## Validation

```bash
# Duplicate-drop counter should stop increasing
curl -s 'http://localhost:9090/api/v1/query?query=increase(prometheus_target_scrapes_sample_duplicate_timestamp_total[10m])' \
  | jq '.data.result[].value[1]'
# Expect: "0"
```

## Prevention

- Review `relabel_configs` for `labeldrop`/`replace` rules that could merge
  series before deploying them.
- Add a synthetic test that scrapes new exporters and checks for duplicate label
  sets.
- Dashboard `prometheus_target_scrapes_sample_duplicate_timestamp_total` so
  silent drops are visible.

## Related Errors

- [Prometheus Out-of-Order Sample](./prometheus-out-of-order-sample.md)
- [Prometheus Remote Write 429](./prometheus-remote-write-429.md)

## References

- [Prometheus: Relabeling](https://prometheus.io/docs/prometheus/latest/configuration/configuration/#relabel_config)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`prometheus` · `tsdb` · `ingestion` · `labels` · `production`
