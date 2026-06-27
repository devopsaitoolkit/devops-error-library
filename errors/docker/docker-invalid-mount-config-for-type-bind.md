---
title: "Docker Invalid Mount Config for Type \"bind\""
slug: docker-invalid-mount-config-for-type-bind
technologies: [docker]
severity: medium
tags: [docker, volumes, bind-mount, configuration, production]
related: [docker-oci-runtime-create-failed, docker-failed-to-mount-overlay]
last_reviewed: 2026-06-27
---

# Docker Invalid Mount Config for Type "bind"

## Error Message

```text
docker: Error response from daemon: invalid mount config for type "bind": bind source path does not exist: /opt/data/config
```

```text
Error response from daemon: invalid mount config for type "bind": field Source must not be empty
```

## Description

A bind mount maps an existing **host** path into the container. Docker validates
the mount spec before starting the container, and rejects it with this error when
the source path is missing, empty, relative, or malformed. By default, bind mount
sources are not auto-created (unlike named volumes), so a wrong or not-yet-created
host path fails immediately. This is a configuration error, caught at create time.

## Technologies

- docker (mount validation, bind mounts, Compose)

## Severity

**medium** — the container won't start, but the daemon and other containers are
fine. It's a fast configuration fix once the offending path is identified.

## Common Causes

1. The host source path does not exist (typo, wrong host, not yet provisioned).
2. A relative path was used where Docker requires an absolute one.
3. An empty/unset variable expanded to an empty `Source` (`-v ${MISSING}:/data`).
4. On Compose, a `volumes:` entry references a host path not present on the node.
5. Confusing a bind mount with a named volume (named volumes auto-create; binds don't).

## Root Cause Analysis

When the daemon parses `--mount type=bind,source=...,target=...` (or the `-v`
short form), it requires `Source` to be a non-empty, absolute path that exists on
the host. The CLI/daemon `stat`s the source; if it's missing or the field is
empty/relative, validation fails before any namespace setup. Variable interpolation
that yields an empty string is a frequent trigger because the error then names an
empty or unexpected source rather than the literal you intended.

## Diagnostic Commands

```bash
# Does the intended host source path actually exist?
ls -ld /opt/data/config

# Show the exact command/variables being expanded (check for empty vars)
echo "source=${DATA_DIR}"

# For Compose, render the resolved config including absolute mount sources
docker compose config | grep -A4 'volumes'
```

## Expected Results

```text
$ ls -ld /opt/data/config
ls: cannot access '/opt/data/config': No such file or directory   # missing source

$ echo "source=${DATA_DIR}"
source=            # variable empty -> "Source must not be empty"

# Healthy:
$ ls -ld /opt/data/config
drwxr-xr-x 2 root root 4096 Jun 27 05:00 /opt/data/config
```

## Resolution

1. Create the host directory before running, if a bind mount is truly intended:

   ```bash
   sudo mkdir -p /opt/data/config
   ```
2. Use absolute paths for bind sources; for the current directory use `"$(pwd)"`:

   ```bash
   docker run -v "$(pwd)/config:/etc/app" myimage
   ```
3. Ensure interpolated variables are set (e.g. via an `.env` file for Compose) so
   `Source` never expands empty.
4. If you don't actually need host data, switch to a **named volume**, which Docker
   creates automatically: `-v appdata:/data`.

## Validation

```bash
docker run --rm -v /opt/data/config:/etc/app busybox ls /etc/app
# Expect the host directory's contents listed inside the container, no mount error.
```

## Prevention

- Create or provision bind-source paths in host setup before deploying.
- Run `docker compose config` in CI to catch unresolved/empty mount sources.
- Prefer named volumes for managed data; reserve bind mounts for known host paths.
- Always quote and absolute-ize paths in run/compose definitions.

## Related Errors

- [Docker OCI Runtime Create Failed](./docker-oci-runtime-create-failed.md)
- [Docker Failed to Mount Overlay](./docker-failed-to-mount-overlay.md)

## References

- [Docker: bind mounts](https://docs.docker.com/storage/bind-mounts/)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`docker` · `volumes` · `bind-mount` · `configuration` · `production`
