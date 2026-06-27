---
title: "Prometheus Too Many Open Files"
slug: prometheus-too-many-open-files
technologies: [prometheus]
severity: high
tags: [prometheus, tsdb, ulimit, filedescriptors, production]
related: [prometheus-tsdb-no-space-left-on-device, prometheus-oomkilled-high-cardinality]
last_reviewed: 2026-06-27
---

# Prometheus Too Many Open Files

## Error Message

```text
level=error component=tsdb msg="Failed to open block" err="open /prometheus/01H.../chunks/000001: too many open files"
```

From the scrape or HTTP layer:

```text
accept tcp [::]:9090: accept4: too many open files
```

## Description

Prometheus memory-maps every chunk file in its persistent blocks and holds
network sockets for scrapes and the HTTP API, so it legitimately needs a large
number of file descriptors. When the process hits its `RLIMIT_NOFILE` (open-file
limit), the kernel returns `EMFILE` and any operation needing a new descriptor —
opening a block, accepting a connection, or rotating the WAL — fails with
`too many open files`. The server stays up but degrades: scrapes fail, queries
error, and compaction can stall.

## Technologies

- prometheus (TSDB mmap, HTTP server, OS limits)

## Severity

**high** — a process at its FD ceiling cannot reliably scrape, serve queries, or
compact. It often manifests as widespread intermittent failures that are easy to
misdiagnose as a network problem.

## Common Causes

1. The systemd unit or container has a low `LimitNOFILE` (e.g. the old default
   of 1024) while the TSDB has many blocks/series.
2. Series/block growth increased the number of mmap'd chunk files past the
   limit.
3. Many concurrent HTTP API consumers (Grafana, federation) hold open sockets.
4. A descriptor leak in an exporter or sidecar sharing the limit.

## Root Cause Analysis

Each persistent block contains chunk and index files that Prometheus mmaps; the
mmap counts against the open-file limit, and the count scales with the number of
blocks and series. Add active TCP sockets for scrapes and the API. When the sum
reaches `RLIMIT_NOFILE`, every `open()`/`accept4()` returns `EMFILE`. Because the
limit is per-process and enforced by the kernel, the fix is to raise the limit to
match the real working set — not to restart and hope, which only resets the
counter until it climbs again.

## Diagnostic Commands

```bash
# Prometheus exposes its own FD usage and the soft limit
curl -s 'http://localhost:9090/api/v1/query?query=process_open_fds' | jq '.data.result[].value[1]'
curl -s 'http://localhost:9090/api/v1/query?query=process_max_fds' | jq '.data.result[].value[1]'

# The effective limit for the running process
cat /proc/$(pgrep -o prometheus)/limits | grep "open files"

# Count of descriptors actually held
ls /proc/$(pgrep -o prometheus)/fd | wc -l

# EMFILE errors in the journal
journalctl -u prometheus --since "-30min" | grep -i "too many open files"
```

## Expected Results

```text
process_open_fds   1019
process_max_fds    1024
```

When `process_open_fds` sits at or just under `process_max_fds`, you have hit the
ceiling. `/proc/<pid>/limits` will show the same soft limit, confirming it is an
OS limit and not a Prometheus bug.

## Resolution

1. Raise the limit for the service. For systemd, set it in the unit and reload:

   ```ini
   [Service]
   LimitNOFILE=65536
   ```
   ```bash
   systemctl daemon-reload && systemctl restart prometheus
   ```
2. For containers, raise the ulimit (`--ulimit nofile=65536:65536`) or the
   pod/runtime default.
3. If growth is driven by cardinality, also reduce series so the FD need stops
   climbing.
4. Verify the new limit took effect via `/proc/<pid>/limits`.

## Validation

```bash
# Headroom should exist between open and max FDs
curl -s 'http://localhost:9090/api/v1/query?query=process_max_fds - process_open_fds' \
  | jq '.data.result[].value[1]'
# Expect a comfortably positive number
```

## Prevention

- Set `LimitNOFILE` generously (65536+) in the Prometheus unit from day one.
- Alert on `process_open_fds / process_max_fds > 0.8`.
- Track series and block counts so FD demand growth is visible in advance.

## Related Errors

- [Prometheus TSDB No Space Left on Device](./prometheus-tsdb-no-space-left-on-device.md)
- [Prometheus OOMKilled from High Cardinality](./prometheus-oomkilled-high-cardinality.md)

## References

- [Prometheus: Storage operational aspects](https://prometheus.io/docs/prometheus/latest/storage/#operational-aspects)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`prometheus` · `tsdb` · `ulimit` · `filedescriptors` · `production`
