---
title: "GitLab CI — Registry 401 Unauthorized on Image Pull/Push"
slug: gitlab-registry-401-unauthorized
technologies: [gitlab]
severity: high
tags: [gitlab, ci, registry, authentication, production]
related: [gitlab-could-not-read-username-ci-job-token, gitlab-not-allowed-to-download-code]
last_reviewed: 2026-06-27
---

# GitLab CI — Registry 401 Unauthorized on Image Pull/Push

## Error Message

```text
$ docker pull registry.gitlab.com/acme/app/base:latest
Error response from daemon: Head "https://registry.gitlab.com/v2/acme/app/base/manifests/latest": unauthorized: HTTP Basic: Access denied
```

```text
denied: requested access to the resource is denied
unauthorized: authentication required
```

## Description

A `401 unauthorized` from the GitLab Container Registry means the credentials the
job presented were rejected (or absent) when pulling or pushing an image. In CI
this usually surfaces while pulling a private base image for the job, or while
pushing a built image with `docker push`. The registry requires a valid token
scoped for the target repository; the default `$CI_JOB_TOKEN` works for the
*current* project but is restricted for cross-project access.

## Technologies

- gitlab (Container Registry, CI authentication)

## Severity

**high** — builds that depend on private images cannot start, and release
pipelines that push images fail, blocking deployment.

## Common Causes

1. The job never logged in to the registry, or used wrong credentials in
   `docker login`.
2. `$CI_JOB_TOKEN` is being used to access a **different** project's registry and
   that project does not allow this project in its **CI/CD job token allowlist**.
3. A Personal/Project/Deploy token used for login is **expired, revoked, or lacks
   `read_registry`/`write_registry` scope**.
4. The image path is wrong (typo in group/project/path), so auth is evaluated
   against a repo the token cannot access.
5. Registry login happened in a different shell/layer than the pull/push (DinD
   credential not shared).

## Root Cause Analysis

The GitLab Registry uses token-based auth: the Docker client requests a bearer
token from GitLab's auth service scoped to `repository:<path>:pull` (and/or
`push`). GitLab grants the token only if the presented credential has rights to
that path. `$CI_JOB_TOKEN` is automatically scoped to the running pipeline's
project; accessing another project's registry requires that project to allowlist
yours (Settings > CI/CD > Token Access). A revoked token or insufficient scope
yields no grant, and the registry responds `401 unauthorized` / `denied`.

## Diagnostic Commands

```bash
# Confirm the CI variables the job has for registry auth (names only, never echo secrets to public logs)
grep -nE 'CI_REGISTRY|CI_REGISTRY_IMAGE|docker login' .gitlab-ci.yml

# Inspect how the job authenticates
grep -nE 'docker login|DOCKER_AUTH_CONFIG|before_script' .gitlab-ci.yml

# Verify a token's scope via the API (read-only)
curl -s --header "PRIVATE-TOKEN: $GL_TOKEN" "https://gitlab.com/api/v4/personal_access_tokens/self" \
  | tr ',' '\n' | grep -iE 'scopes|active|expires'

# Check the cross-project token allowlist setting for the target project
curl -s --header "PRIVATE-TOKEN: $GL_TOKEN" \
  "https://gitlab.com/api/v4/projects/<target-id>/job_token_scope/allowlist"
```

## Expected Results

```text
# Wrong/expired token: any pull returns
unauthorized: HTTP Basic: Access denied

# A correctly scoped login succeeds:
$ docker login -u "$CI_REGISTRY_USER" -p "$CI_REGISTRY_PASSWORD" "$CI_REGISTRY"
Login Succeeded
```

## Resolution

1. For the **current project's** registry, log in with the built-in variables:

   ```yaml
   before_script:
     - echo "$CI_REGISTRY_PASSWORD" | docker login -u "$CI_REGISTRY_USER" --password-stdin "$CI_REGISTRY"
   ```
2. For **cross-project** access via `$CI_JOB_TOKEN`, add your project to the target
   project's **CI/CD > Job token allowlist** (and grant the right access level).
3. If using a Deploy/Project Access Token, ensure it is active and has
   `read_registry` (pull) and/or `write_registry` (push) scope; rotate if expired.
4. Double-check the image path matches `$CI_REGISTRY_IMAGE/...` exactly.

## Validation

```bash
docker login -u "$CI_REGISTRY_USER" -p "$CI_REGISTRY_PASSWORD" "$CI_REGISTRY"   # Login Succeeded
docker pull "$CI_REGISTRY_IMAGE/base:latest"                                    # pulls without 401
```

## Prevention

- Prefer `$CI_REGISTRY_USER`/`$CI_REGISTRY_PASSWORD` (auto-scoped to the project)
  over hand-managed tokens.
- Track token expiry; rotate Deploy/PATs before they lapse.
- Document and review the job-token allowlist when projects depend on each other.

## Related Errors

- [GitLab — Could Not Read Username (CI Job Token)](./gitlab-could-not-read-username-ci-job-token.md)
- [GitLab — Not Allowed to Download Code](./gitlab-not-allowed-to-download-code.md)

## References

- [GitLab Container Registry: Authenticate](https://docs.gitlab.com/ee/user/packages/container_registry/authenticate_with_container_registry.html)
- [GitLab: CI/CD job token](https://docs.gitlab.com/ee/ci/jobs/ci_job_token.html)

## Tags

`gitlab` · `ci` · `registry` · `authentication` · `production`
