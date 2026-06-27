---
title: "Prometheus Scrape 401 Unauthorized"
slug: prometheus-scrape-401-unauthorized
technologies: [prometheus]
severity: high
tags: [prometheus, scraping, authentication, security, production]
related: [prometheus-target-down-connection-refused, prometheus-config-reload-failed]
last_reviewed: 2026-06-27
---

# Prometheus Scrape 401 Unauthorized

## Error Message

```text
server returned HTTP status 401 Unauthorized
```

On the `/targets` page:

```text
State   Endpoint                              Error
DOWN    https://api:8443/metrics              server returned HTTP status 401 Unauthorized
```

## Description

The target is reachable and responded — but it rejected the scrape because
Prometheus did not present valid credentials. A `401` specifically means the
target requires authentication and the request either carried no credentials or
the wrong ones. (`403 Forbidden` is the related case where credentials were
accepted but lack permission.) Prometheus marks the target `DOWN` and `up` goes
to 0, but unlike a connection failure the HTTP layer is fully working.

## Technologies

- prometheus (scrape manager, HTTP client auth)

## Severity

**high** — the secured target yields no metrics. Because auth failures often
follow a credential rotation, they can take down many targets in a job at once
when a shared bearer token or password changes.

## Common Causes

1. A bearer token / basic-auth password rotated but the scrape config (or its
   referenced file) still holds the old value.
2. The scrape config has no `authorization` / `basic_auth` block for a target
   that requires it.
3. `bearer_token_file` points at a missing or empty file, so an empty token is
   sent.
4. For Kubernetes targets, the ServiceAccount token mounted into Prometheus
   expired or lost RBAC for the metrics endpoint.

## Root Cause Analysis

Prometheus attaches credentials per the job's auth config on every scrape
request. The target's auth middleware validates the `Authorization` header (or
mTLS/basic-auth) and returns `401` with `WWW-Authenticate` when it is missing or
invalid. Prometheus does not retry with different credentials — it records the
status verbatim. Because the failure is returned by the *application*, you will
see a real HTTP response, which cleanly distinguishes it from refused/timeout
target failures.

## Diagnostic Commands

```bash
# Confirm the API reports a 401 for the target
curl -s http://localhost:9090/api/v1/targets \
  | jq '.data.activeTargets[] | select(.lastError|test("401")) | {url:.scrapeUrl, lastError}'

# Reproduce WITHOUT credentials (expect 401) then WITH the token (expect 200)
curl -s -o /dev/null -w '%{http_code}\n' https://api:8443/metrics
curl -s -o /dev/null -w '%{http_code}\n' -H "Authorization: Bearer $(cat /etc/prometheus/token)" https://api:8443/metrics

# Show the (redacted) auth config Prometheus actually loaded for the job
curl -s http://localhost:9090/api/v1/status/config | jq -r '.data.yaml' | grep -A6 'job_name: api'
```

## Expected Results

```text
401      # no credentials
200      # with the correct bearer token
```

If the unauthenticated request returns `401` and the authenticated one returns
`200`, the credential in Prometheus's config is wrong or stale. Secrets in the
loaded config show as `<secret>`, so verify the *file* contents separately.

## Resolution

1. Update the credential Prometheus uses. With a token file, write the new token
   and let `bearer_token_file` reload on next scrape:

   ```yaml
   - job_name: api
     scheme: https
     authorization:
       type: Bearer
       credentials_file: /etc/prometheus/token
   ```
2. For basic auth, set `basic_auth.password_file` to a file holding the current
   password (avoid inlining secrets).
3. For Kubernetes, ensure the ServiceAccount token is mounted and RBAC permits
   scraping the endpoint.
4. Reload Prometheus (`POST /-/reload` or `SIGHUP`) after changing inline values.

## Validation

```bash
# Target should return to up == 1
curl -s 'http://localhost:9090/api/v1/query?query=up{job="api"}' | jq '.data.result[].value[1]'
# Expect: "1"
```

## Prevention

- Reference secrets via `*_file` options and rotate the file atomically so scrapes
  pick up new credentials without a reload.
- Alert on `up == 0` segmented by job to catch a fleet-wide credential rotation.
- Automate token rotation so Prometheus and targets update together.

## Related Errors

- [Prometheus Target Down: Connection Refused](./prometheus-target-down-connection-refused.md)
- [Prometheus Config Reload Failed](./prometheus-config-reload-failed.md)

## References

- [Prometheus: Scrape configuration (auth)](https://prometheus.io/docs/prometheus/latest/configuration/configuration/#scrape_config)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`prometheus` · `scraping` · `authentication` · `security` · `production`
