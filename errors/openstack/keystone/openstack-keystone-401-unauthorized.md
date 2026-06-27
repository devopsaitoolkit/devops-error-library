---
title: "OpenStack Keystone 401 Unauthorized"
slug: openstack-keystone-401-unauthorized
technologies: [openstack, keystone]
severity: high
tags: [openstack, keystone, authentication, 401, token, production]
related: [openstack-keystone-could-not-find-service, openstack-keystone-application-credentials-cannot-request-scope]
last_reviewed: 2026-06-27
---

# OpenStack Keystone 401 Unauthorized

## Error Message

```text
The request you have made requires authentication. (HTTP 401) (Request-ID: req-...)
```

```text
$ openstack server list
Failed to validate token (HTTP 401)
keystone[1203]: WARNING keystone.common.wsgi [req-...] Authorization failed. \
The request you have made requires authentication. from 10.0.0.5
```

## Description

Keystone rejected the request because it could not authenticate the caller or
validate the supplied token. A 401 is returned both at the `auth/tokens` endpoint
(wrong credentials) and at every other OpenStack service when the token sent in
`X-Auth-Token` is missing, malformed, expired, or revoked. Because every API call
depends on a valid Keystone token, a systemic 401 effectively locks operators and
services out of the cloud.

## Technologies

- openstack (keystone, keystonemiddleware on every service endpoint)

## Severity

**high** — if it affects an operator's credentials it blocks all CLI/API work;
if it affects a service user (nova, neutron, cinder) it breaks cross-service
calls and can cascade into failed operations cloud-wide.

## Common Causes

1. Wrong or expired credentials — bad password, wrong `OS_USERNAME`, or a stale
   `clouds.yaml`/RC file pointing at the wrong project or domain.
2. Expired token — the cached token outlived `[token] expiration` (default 3600s).
3. Clock skew between API nodes so Fernet token timestamps validate as expired.
4. Missing or rotated Fernet/credential keys, so previously issued tokens can no
   longer be decrypted/validated.
5. Disabled user, project, or domain; or a deleted/disabled service account.
6. A `service_token` mismatch in keystonemiddleware (`[keystone_authtoken]`
   `username`/`password`/`project_name` wrong on a downstream service).

## Root Cause Analysis

There are two distinct 401 paths. At the token endpoint, Keystone hashes the
presented secret and compares it to the stored credential; a mismatch yields 401.
On every other API, `keystonemiddleware` extracts `X-Auth-Token` and validates it
against Keystone (or locally for Fernet). Validation fails if the token is
expired, was issued with now-rotated Fernet keys, or was revoked. Clock skew
makes valid tokens look expired because Fernet encodes an absolute timestamp that
each node compares to its own wall clock.

## Diagnostic Commands

```bash
# Reproduce auth in isolation and see the precise failure
openstack token issue

# Inspect the environment actually in use
env | grep -E "^OS_"

# Keystone auth failures with request IDs
journalctl -u devstack@keystone --since "15 min ago" | grep -iE "401|Authorization failed"

# Is the user/project/domain enabled?
openstack user show <user> -c enabled -f value
openstack project show <project> -c enabled -f value

# Check clock skew across control-plane nodes
chronyc tracking    # or: timedatectl

# Raw token validation against the identity endpoint
curl -s -o /dev/null -w "%{http_code}\n" -H "X-Subject-Token: $TOKEN" \
  -H "X-Auth-Token: $TOKEN" http://<keystone>:5000/v3/auth/tokens
```

## Expected Results

```text
$ openstack token issue
The request you have made requires authentication. (HTTP 401)

# Environment reveals the mismatch, e.g. wrong project/domain:
OS_PROJECT_NAME=admin
OS_USER_DOMAIN_NAME=Default
OS_PASSWORD=...            # stale

# Skew that breaks Fernet:
$ chronyc tracking
System time : 47.30 seconds slow of NTP time   # > token leeway

# Healthy: 'token issue' returns a token; clock skew is sub-second.
```

## Resolution

1. Re-source correct credentials and confirm the project/domain scope:
   ```bash
   source ./admin-openrc.sh
   openstack token issue        # must succeed before anything else
   ```
2. Re-enable a disabled identity if that is the cause:
   ```bash
   openstack user set --enable <user>
   openstack project set --enable <project>
   ```
3. Fix clock skew — start/sync `chronyd`/NTP on all control nodes so Fernet
   timestamps agree.
4. If Fernet keys were mis-rotated, restore the key repository and ensure all
   keystone nodes share the same `/etc/keystone/fernet-keys` and
   `credential-keys`, then restart keystone.
5. For service-to-service 401s, correct `[keystone_authtoken]` credentials in the
   downstream service config and restart it.

## Validation

```bash
openstack token issue -c id -f value     # returns a token
openstack server list                    # returns without 401
```

## Prevention

- Keep `chronyd`/NTP running on every control node and alert on skew.
- Use `clouds.yaml` / Vault for credentials instead of hand-edited RC files.
- Synchronize Fernet key rotation across all keystone nodes (shared repo or
  config management); never rotate past the configured `max_active_keys`.
- Alert on spikes in Keystone 401s to catch a bad rotation or disabled account.

## Related Errors

- [OpenStack Keystone Could Not Find Service](./openstack-keystone-could-not-find-service.md)
- [OpenStack Keystone Application Credentials Cannot Request Scope](./openstack-keystone-application-credentials-cannot-request-scope.md)

## References

- [Keystone Fernet tokens](https://docs.openstack.org/keystone/latest/admin/fernet-token-faq.html)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`openstack` · `keystone` · `authentication` · `401` · `token` · `production`
