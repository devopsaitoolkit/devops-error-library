---
title: "Docker Manifest Unknown"
slug: docker-manifest-unknown
technologies: [docker]
severity: medium
tags: [docker, registry, tag, manifest, production]
related: [docker-pull-access-denied, docker-no-matching-manifest-linux-amd64]
last_reviewed: 2026-06-27
---

# Docker Manifest Unknown

## Error Message

```text
Error response from daemon: manifest for myorg/api:v2.3.1 not found: manifest unknown: manifest unknown
```

```text
manifest unknown: OCI index found, but no matching manifest. tag does not exist
```

## Description

The registry resolved the repository and authorized the request, but the specific
**reference** — usually a tag, sometimes a digest — does not point to any manifest.
Unlike *pull access denied* (an auth/visibility problem), here you reached the
repo successfully; the exact tag or digest you asked for simply isn't there. It is
emitted by the registry during manifest resolution.

## Technologies

- docker (registry API v2, manifest resolution)

## Severity

**medium** — the dependent pull/deploy fails, but it's a reference-correctness
issue. The blast radius is whatever pipeline pinned the missing tag.

## Common Causes

1. The tag is misspelled or uses the wrong convention (`v2.3.1` vs `2.3.1`).
2. The tag was never pushed, or was deleted / overwritten / retention-pruned.
3. Pinning to a digest that no longer exists after a registry GC.
4. Wrong repository or registry host, so the tag exists elsewhere but not here.
5. A multi-arch push failed partway, leaving the index without the tag.

## Root Cause Analysis

A pull is a two-step lookup: resolve `repo:tag` (or `@digest`) to a manifest, then
fetch the referenced blobs. *manifest unknown* is the registry saying the first
step failed — there is no manifest under that reference. Because auth already
succeeded, this is purely about whether that tag/digest exists in that repo. Listing
the repository's real tags immediately disambiguates a typo from a never-pushed tag.

## Diagnostic Commands

```bash
# Inspect the exact reference (read-only) — fails with manifest unknown if absent
docker manifest inspect myorg/api:v2.3.1

# List tags that actually exist in the repo via the registry v2 API
curl -s https://registry.example.com/v2/myorg/api/tags/list | head

# Confirm the reference string you're using is what you think it is
echo "registry.example.com/myorg/api:v2.3.1"
```

## Expected Results

```text
$ docker manifest inspect myorg/api:v2.3.1
no such manifest: myorg/api:v2.3.1

$ curl -s https://registry.example.com/v2/myorg/api/tags/list
{"name":"myorg/api","tags":["2.3.0","2.3.1","latest"]}   # note: "2.3.1", not "v2.3.1"
```

## Resolution

1. List the repo's tags and pull an existing one; fix the reference to match the
   real tag convention.
2. If the tag should exist but doesn't, (re)push it:

   ```bash
   docker tag local/api:build registry.example.com/myorg/api:2.3.1
   docker push registry.example.com/myorg/api:2.3.1
   ```
3. If you pinned a digest that was GC'd, re-resolve the tag to a current digest
   and update the pin.
4. Verify you're pointing at the correct registry host and repository path.

## Validation

```bash
docker pull registry.example.com/myorg/api:2.3.1
# Expect a successful pull; the previously-missing reference now resolves.
```

## Prevention

- Standardize and document one tag convention; lint references in manifests.
- Treat published tags as immutable; never delete tags a deploy may still pin.
- Prefer pulling by digest only when paired with a retention/GC policy that keeps it.
- Verify multi-arch pushes completed (`docker manifest inspect`) before deploying.

## Related Errors

- [Docker Pull Access Denied](./docker-pull-access-denied.md)
- [Docker No Matching Manifest for linux/amd64](./docker-no-matching-manifest-linux-amd64.md)

## References

- [Registry API v2: manifests and tags](https://distribution.github.io/distribution/spec/api/)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`docker` · `registry` · `tag` · `manifest` · `production`
