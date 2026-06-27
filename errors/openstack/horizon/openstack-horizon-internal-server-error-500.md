---
title: "OpenStack Horizon Internal Server Error (HTTP 500)"
slug: openstack-horizon-internal-server-error-500
technologies: [openstack, horizon]
severity: high
tags: [openstack, horizon, dashboard, 500, django, production]
related: [openstack-keystone-401-unauthorized, openstack-keystone-could-not-find-service]
last_reviewed: 2026-06-27
---

# OpenStack Horizon Internal Server Error (HTTP 500)

## Error Message

```text
Internal Server Error
The server encountered an internal error or misconfiguration and was unable to
complete your request.
```

```text
[wsgi:error] [pid 22418] Internal Server Error: /horizon/auth/login/
ImportError: No module named 'openstack_dashboard.local.local_settings'
DisallowedHost at /  Invalid HTTP_HOST header: 'dashboard.example.com'. \
You may need to add 'dashboard.example.com' to ALLOWED_HOSTS.
```

## Description

Horizon (a Django app served under Apache/mod_wsgi or uWSGI) returned an HTTP 500
instead of rendering a page. With `DEBUG = False` in production the browser shows
only a generic error; the actual Python traceback is written to the web server
error log. The cause is almost always a configuration or environment problem in
the dashboard host — a bad `local_settings`, a missing static/cache backend, an
unreachable Keystone, or a Django setting like `ALLOWED_HOSTS`.

## Technologies

- openstack (horizon / openstack_dashboard, Django, Apache mod_wsgi or uWSGI)

## Severity

**high** — the web UI is unusable for all tenants and operators. The API and CLI
remain functional, so it is a UI outage rather than a control-plane outage.

## Common Causes

1. `ALLOWED_HOSTS` does not include the hostname/IP the browser used
   (`DisallowedHost`), so Django 500s on every request.
2. `local_settings.py` is missing, has a syntax/import error, or references an
   undefined `OPENSTACK_HOST`/`OPENSTACK_KEYSTONE_URL`.
3. The session/cache backend is unreachable — Memcached down, or
   `CACHES`/`SESSION_ENGINE` misconfigured.
4. Static files were never collected/compressed, or their directory is not
   writable, breaking page render.
5. Keystone is unreachable from the Horizon host, so login/catalog calls raise.
6. Wrong file permissions or SELinux/AppArmor denial on the WSGI process.

## Root Cause Analysis

Apache/mod_wsgi loads the Django `openstack_dashboard` application using the
settings module. If settings import fails, or a request violates a Django guard
(`ALLOWED_HOSTS`), or a downstream dependency (Memcached, Keystone) raises during
view processing, Django returns 500 and logs the traceback. Because `DEBUG` is
off in production, the only way to find the true cause is the web server error
log. The traceback's final exception line names the precise subsystem at fault.

## Diagnostic Commands

```bash
# The real traceback lives here (Apache); pick your distro's path
journalctl -u apache2 --since "15 min ago" | grep -iE "error|traceback|horizon"
tail -n 100 /var/log/apache2/error.log        # or /var/log/httpd/error_log

# uWSGI deployments
journalctl -u horizon --since "15 min ago"

# Is Memcached (session/cache backend) reachable?
echo stats | timeout 2 nc 127.0.0.1 11211 | head

# Can the Horizon host reach Keystone?
curl -s -o /dev/null -w "%{http_code}\n" http://<keystone-host>:5000/v3

# Confirm settings load cleanly (read-only check)
python3 -c "import openstack_dashboard.settings" 2>&1 | head

# Verify the configured ALLOWED_HOSTS and OPENSTACK_HOST
grep -nE "ALLOWED_HOSTS|OPENSTACK_HOST|OPENSTACK_KEYSTONE_URL" \
  /etc/openstack-dashboard/local_settings.py
```

## Expected Results

```text
# Smoking-gun traceback lines:
DisallowedHost: Invalid HTTP_HOST header: 'dashboard.example.com'.
  -> ALLOWED_HOSTS is too narrow.

pylibmc.ConnectionError: error 3 from memcached_get
  -> Memcached / cache backend is down.

ConnectionError: HTTPConnectionPool(host='keystone', port=5000) Max retries exceeded
  -> Keystone unreachable from Horizon.

# Healthy: settings import returns nothing, nc to memcached prints stats,
# and the Keystone curl returns 200/300.
```

## Resolution

1. For `DisallowedHost`, add the hostname(s) and restart the web server:
   ```python
   ALLOWED_HOSTS = ['dashboard.example.com', 'localhost', '127.0.0.1']
   ```
   ```bash
   systemctl restart apache2     # or: systemctl restart horizon
   ```
2. Fix `local_settings.py` syntax/imports; ensure `OPENSTACK_HOST` and
   `OPENSTACK_KEYSTONE_URL` point at a reachable Keystone.
3. Restore the cache/session backend (start Memcached) or correct `CACHES`.
4. Recollect and compress static assets, then fix ownership:
   ```bash
   python3 manage.py collectstatic --noinput
   python3 manage.py compress --force
   ```
5. Resolve permission/SELinux denials on the WSGI user.

## Validation

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://<horizon-host>/auth/login/
# Expect: 200 (login page renders), not 500
```

## Prevention

- Keep `DEBUG = False` in production but ship error logging to a central place so
  500 tracebacks are searchable.
- Manage `local_settings.py` with config management and validate import in CI.
- Monitor Memcached and Keystone reachability from each Horizon node.
- Run `collectstatic`/`compress` as part of deployment, not by hand.

## Related Errors

- [OpenStack Keystone 401 Unauthorized](../keystone/openstack-keystone-401-unauthorized.md)
- [OpenStack Keystone Could Not Find Service](../keystone/openstack-keystone-could-not-find-service.md)

## References

- [Horizon deployment & settings](https://docs.openstack.org/horizon/latest/admin/index.html)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`openstack` · `horizon` · `dashboard` · `500` · `django` · `production`
