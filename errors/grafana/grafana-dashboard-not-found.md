---
title: "Grafana Dashboard Not Found"
slug: grafana-dashboard-not-found
technologies: [grafana]
severity: low
tags: [grafana, dashboard, provisioning, links, production]
related: [grafana-failed-to-load-dashboards, grafana-invalid-username-or-password]
last_reviewed: 2026-06-27
---

# Grafana Dashboard Not Found

## Error Message

```text
Dashboard not found
```

```text
{"message":"Dashboard not found","status":"not-found","traceID":""}
```

```text
t=2026-06-24T11:05:33+0000 lvl=info msg="Request Completed" logger=context status=404 path=/api/dashboards/uid/abc123 method=GET
```

## Description

Grafana returns **Dashboard not found** (HTTP 404) when a request references a
dashboard UID/slug that no longer exists, was moved/renamed, lives in a different
organization, or is not visible to the current user's permissions. It surfaces
when following a stale bookmark/link, after a dashboard was deleted or re-imported
with a new UID, or when a provisioned dashboard failed to load. The lookup is by
**UID** (stable) — slug-based URLs are not.

## Technologies

- grafana (dashboard service / API)

## Severity

**low** — a single dashboard is inaccessible; Grafana, data sources, and other
dashboards are unaffected. It rises in importance if the missing board is a
linked runbook/incident dashboard.

## Common Causes

1. Stale link/bookmark to a dashboard that was deleted or whose UID changed on
   re-import.
2. The dashboard belongs to a different **organization** than the one the user is
   currently in.
3. The user lacks **View** permission on the dashboard or its folder (404 is
   returned instead of 403 in some flows).
4. A provisioned dashboard failed to apply (bad JSON / duplicate UID), so it
   never got created.
5. Slug-based URL after a title change — Grafana resolves by UID, and the old
   slug path no longer maps.

## Root Cause Analysis

Grafana resolves dashboards primarily by UID in the `dashboard` table for the
active org. If no row matches the UID (deleted, re-imported with a new UID, or in
another org), or RBAC filters it out for the user, the dashboard service returns
404. For provisioned dashboards, a load failure means the row was never inserted,
so every link to it 404s. Confirming the UID's existence and org/permissions
separates "truly gone" from "hidden by org/permission".

## Diagnostic Commands

```bash
# Does the UID exist (and in which org/folder)? (admin, read-only)
curl -s -H "Authorization: Bearer $GRAFANA_TOKEN" \
  "http://localhost:3000/api/dashboards/uid/abc123" | jq '{title: .dashboard.title, uid: .dashboard.uid}'

# Search by title to find the current UID if it changed
curl -s -H "Authorization: Bearer $GRAFANA_TOKEN" \
  "http://localhost:3000/api/search?query=API%20Overview&type=dash-db" | jq '.[] | {title, uid, folderTitle}'

# Provisioning load errors (dashboards that never got created)
journalctl -u grafana-server --since "30 min ago" | grep -i "provisioning\|dashboard\|404"

# Read-only DB check across orgs
sqlite3 -readonly /var/lib/grafana/grafana.db \
  "SELECT org_id, uid, title FROM dashboard WHERE uid='abc123';"
```

## Expected Results

```text
{"message":"Dashboard not found","status":"not-found"}   # UID truly absent for this org/user
```

If `/api/search` finds the title under a different UID, the dashboard was
re-imported — update links to the new UID. If the SQLite row exists under a
different `org_id`, the user is simply in the wrong org.

## Resolution

1. Use `/api/search` (or the UI search) to find the dashboard's **current UID**
   and update the stale link/bookmark.
2. If it lives in another org, switch orgs (top-left org switcher) or move the
   dashboard.
3. Grant the user/team **View** on the dashboard's folder if it is a permission
   issue.
4. For provisioned dashboards, fix the JSON/duplicate-UID error reported in the
   logs and let provisioning re-apply.

## Validation

```bash
# The (corrected) UID now resolves
curl -s -o /dev/null -w "%{http_code}\n" -H "Authorization: Bearer $GRAFANA_TOKEN" \
  "http://localhost:3000/api/dashboards/uid/<correct-uid>"   # Expect: 200
```

## Prevention

- Pin a stable `uid` in dashboard JSON so re-imports keep the same URL.
- Link to dashboards by UID, not slug.
- Add a CI check that validates provisioned dashboard JSON and unique UIDs before
  deploy.

## Related Errors

- [Grafana Failed to Load Dashboards](./grafana-failed-to-load-dashboards.md)
- [Grafana Invalid Username or Password](./grafana-invalid-username-or-password.md)

## References

- [Grafana dashboard API](https://grafana.com/docs/grafana/latest/developers/http_api/dashboard/)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`grafana` · `dashboard` · `provisioning` · `links` · `production`
