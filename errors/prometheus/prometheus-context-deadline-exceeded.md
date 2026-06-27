---
title: "Prometheus Context Deadline Exceeded"
slug: prometheus-context-deadline-exceeded
technologies: [prometheus]
severity: high
tags: [prometheus, scraping, timeout, performance, production]
related: [prometheus-target-down-connection-refused, prometheus-query-processing-would-load-too-many-samples]
last_reviewed: 2026-06-27
---

# Prometheus Context Deadline Exceeded

## Error Message

```text
Get "http://10.0.4.21:9100/metrics": context deadline exceeded
```

A common variant when TLS or the headers stall:

```text
Get "https://app:8443/metrics": context deadline exceeded (Client.Timeout exceeded while awaiting headers)
```

## Description

Prometheus bounds every scrape with a `scrape_timeout` (default 10s, never
larger than `scrape_interval`). When the target does not return a full,
parseable response within that window, Go cancels the request context and the
scrape fails with `context deadline exceeded`. The target may be reachable and
even partway through responding — the problem is *latency*, not refusal. The
target is marked `DOWN` and `up` goes to 0, exactly like a refused connection,
but the cause and fix are completely different.

## Technologies

- prometheus (scrape manager)

## Severity

**high** — a timing-out target reports no metrics. Worse, a slow `/metrics`
endpoint often signals the target itself is under load, so you lose visibility
precisely when you most need it.

## Common Causes

1. The exporter renders a very large or high-cardinality `/metrics` payload that
   takes longer than `scrape_timeout` to generate or transfer.
2. The target host is CPU-starved or swapping, so the handler is slow.
3. `scrape_timeout` is set too low for a legitimately heavy endpoint (e.g.
   `kube-state-metrics` on a large cluster).
4. A slow TLS handshake or a proxy in the path adds latency.

## Root Cause Analysis

The scrape is wrapped in a `context.WithTimeout(scrape_timeout)`. The clock
starts at the moment Prometheus initiates the request and covers DNS, connect,
TLS, *and* reading the entire body. If the exporter computes metrics lazily on
each scrape (many do), a growing series count linearly increases response time
until it crosses the deadline. Because the failure is time-based, it often
appears intermittently first — some scrapes squeak in under the limit — before
becoming permanent.

## Diagnostic Commands

```bash
# Which targets are timing out, per the API
curl -s http://localhost:9090/api/v1/targets \
  | jq '.data.activeTargets[] | select(.lastError|test("deadline")) | {url:.scrapeUrl, lastScrapeDuration, lastError}'

# Measure how long the target actually takes to respond, with byte size
curl -s -o /dev/null -w 'time=%{time_total}s size=%{size_download}bytes\n' http://10.0.4.21:9100/metrics

# How big is the response — count exposed series
curl -s http://10.0.4.21:9100/metrics | grep -vc '^#'
```

## Expected Results

```text
time=12.84s size=41203338bytes
```

A response that takes longer than `scrape_timeout` (e.g. 12.8s against a 10s
timeout) confirms the diagnosis. `lastScrapeDuration` in the API will hover at
or above the timeout. A healthy target returns in well under a second.

## Resolution

1. Reduce the payload at the source: drop unneeded high-cardinality metrics with
   `metric_relabel_configs` `drop` actions, or disable expensive collectors.
2. If the endpoint is legitimately heavy, raise the timeout (and interval if
   needed) for that job only:

   ```yaml
   - job_name: kube-state-metrics
     scrape_interval: 60s
     scrape_timeout: 55s   # must be <= scrape_interval
   ```
3. Fix host resource pressure (CPU/memory) on the target so the handler is fast.
4. Reload Prometheus and watch `scrape_duration_seconds` for the job.

## Validation

```bash
# Scrape duration should sit comfortably under the timeout
curl -s 'http://localhost:9090/api/v1/query?query=scrape_duration_seconds{instance="10.0.4.21:9100"}' \
  | jq '.data.result[].value[1]'
# Expect a value well below scrape_timeout, and up == 1
```

## Prevention

- Alert on `scrape_duration_seconds / scrape_timeout > 0.8` to catch slow
  scrapes before they fail.
- Keep `/metrics` small: trim labels and cardinality at the exporter.
- Never set `scrape_timeout` larger than `scrape_interval` — Prometheus rejects
  the config.

## Related Errors

- [Prometheus Target Down: Connection Refused](./prometheus-target-down-connection-refused.md)
- [Prometheus query processing would load too many samples](./prometheus-query-processing-would-load-too-many-samples.md)

## References

- [Prometheus: Scrape configuration](https://prometheus.io/docs/prometheus/latest/configuration/configuration/#scrape_config)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`prometheus` · `scraping` · `timeout` · `performance` · `production`
