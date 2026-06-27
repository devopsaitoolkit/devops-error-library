---
title: "Docker Pull Access Denied"
slug: docker-pull-access-denied
technologies: [docker]
severity: medium
tags: [docker, registry, authentication, pull, production]
related: [docker-manifest-unknown, docker-image-pull-failed]
last_reviewed: 2026-06-27
---

# Docker Pull Access Denied

## Error Message

```text
Error response from daemon: pull access denied for myorg/private-api, repository does not exist or may require 'docker login': denied: requested access to the resource is denied
```

```text
denied: requested access to the resource is denied
```

## Description

The registry returned HTTP `403 denied` for the pull. Docker phrases it
ambiguously on purpose: to an unauthenticated caller, a **private** repository and
a **non-existent** repository are indistinguishable, so the registry won't reveal
which it is. In practice this means the daemon either has no credentials for the
registry, has the wrong ones, or the repository name/path is wrong.

## Technologies

- docker (registry client, credential store, `docker login`)

## Severity

**medium** — deployments and CI pulls that depend on the image fail, but the
fix is a credentials or naming correction rather than an infrastructure outage.

## Common Causes

1. Not logged in to the registry hosting a private image (`docker login` missing).
2. Logged in, but the token/password is expired or for the wrong account.
3. The repository path is wrong (typo, missing org/namespace, wrong registry host).
4. The authenticated identity lacks `pull` permission on that repository.
5. On a CI runner, credentials weren't injected into the daemon's config.

## Root Cause Analysis

For a private repo, the registry first requires an auth token scoped to that
repository. The daemon obtains it using credentials from
`~/.docker/config.json` (or a credential helper). If those are absent, expired, or
authorize a principal without read access, the token request — or the subsequent
manifest fetch — returns `denied`. The same `denied` is returned for a repository
that doesn't exist, to avoid leaking which private names are valid.

## Diagnostic Commands

```bash
# Which registries the daemon has stored credentials for
cat ~/.docker/config.json | grep -A3 '"auths"'

# Confirm the exact image reference you're pulling
echo "ghcr.io/myorg/private-api:1.4.2"

# Re-auth and test (will prompt; read-only check of access)
docker login ghcr.io

# Does the manifest resolve once authenticated? (read-only)
docker manifest inspect ghcr.io/myorg/private-api:1.4.2
```

## Expected Results

```text
$ cat ~/.docker/config.json
{ "auths": {} }                 # no stored credentials -> denied for private repos

# After a correct login, manifest inspect succeeds:
$ docker manifest inspect ghcr.io/myorg/private-api:1.4.2
{ "schemaVersion": 2, "mediaType": "application/vnd.oci.image.index.v1+json", ... }
```

## Resolution

1. Authenticate to the correct registry host:

   ```bash
   docker login ghcr.io        # or registry.example.com, docker.io, etc.
   ```
2. Verify the full reference includes the registry, namespace, repo, and tag, and
   correct any typo: `ghcr.io/<org>/<repo>:<tag>`.
3. If logged in but still denied, the account lacks read access — grant `pull`
   permission on that repository, or use a token/PAT with `read:packages` scope.
4. On CI, inject credentials before the pull (e.g. `docker login` with a secret),
   not interactively.

## Validation

```bash
docker pull ghcr.io/myorg/private-api:1.4.2
# Expect: layers download and "Status: Downloaded newer image", no denied error.
```

## Prevention

- Store registry credentials in CI secrets and log in at the start of each job.
- Use scoped, rotating tokens (PATs/robot accounts) rather than personal passwords.
- Reference images by full path in manifests to avoid namespace typos.
- Audit registry RBAC so deploy identities have `pull` on the repos they need.

## Related Errors

- [Docker Manifest Unknown](./docker-manifest-unknown.md)
- [Docker Image Pull Failed](./docker-image-pull-failed.md)

## References

- [Docker login and credential stores](https://docs.docker.com/engine/reference/commandline/login/)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`docker` · `registry` · `authentication` · `pull` · `production`
