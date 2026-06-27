---
title: "Prometheus Config Reload Failed"
slug: prometheus-config-reload-failed
technologies: [prometheus]
severity: high
tags: [prometheus, configuration, reload, validation, production]
related: [prometheus-promql-parse-error, prometheus-scrape-401-unauthorized]
last_reviewed: 2026-06-27
---

# Prometheus Config Reload Failed

## Error Message

```text
level=error msg="Error reloading config" err="couldn't load configuration (--config.file=\"/etc/prometheus/prometheus.yml\"): parsing YAML file /etc/prometheus/prometheus.yml: yaml: line 42: mapping values are not allowed in this context"
```

The reload endpoint surfaces it as:

```text
HTTP/1.1 400 Bad Request
failed to reload config: ...
```

## Description

Prometheus reloads its configuration on `SIGHUP` or `POST /-/reload`. The reload
is transactional: the new file is fully parsed and validated first, and only if
it is valid does it replace the running config. If parsing or validation fails,
Prometheus logs the error, rejects the reload, and **keeps running on the
previous good config**. So a failed reload does not crash the server — but your
intended change (new targets, rules, relabeling) silently does not take effect.

## Technologies

- prometheus (config loader, reload handler)

## Severity

**high** — the running server is fine, but the change you shipped is not live.
If you believed a new alerting rule or scrape job deployed when it did not, you
have a dangerous gap between expectation and reality.

## Common Causes

1. YAML syntax errors — bad indentation, tabs instead of spaces, a stray colon.
2. A referenced file is missing (`rule_files`, `*_file` secrets,
   `file_sd_configs` target files).
3. Invalid field values (e.g. `scrape_timeout` greater than `scrape_interval`,
   an unknown relabel `action`).
4. A rule file referenced by the config contains an invalid PromQL expression.

## Root Cause Analysis

The loader parses YAML into typed config structs and then runs semantic
validation (cross-field constraints, file existence, rule compilation). Any
failure returns an error from `LoadFile`, the reload handler responds `400`, and
the in-memory config is left untouched. Because the active config is preserved,
the only visible signal is the log line and the metric
`prometheus_config_last_reload_successful` flipping to 0 — which is exactly why a
failed reload is easy to miss without monitoring.

## Diagnostic Commands

```bash
# Did the last reload succeed? 1 = yes, 0 = no
curl -s 'http://localhost:9090/api/v1/query?query=prometheus_config_last_reload_successful' \
  | jq '.data.result[].value[1]'

# Validate the file the SAME way Prometheus does, before reloading
promtool check config /etc/prometheus/prometheus.yml

# The exact reload error from the journal
journalctl -u prometheus --since "-15min" | grep -i "reloading config\|loading configuration"
```

## Expected Results

```text
"0"     # last reload failed
```

```text
Checking /etc/prometheus/prometheus.yml
  FAILED: parsing YAML file ...: yaml: line 42: mapping values are not allowed in this context
```

`promtool` reports the same error and line number Prometheus would, so you can
fix it without touching the live process.

## Resolution

1. Run `promtool check config` and fix the reported line — most often
   indentation or a missing referenced file.
2. Confirm all referenced files exist and are readable by the Prometheus user
   (`rule_files`, secret `*_file`, `file_sd_configs`).
3. Re-validate until `promtool` reports `SUCCESS`.
4. Reload again and confirm success:

   ```bash
   curl -s -X POST http://localhost:9090/-/reload
   ```

## Validation

```bash
# Reload metric should be 1 after a clean reload
curl -s 'http://localhost:9090/api/v1/query?query=prometheus_config_last_reload_successful' \
  | jq '.data.result[].value[1]'
# Expect: "1"
```

## Prevention

- Gate every config/rule change in CI with `promtool check config` and
  `promtool check rules`.
- Alert on `prometheus_config_last_reload_successful == 0` so a silent failed
  reload pages you.
- Deploy config via a templating tool that renders and validates before
  shipping.

## Related Errors

- [Prometheus PromQL Parse Error](./prometheus-promql-parse-error.md)
- [Prometheus Scrape 401 Unauthorized](./prometheus-scrape-401-unauthorized.md)

## References

- [Prometheus: Configuration](https://prometheus.io/docs/prometheus/latest/configuration/configuration/)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`prometheus` · `configuration` · `reload` · `validation` · `production`
