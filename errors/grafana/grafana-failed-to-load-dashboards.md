---
title: "Grafana Failed to Load Dashboards"
slug: grafana-failed-to-load-dashboards
technologies: [grafana]
severity: medium
tags: [grafana, dashboard, provisioning, schema, production]
related: [grafana-dashboard-not-found, grafana-database-is-locked-sqlite]
last_reviewed: 2026-06-27
---

# Grafana Failed to Load Dashboards

## Error Message

```text
Failed to load dashboards
```

```text
t=2026-06-24T07:22:18+0000 lvl=eror msg="failed to load dashboard from " logger=provisioning.dashboard file=/etc/grafana/provisioning/dashboards/api.json error="invalid character '}' looking for beginning of object key string"
```

```text
t=2026-06-24T07:22:18+0000 lvl=eror msg="failed to provision dashboards" error="Dashboard title cannot be empty"
```

## Description

**Failed to load dashboards** appears in the UI (dashboard list) or as
provisioning errors in the server log when Grafana cannot read or apply one or
more dashboards. The two common flavors are: (1) the browser failed to fetch the
dashboard list from the API (auth/DB/connectivity), or (2) **provisioning**
failed to apply file-based dashboards because the JSON is invalid, the title is
empty, or two dashboards share a UID. The detail is always in the
`provisioning.dashboard` logger.

## Technologies

- grafana (provisioning / dashboard service)

## Severity

**medium** — affected dashboards do not appear or do not update; unaffected
dashboards and the rest of Grafana keep working. It is higher when an entire
provisioning folder of dashboards fails to load.

## Common Causes

1. Malformed dashboard JSON in a provisioning file (trailing comma, bad object
   key, truncated file).
2. Missing required fields — empty `title`, or a provider `path` that does not
   exist / is unreadable by the grafana user.
3. **Duplicate UID** across two provisioned files; Grafana refuses the conflict.
4. The dashboard JSON's `schemaVersion`/structure is incompatible with the
   running Grafana version.
5. The UI list fails to load because the API call is unauthorized or the backend
   DB is unavailable/locked.

## Root Cause Analysis

On startup and on a reload interval, the provisioning service walks each
configured dashboards provider path, parses every JSON file, and upserts it into
the dashboard store by UID. A JSON parse error, an empty title, or a UID
collision aborts that file's load and is logged — the dashboard never reaches the
store, so links and lists 404 or show stale versions. For the *UI* "Failed to
load dashboards" toast, the cause is instead the `/api/search` call failing
(expired session/token, or a DB problem such as a SQLite lock).

## Diagnostic Commands

```bash
# Provisioning load errors (JSON, title, duplicate UID)
journalctl -u grafana-server --since "20 min ago" | grep -i "provisioning\|failed to load dashboard\|provision dashboards"

# Validate provisioned JSON files locally (read-only)
for f in /etc/grafana/provisioning/dashboards/*.json; do echo "== $f"; jq -e . "$f" >/dev/null && echo OK || echo BAD; done

# Detect duplicate UIDs across provisioned files
grep -rhoE '"uid"\s*:\s*"[^"]+"' /etc/grafana/provisioning/dashboards/ | sort | uniq -d

# Does the UI list API succeed for the current token? (admin)
curl -s -o /dev/null -w "%{http_code}\n" -H "Authorization: Bearer $GRAFANA_TOKEN" \
  "http://localhost:3000/api/search?type=dash-db"

# Provider paths configured
cat /etc/grafana/provisioning/dashboards/*.yaml
```

## Expected Results

```text
error="invalid character '}' looking for beginning of object key string"   # bad JSON
error="Dashboard title cannot be empty"                                     # missing title
error="dashboard with the same uid already exists"                          # duplicate UID
```

`jq -e .` printing `BAD` pinpoints the unparseable file. The `uniq -d` line
prints any UID used by more than one file. A `200` from `/api/search` means the
UI-list path is healthy and the problem is provisioning, not connectivity.

## Resolution

1. Fix the JSON reported in the log (`jq` the offending file to find the syntax
   error), and ensure every dashboard has a non-empty `title`.
2. Resolve duplicate UIDs — give each provisioned dashboard a unique, stable
   `uid`.
3. Make the provider `path` exist and be readable by the `grafana` user:

   ```bash
   sudo chown -R grafana:grafana /etc/grafana/provisioning/dashboards
   ```
4. If the JSON targets an incompatible `schemaVersion`, re-export it from a
   matching Grafana version.
5. If the *UI list* fails (200 not returned), fix the session/token or the
   backend DB (see the SQLite-locked error) before touching provisioning.

## Validation

```bash
# Reload provisioning, then confirm clean logs and that the dashboard resolves
sudo systemctl restart grafana-server
journalctl -u grafana-server --since "2 min ago" | grep -i "failed to load dashboard" || echo "no provisioning errors"
```

## Prevention

- Validate dashboard JSON and check for duplicate UIDs in CI before deploy.
- Pin a unique, stable `uid` per dashboard and export from the target Grafana
  version.
- Keep provisioning paths owned/readable by the grafana service user.

## Related Errors

- [Grafana Dashboard Not Found](./grafana-dashboard-not-found.md)
- [Grafana Database Is Locked (SQLite)](./grafana-database-is-locked-sqlite.md)

## References

- [Grafana provisioning dashboards](https://grafana.com/docs/grafana/latest/administration/provisioning/#dashboards)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`grafana` · `dashboard` · `provisioning` · `schema` · `production`
