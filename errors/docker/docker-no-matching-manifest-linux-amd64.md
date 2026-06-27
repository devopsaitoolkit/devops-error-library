---
title: "Docker No Matching Manifest for linux/amd64"
slug: docker-no-matching-manifest-linux-amd64
technologies: [docker]
severity: medium
tags: [docker, multi-arch, platform, manifest, production]
related: [docker-manifest-unknown, docker-oci-runtime-create-failed]
last_reviewed: 2026-06-27
---

# Docker No Matching Manifest for linux/amd64

## Error Message

```text
no matching manifest for linux/amd64 in the manifest list entries
```

```text
docker: image with reference myorg/tool:1.0 was found but does not match the specified platform: wanted linux/arm64/v8, actual: linux/amd64.
```

## Description

The image reference resolves to a **manifest list** (a multi-arch index), but that
index contains no entry matching the platform Docker is pulling for. The
repository and tag exist (so this is not *manifest unknown*); the image just wasn't
built for your CPU architecture/OS. This is increasingly common on mixed fleets of
`amd64` servers and `arm64` machines (Apple Silicon, Graviton).

## Technologies

- docker (multi-arch manifest lists, BuildKit/buildx, host platform)

## Severity

**medium** — the affected platform can't run the image, so deploys to that arch
fail. Other architectures of the same fleet may be unaffected.

## Common Causes

1. The image was published for only one architecture (e.g. arm64-only from an M-series Mac).
2. The host is a different arch than what the image provides.
3. An explicit `--platform` was requested that the index doesn't include.
4. A multi-arch build/push only completed for some platforms.
5. A base image used in the build itself lacks the target arch.

## Root Cause Analysis

A manifest list maps `os/arch[/variant]` tuples to concrete per-platform
manifests. When pulling, Docker selects the entry matching the host (or the
requested `--platform`). If no tuple matches, there is nothing to download and the
client reports *no matching manifest*. The fix is either to build/publish the image
for the needed platform or to run the existing arch under emulation.

## Diagnostic Commands

```bash
# What platforms does the index actually contain?
docker manifest inspect myorg/tool:1.0 | grep -A2 '"platform"'

# What platform is THIS host?
docker version --format '{{.Server.Os}}/{{.Server.Arch}}'
uname -m

# Inspect the local image's architecture if one was pulled
docker image inspect myorg/tool:1.0 --format '{{.Os}}/{{.Architecture}}'
```

## Expected Results

```text
$ docker manifest inspect myorg/tool:1.0 | grep -A2 '"platform"'
"platform": { "architecture": "arm64", "os": "linux" }   # only arm64 present

$ docker version --format '{{.Server.Os}}/{{.Server.Arch}}'
linux/amd64                                               # host needs amd64 -> no match
```

## Resolution

1. Rebuild and publish the image for the missing platform with buildx:

   ```bash
   docker buildx build \
     --platform linux/amd64,linux/arm64 \
     -t myorg/tool:1.0 --push .
   ```
2. As a stopgap, run the available arch under QEMU emulation (slower):

   ```bash
   docker run --platform linux/amd64 myorg/tool:1.0
   ```
3. Ensure every base image (`FROM`) in the Dockerfile is itself multi-arch.
4. Verify the push produced all platforms with `docker manifest inspect` before
   declaring the release done.

## Validation

```bash
docker pull myorg/tool:1.0 && \
  docker image inspect myorg/tool:1.0 --format '{{.Architecture}}'
# Expect the pull to succeed and the architecture to match the host.
```

## Prevention

- Build release images with `buildx` for all architectures your fleet runs.
- Add a CI check that `docker manifest inspect` lists every required platform.
- Pin multi-arch base images; avoid arch-specific bases unless intentional.
- Document target platforms per service so single-arch builds are caught in review.

## Related Errors

- [Docker Manifest Unknown](./docker-manifest-unknown.md)
- [Docker OCI Runtime Create Failed](./docker-oci-runtime-create-failed.md)

## References

- [Docker multi-platform images (buildx)](https://docs.docker.com/build/building/multi-platform/)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`docker` · `multi-arch` · `platform` · `manifest` · `production`
