---
title: "Prometheus PromQL Parse Error"
slug: prometheus-promql-parse-error
technologies: [prometheus]
severity: low
tags: [prometheus, promql, query, syntax, production]
related: [prometheus-query-processing-would-load-too-many-samples, prometheus-config-reload-failed]
last_reviewed: 2026-06-27
---

# Prometheus PromQL Parse Error

## Error Message

```text
{"status":"error","errorType":"bad_data","error":"1:14: parse error: unexpected character inside braces: '\"'"}
```

Another frequent variant:

```text
parse error: unexpected "}" in label matching, expected string
```

## Description

This error comes from the PromQL parser, not the storage engine. Before a query
runs, Prometheus tokenizes and parses the expression; if it does not conform to
PromQL grammar, it returns HTTP 400 with `errorType: bad_data` and a
`line:column` position. The query never touches the TSDB. The same parser backs
recording/alerting rule loading, so a malformed expression in a rule file
surfaces the same class of message at reload time.

## Technologies

- prometheus (PromQL parser, query API, rule loader)

## Severity

**low** — no impact on the running server; the bad query or rule simply fails to
evaluate. Severity rises if the broken expression is inside an alerting rule,
because that alert silently never fires.

## Common Causes

1. Unquoted or wrongly quoted label values (`{job=api}` instead of
   `{job="api"}`).
2. Mismatched braces, brackets, or parentheses.
3. A range selector on an instant context where one is not allowed (e.g.
   `rate(metric)` without `[5m]`).
4. YAML quoting in rule files mangling the expression (e.g. an unescaped `{{`).

## Root Cause Analysis

PromQL has a strict grammar: label matchers require double-quoted string values,
range selectors require a duration in square brackets, and functions have fixed
arities. The lexer reports the exact offset where a token violated the grammar —
the `1:14` prefix is `line:column`. Because parsing happens before evaluation,
the error is deterministic and reproducible from the expression text alone, which
makes it quick to fix once you read the column pointer.

## Diagnostic Commands

```bash
# Submit the exact expression and read the position the parser objected to
curl -s 'http://localhost:9090/api/v1/query' --data-urlencode 'query={job=api}' \
  | jq '.error'

# If the parse error is in a rule file, promtool pinpoints the line
promtool check rules /etc/prometheus/rules/*.yml

# Validate the whole config (which loads rule files too)
promtool check config /etc/prometheus/prometheus.yml
```

## Expected Results

```text
"1:6: parse error: unexpected identifier \"api\" in label matching, expected string"
```

The `line:column` and the "expected string" message point straight at the
unquoted value. `promtool check rules` prints the failing file and line for
rule-file cases; a clean run reports `SUCCESS`.

## Resolution

1. Quote label values and fix delimiters: `{job="api"}`.
2. Add the required range to functions that need one: `rate(metric[5m])`.
3. In rule YAML, wrap expressions that contain special characters in single or
   block quotes so YAML does not eat braces:

   ```yaml
   - record: job:http_requests:rate5m
     expr: 'sum by (job) (rate(http_requests_total[5m]))'
   ```
4. Re-run `promtool check rules` until it reports `SUCCESS`, then reload.

## Validation

```bash
# Corrected query should parse and return data
curl -s 'http://localhost:9090/api/v1/query' --data-urlencode 'query=up{job="api"}' \
  | jq '.status'
# Expect: "success"
```

## Prevention

- Run `promtool check config` and `promtool check rules` in CI on every change.
- Use an editor/LSP with PromQL syntax checking when authoring dashboards.
- Always single-quote rule `expr:` values in YAML.

## Related Errors

- [Prometheus query processing would load too many samples](./prometheus-query-processing-would-load-too-many-samples.md)
- [Prometheus Config Reload Failed](./prometheus-config-reload-failed.md)

## References

- [Prometheus: Querying basics](https://prometheus.io/docs/prometheus/latest/querying/basics/)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`prometheus` · `promql` · `query` · `syntax` · `production`
