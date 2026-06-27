---
title: "Grafana Request Entity Too Large (413)"
slug: grafana-request-entity-too-large-413
technologies: [grafana]
severity: medium
tags: [grafana, proxy, http, dashboard, production]
related: [grafana-failed-to-load-dashboards, grafana-datasource-proxy-error]
last_reviewed: 2026-06-27
---

# Grafana Request Entity Too Large (413)

## Error Message

```text
413 Request Entity Too Large
```

```text
<html>
<head><title>413 Request Entity Too Large</title></head>
<body><center><h1>413 Request Entity Too Large</h1></center>
<hr><center>nginx</center></body>
</html>
```

```text
{"message":"Request Entity Too Large","traceID":""}
```

## Description

**413 Request Entity Too Large** is returned when the body of an HTTP request to
Grafana exceeds a maximum size limit. It most often appears when **saving a large
dashboard** (many panels / large JSON), importing a big dashboard, or uploading a
file/snapshot. The limit is enforced either by a **reverse proxy in front of
Grafana** (nginx `client_max_body_size`, Traefik/Ingress body limits) or by
Grafana itself if so configured. The tell-tale is whether the 413 page is branded
by the proxy (nginx) or returned as Grafana JSON.

## Technologies

- grafana (HTTP server) and/or fronting reverse proxy (nginx / Ingress / Traefik)

## Severity

**medium** — large dashboards cannot be saved/imported, blocking edits to those
specific objects; the rest of Grafana works normally.

## Common Causes

1. A reverse proxy (nginx) with a default `client_max_body_size 1m` rejects the
   dashboard-save POST that exceeds 1 MB.
2. A Kubernetes Ingress (`nginx.ingress.kubernetes.io/proxy-body-size`) caps the
   request body.
3. The dashboard JSON is genuinely huge (hundreds of panels, embedded data,
   inline images/snapshots).
4. Large annotation or snapshot uploads exceed the limit.
5. Grafana behind a CDN/WAF that imposes its own body-size cap.

## Root Cause Analysis

Saving a dashboard issues `POST /api/dashboards/db` with the entire dashboard
JSON as the body. As the request passes through the proxy, the proxy compares the
`Content-Length` (or streamed body) against its body-size limit and, if exceeded,
returns 413 **before the request ever reaches Grafana**. That is why the 413 page
is often nginx-branded rather than Grafana JSON. The size grows with panel count,
inline/base64 content, and template options, so very large boards cross the
default 1 MB limit.

## Diagnostic Commands

```bash
# Is the 413 from the proxy or from Grafana? Inspect the Server header
curl -s -o /dev/null -D - -X POST https://grafana.example.com/api/dashboards/db \
  -H "Authorization: Bearer $GRAFANA_TOKEN" -H "Content-Type: application/json" \
  --data-binary @big-dashboard.json | grep -iE "HTTP/|server:"

# Measure the dashboard payload size (compare to the proxy limit)
curl -s -H "Authorization: Bearer $GRAFANA_TOKEN" \
  "http://localhost:3000/api/dashboards/uid/<uid>" | wc -c

# Reverse-proxy body limit (nginx, read-only)
grep -rni "client_max_body_size" /etc/nginx/

# Ingress body-size annotation (Kubernetes)
kubectl get ingress grafana -o jsonpath='{.metadata.annotations.nginx\.ingress\.kubernetes\.io/proxy-body-size}'
```

## Expected Results

```text
HTTP/1.1 413 Request Entity Too Large
Server: nginx                       <-- 413 came from nginx, not Grafana
```

A `Server: nginx` (or Traefik/Ingress) header on the 413 confirms the proxy
rejected it. The `wc -c` byte count vs. the configured `client_max_body_size`
shows you are over the limit (e.g. payload 1.6 MB > `1m`).

## Resolution

1. Raise the body-size limit on whichever layer returned the 413.
   - **nginx:** in the relevant `server`/`location` block, then reload:

     ```nginx
     client_max_body_size 16m;
     ```
     ```bash
     sudo nginx -t && sudo systemctl reload nginx
     ```
   - **Kubernetes nginx Ingress:** annotate the Ingress:

     ```yaml
     metadata:
       annotations:
         nginx.ingress.kubernetes.io/proxy-body-size: "16m"
     ```
2. If a CDN/WAF caps it, raise that limit too (the request must pass every hop).
3. **Also** shrink the dashboard: split monster boards, remove inline/base64
   data, and use library panels — a smaller payload is the durable fix.

## Validation

```bash
# Re-POST the dashboard; expect 200 with a version number, not 413
curl -s -X POST https://grafana.example.com/api/dashboards/db \
  -H "Authorization: Bearer $GRAFANA_TOKEN" -H "Content-Type: application/json" \
  --data-binary @big-dashboard.json | jq '{status, version}'
# Expect: {"status":"success","version":N}
```

## Prevention

- Set a generous, consistent body-size limit across every proxy/Ingress/CDN in
  front of Grafana (e.g. 16m) as part of infra-as-code.
- Keep dashboards lean: split very large boards, avoid embedding data, use
  library panels.
- Add a CI guard that flags dashboard JSON over a size threshold.

## Related Errors

- [Grafana Failed to Load Dashboards](./grafana-failed-to-load-dashboards.md)
- [Grafana Data Source Proxy Error](./grafana-datasource-proxy-error.md)

## References

- [nginx client_max_body_size](https://nginx.org/en/docs/http/ngx_http_core_module.html#client_max_body_size)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`grafana` · `proxy` · `http` · `dashboard` · `production`
