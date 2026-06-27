---
title: "OpenStack Keystone Application Credentials Cannot Request a Scope"
slug: openstack-keystone-application-credentials-cannot-request-scope
technologies: [openstack, keystone]
severity: medium
tags: [openstack, keystone, application-credentials, scope, authentication, production]
related: [openstack-keystone-401-unauthorized]
last_reviewed: 2026-06-27
---

# OpenStack Keystone Application Credentials Cannot Request a Scope

## Error Message

```text
Application credentials cannot request a scope. (HTTP 400) (Request-ID: req-...)
```

```text
keystone[1203]: WARNING keystone.server.flask.application [req-...] \
Application credentials cannot be used to request a scope; the scope is inherited \
from the application credential itself.
```

## Description

This error appears when a client authenticates with an **application credential**
but *also* sends an explicit scope (project, domain, or system) in the auth
request. By design, an application credential is permanently bound to the project
and roles that existed when it was created — its scope is fixed and cannot be
overridden at token-request time. Keystone therefore rejects any auth body that
combines the `application_credential` identity method with a `scope` block.

## Technologies

- openstack (keystone identity v3, application credential auth plugin)

## Severity

**medium** — automation, CI pipelines, or service integrations using app
credentials fail to authenticate. Human operators with passwords are unaffected,
so it is typically a broken job rather than a cloud-wide outage.

## Common Causes

1. The environment/`clouds.yaml` sets both app-credential variables **and**
   `OS_PROJECT_NAME`/`OS_PROJECT_ID` (or `--os-project-name`), so the client adds
   a scope block.
2. Mixing auth types — `OS_AUTH_TYPE=v3applicationcredential` left alongside
   leftover password+project variables from a previous `openrc`.
3. A wrapper/SDK explicitly passing `project_id`/`project_name` when constructing
   the app-credential session.
4. Copy-pasting a password-based `clouds.yaml` cloud entry and only swapping in
   the app-credential id/secret without removing the project scope keys.

## Root Cause Analysis

When you create an application credential, Keystone records the project and role
set as immutable attributes of that credential. At auth time the
`application_credential` method derives the scope *from the stored credential*,
not from the request. If the request also carries a `scope`, Keystone cannot
reconcile a caller-supplied scope with the credential's intrinsic scope, so it
fails fast with HTTP 400 rather than silently ignoring one of them. The practical
trigger is almost always stray project/domain variables in the environment.

## Diagnostic Commands

```bash
# Inspect exactly which OS_* variables are set; look for BOTH app-cred and project
env | grep -E "^OS_"

# Confirm the auth type the client will use
echo "$OS_AUTH_TYPE"

# Inspect the clouds.yaml cloud entry being used
openstack --os-cloud <cloud> configuration show 2>/dev/null | grep -iE "auth_type|application_credential|project"

# Keystone log showing the rejected scope
journalctl -u devstack@keystone --since "10 min ago" | grep -i "cannot request a scope"

# Verify the credential itself and its bound project
openstack application credential show <app-cred-name> -c project_id -f value
```

## Expected Results

```text
# The offending combination — app-cred AND a project scope present:
OS_AUTH_TYPE=v3applicationcredential
OS_APPLICATION_CREDENTIAL_ID=4d2...
OS_APPLICATION_CREDENTIAL_SECRET=********
OS_PROJECT_NAME=myproject          # <-- must be removed
OS_PROJECT_DOMAIN_NAME=Default     # <-- must be removed

# Healthy app-cred environment has NO OS_PROJECT_* / OS_*DOMAIN* scope keys.
```

## Resolution

1. Unset all scope variables so only the app-credential identity remains:
   ```bash
   unset OS_PROJECT_NAME OS_PROJECT_ID OS_PROJECT_DOMAIN_NAME \
         OS_PROJECT_DOMAIN_ID OS_DOMAIN_NAME OS_DOMAIN_ID \
         OS_USERNAME OS_USER_DOMAIN_NAME OS_PASSWORD
   export OS_AUTH_TYPE=v3applicationcredential
   ```
2. In `clouds.yaml`, use a clean app-credential auth block — no `project_name`,
   `project_id`, or domain keys:
   ```yaml
   clouds:
     myapp:
       auth_type: v3applicationcredential
       auth:
         auth_url: https://keystone.example.com:5000/v3
         application_credential_id: 4d2...
         application_credential_secret: ********
   ```
3. Regenerate the openrc from Horizon as an *application credential* RC file
   (not a password RC) so the correct variables are emitted.

## Validation

```bash
openstack token issue -c project_id -f value
# Returns the credential's bound project id, no HTTP 400.
```

## Prevention

- Keep app-credential `clouds.yaml` entries separate from password entries; never
  edit a password entry into an app-credential one in place.
- In CI, start each job from a clean environment and export only the
  app-credential variables.
- Document that app credentials carry their own immutable scope — never pass
  `--os-project-*` with them.

## Related Errors

- [OpenStack Keystone 401 Unauthorized](./openstack-keystone-401-unauthorized.md)

## References

- [Keystone application credentials](https://docs.openstack.org/keystone/latest/user/application_credentials.html)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`openstack` · `keystone` · `application-credentials` · `scope` · `authentication` · `production`
