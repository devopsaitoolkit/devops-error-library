---
title: "Docker No Space Left on Device"
slug: docker-no-space-left-on-device
technologies: [docker]
severity: high
tags: [docker, disk, storage, cleanup, production]
related: [docker-failed-to-mount-overlay, docker-image-pull-failed]
last_reviewed: 2026-06-27
---

# Docker No Space Left on Device

## Error Message

```text
write /var/lib/docker/tmp/GetImageBlob123456789: no space left on device
```

```text
failed to register layer: Error processing tar file(exit status 1): write /usr/lib/.../libfoo.so: no space left on device
```

## Description

Docker stores images, container writable layers, volumes, and build cache under
its data root (default `/var/lib/docker`). When the filesystem backing that
directory fills up — or runs out of **inodes** — any operation that writes
(pulling, building, starting a container, writing logs) fails with *no space left
on device*. The message is the kernel's `ENOSPC`; Docker just surfaces it during
whatever write it was attempting.

## Technologies

- docker (data root `/var/lib/docker`, storage driver, host filesystem)

## Severity

**high** — builds and pulls fail, containers can't write, and a full root
filesystem can destabilize the whole host, not just Docker.

## Common Causes

1. Accumulated dangling images, stopped containers, and unused build cache.
2. Unbounded container logs (`json-file` driver with no rotation).
3. Large or orphaned named/anonymous volumes never cleaned up.
4. Inode exhaustion (millions of tiny files) even though bytes look free.
5. A small dedicated disk/partition for `/var/lib/docker` that simply filled.

## Root Cause Analysis

Every pulled layer, container diff, and build step consumes blocks under the data
root. Without pruning, this grows monotonically. Two distinct exhaustion modes
both produce the same `ENOSPC`: running out of **bytes** (`df -h`) or running out
of **inodes** (`df -i`) — the latter is common with overlay2 because images
contain huge numbers of small files. Container logs are a third silent consumer:
a chatty container with no log rotation can fill a disk on its own.

## Diagnostic Commands

```bash
# Bytes free on the data-root filesystem
df -h /var/lib/docker

# Inodes free — a separate exhaustion mode
df -i /var/lib/docker

# What Docker itself is using, by category (images/containers/volumes/cache)
docker system df -v

# Largest log files under the data root
du -sh /var/lib/docker/containers/*/*-json.log 2>/dev/null | sort -rh | head
```

## Expected Results

```text
$ df -h /var/lib/docker
Filesystem      Size  Used Avail Use% Mounted on
/dev/nvme0n1p1   50G   50G     0 100% /

$ df -i /var/lib/docker
Filesystem      Inodes  IUsed IFree IUse% Mounted on
/dev/nvme0n1p1  3276800 3276800   0  100% /     # inodes exhausted

$ docker system df
TYPE          TOTAL  ACTIVE  SIZE     RECLAIMABLE
Images        142    8       38.7GB   31.2GB (80%)
Build Cache   980    0       12.4GB   12.4GB
```

## Resolution

1. Reclaim space safely, starting with what's clearly unused:

   ```bash
   docker container prune          # stopped containers
   docker image prune              # dangling images
   docker builder prune            # build cache
   ```
2. For a deeper cleanup (review first — this removes ALL unused data and,
   with `--volumes`, unattached volumes):

   ```bash
   docker system prune -a --volumes
   ```
3. Cap container logs so they can't refill the disk:

   ```json
   { "log-driver": "json-file", "log-opts": { "max-size": "10m", "max-file": "3" } }
   ```
4. If inodes are the issue, the same prunes help; consider moving the data root
   to a larger/dedicated volume via `data-root` in `daemon.json`.

## Validation

```bash
df -h /var/lib/docker && df -i /var/lib/docker
# Expect Use% and IUse% well below 100; re-run the failed pull/build successfully.
```

## Prevention

- Configure global log rotation in `daemon.json` (`max-size`/`max-file`).
- Run a scheduled `docker system prune -af --filter "until=168h"` on hosts.
- Monitor and alert on `/var/lib/docker` byte AND inode usage.
- Put the data root on its own sized volume so a fill can't take down the OS disk.

## Related Errors

- [Docker Failed to Mount Overlay](./docker-failed-to-mount-overlay.md)
- [Docker Image Pull Failed](./docker-image-pull-failed.md)

## References

- [Docker: prune unused objects](https://docs.docker.com/config/pruning/)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`docker` · `disk` · `storage` · `cleanup` · `production`
