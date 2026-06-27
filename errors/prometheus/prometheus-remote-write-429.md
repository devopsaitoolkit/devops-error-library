---
title: "Prometheus Remote Write 429 Too Many Requests"
slug: prometheus-remote-write-429
technologies: [prometheus]
severity: medium
tags: [prometheus, remote-write, backpressure, throttling, production]
related: [prometheus-out-of-order-sample, prometheus-duplicate-sample-for-timestamp]
last_reviewed: 2026-06-27
---

# Prometheus Remote Write 429 Too Many Requests

## Error Message

```text
level=warn component=remote msg="Failed to send batch, retrying" err="server returned HTTP status 429 Too Many Requests"
```

A throttling variant including the retry hint:

```text
remote_write: 429 Too Many Requests (retry after 1s); samples dropped after retries exhausted
```

## Description

When Prometheus forwards samples to a remote endpoint (Mimir, Thanos Receive,
Cortex, a vendor backend) via `remote_write`, the receiver can push back with
HTTP `429` to signal it is over its ingestion or rate limit. Prometheus treats
`429` as retryable: it backs off and retries from its in-memory queue. If the
backlog cannot drain within the queue/retry limits, samples are eventually
dropped. Sustained `429`s mean the remote backend cannot keep up with your
ingestion rate or you are hitting a per-tenant quota.

## Technologies

- prometheus (remote-write queue manager)

## Severity

**medium** — Prometheus's local TSDB is unaffected, so local queries still work.
But samples destined for the remote (often the long-term/global store) are
delayed and, if the queue saturates, lost — creating gaps in the central view.

## Common Causes

1. The remote backend's per-tenant ingestion rate or active-series limit is
   exceeded.
2. A cardinality spike pushed the sample rate above the configured quota.
3. Remote-write queue (`max_samples_per_send`, `max_shards`) is tuned to push
   faster than the backend accepts.
4. The backend is itself degraded/overloaded and shedding load with `429`.

## Root Cause Analysis

The remote-write queue manager shards pending samples and sends batches
concurrently. The receiver enforces limits and returns `429` (sometimes with
`Retry-After`) when a tenant exceeds them. Prometheus increments
`prometheus_remote_storage_samples_failed_total` / `..._retried_total`, applies
exponential backoff, and keeps the samples queued. The queue has a bounded
capacity (`capacity × max_shards`); once full, the oldest samples are dropped and
`prometheus_remote_storage_samples_dropped_total` rises. So `429` is backpressure
— the fix is to send less or raise the receiver's limit, not to push harder.

## Diagnostic Commands

```bash
# Failed and dropped remote-write samples over time
curl -s 'http://localhost:9090/api/v1/query?query=rate(prometheus_remote_storage_samples_failed_total[5m])' \
  | jq '.data.result'

# Queue backlog: is the pending queue filling up?
curl -s 'http://localhost:9090/api/v1/query?query=prometheus_remote_storage_samples_pending' \
  | jq '.data.result[].value[1]'

# The remote_write block actually loaded
curl -s http://localhost:9090/api/v1/status/config | jq -r '.data.yaml' | grep -A12 'remote_write'

# Receiver-side limit/throttle messages
journalctl -u prometheus --since "-15min" | grep -i "429\|remote"
```

## Expected Results

```text
[ { "metric": {"remote_name":"mimir","url":"https://mimir/api/v1/push"}, "value": [ 1719500000, "1240" ] } ]
```

A non-zero `samples_failed_total` rate plus a rising `samples_pending` confirms
the receiver is throttling and the queue is backing up. Healthy remote-write
keeps failed/dropped at 0 and pending near 0.

## Resolution

1. Reduce what you send: drop high-cardinality or unneeded series with
   `write_relabel_configs` before they leave Prometheus:

   ```yaml
   remote_write:
     - url: https://mimir/api/v1/push
       write_relabel_configs:
         - source_labels: [__name__]
           regex: 'go_.*|process_.*'
           action: drop
   ```
2. Ask the backend owner to raise the tenant's ingestion-rate / active-series
   limit if the volume is legitimate.
3. Tune the queue conservatively rather than aggressively
   (`max_shards`, `max_samples_per_send`) so retries can drain.
4. If the backend is overloaded, scale its receive/ingester tier.

## Validation

```bash
# Failed/dropped counters should stop climbing and pending should fall
curl -s 'http://localhost:9090/api/v1/query?query=rate(prometheus_remote_storage_samples_dropped_total[5m])' \
  | jq '.data.result[].value[1]'
# Expect: "0"
```

## Prevention

- Apply `write_relabel_configs` to ship only the series the remote actually
  needs.
- Alert on `prometheus_remote_storage_samples_pending` and `..._failed_total`.
- Agree on and monitor the per-tenant quota with the backend team.

## Related Errors

- [Prometheus Out-of-Order Sample](./prometheus-out-of-order-sample.md)
- [Prometheus Duplicate Sample for Timestamp](./prometheus-duplicate-sample-for-timestamp.md)

## References

- [Prometheus: Remote write tuning](https://prometheus.io/docs/practices/remote_write/)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`prometheus` · `remote-write` · `backpressure` · `throttling` · `production`
