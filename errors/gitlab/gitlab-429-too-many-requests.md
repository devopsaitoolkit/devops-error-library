---
title: "GitLab CI — 429 Too Many Requests (Rate Limited)"
slug: gitlab-429-too-many-requests
technologies: [gitlab]
severity: medium
tags: [gitlab, ci, rate-limit, registry, production]
related: [gitlab-registry-401-unauthorized, gitlab-job-failed-exit-code-1]
last_reviewed: 2026-06-27
---

# GitLab CI — 429 Too Many Requests (Rate Limited)

## Error Message

```text
$ docker pull node:20
Error response from daemon: toomanyrequests: You have reached your pull rate limit.

$ git fetch origin
error: RPC failed; HTTP 429 curl 22 The requested URL returned error: 429
fatal: expected flush after ref listing
```

```text
WARNING: Retrying (attempt 1/3) after 429 Too Many Requests
Retry-After: 60
```

## Description

A `429 Too Many Requests` response means a server is throttling the job for
exceeding a rate limit. In GitLab CI this comes from one of several places: the
GitLab API/Git endpoints (instance rate limits), the GitLab Container Registry, or
an upstream like Docker Hub's anonymous pull limit. The job typically fails or
retries with a `Retry-After` hint. The fix depends on which endpoint is limiting
you — authenticate, cache/mirror, or reduce request volume.

## Technologies

- gitlab (API/registry rate limiting), upstream registries

## Severity

**medium** — intermittent failures and pipeline retries slow delivery; it becomes
**high** during peak load when many pipelines are throttled simultaneously.

## Common Causes

1. **Docker Hub anonymous pull limit** — many CI jobs pulling public images from
   the same egress IP exhaust the unauthenticated quota.
2. GitLab.com or self-managed **application rate limits** (raw endpoints,
   unauthenticated API, Git over HTTPS) tripped by tight loops or fan-out jobs.
3. GitLab **Container Registry** request limits hit by parallel pulls/pushes.
4. A polling script (`while curl ... /pipelines`) hammering the API.
5. Shared NAT IP across many runners aggregating into one limited identity.

## Root Cause Analysis

Rate limiting is per-identity and/or per-IP over a sliding window. When the count
exceeds the threshold, the server short-circuits the request and returns `429`,
often with a `Retry-After` header telling clients how long to back off.
Authenticated requests usually get a higher (or unlimited) quota than anonymous
ones, which is why pulling `node:20` anonymously from Docker Hub fails while an
authenticated or GitLab-mirrored pull succeeds. Identifying the *which-host*
returning 429 is the key diagnostic step.

## Diagnostic Commands

```bash
# Which host/endpoint returned 429? Inspect the job log line just above the error.
grep -nE 'image:|docker pull|FROM |registry|curl ' .gitlab-ci.yml

# Check Docker Hub remaining pull quota for the current IP (read-only)
TOKEN=$(curl -s "https://auth.docker.io/token?service=registry.docker.io&scope=repository:ratelimitpreview/test:pull" | grep -o '"token":"[^"]*' | cut -d'"' -f4)
curl -sI -H "Authorization: Bearer $TOKEN" https://registry-1.docker.io/v2/ratelimitpreview/test/manifests/latest | grep -i ratelimit

# See the Retry-After / RateLimit headers GitLab returns
curl -sI --header "PRIVATE-TOKEN: $GL_TOKEN" "https://gitlab.com/api/v4/projects/<id>/pipelines" | grep -iE 'ratelimit|retry-after'

# Egress IP that all these runners share
curl -s https://ifconfig.me
```

## Expected Results

```text
# Docker Hub near/over limit:
ratelimit-limit: 100;w=21600
ratelimit-remaining: 0;w=21600     <- exhausted

# GitLab throttling:
RateLimit-Remaining: 0
Retry-After: 60
```

## Resolution

1. **Authenticate** registry pulls so you get the higher quota (and use GitLab's
   Dependency Proxy to cache upstream images):

   ```yaml
   default:
     image: ${CI_DEPENDENCY_PROXY_GROUP_IMAGE_PREFIX}/node:20
   before_script:
     - docker login -u "$CI_DEPENDENCY_PROXY_USER" -p "$CI_DEPENDENCY_PROXY_PASSWORD" "$CI_DEPENDENCY_PROXY_SERVER"
   ```
2. Add retry/back-off for transient 429s:

   ```yaml
   build:
     retry:
       max: 2
       when: [runner_system_failure, api_failure]
   ```
3. Reduce request volume: cache dependencies, avoid tight API polling, and respect
   `Retry-After` in custom scripts.
4. For self-managed GitLab, raise the relevant Admin > Settings > Network rate
   limits if they are too tight for your runner fleet.

## Validation

```bash
# After enabling the Dependency Proxy / auth, re-pull:
docker pull "${CI_DEPENDENCY_PROXY_GROUP_IMAGE_PREFIX}/node:20"   # succeeds, no 429
```

## Prevention

- Route all upstream image pulls through GitLab's Dependency Proxy or a private
  mirror.
- Always authenticate to registries in CI to avoid anonymous limits.
- Replace polling loops with webhooks or pipeline `needs:`; honor `Retry-After`.

## Related Errors

- [GitLab CI — Registry 401 Unauthorized](./gitlab-registry-401-unauthorized.md)
- [GitLab CI Job Failed — Exit Code 1](./gitlab-job-failed-exit-code-1.md)

## References

- [GitLab: Dependency Proxy](https://docs.gitlab.com/ee/user/packages/dependency_proxy/)
- [GitLab: Rate limits](https://docs.gitlab.com/ee/security/rate_limits.html)

## Tags

`gitlab` · `ci` · `rate-limit` · `registry` · `production`
