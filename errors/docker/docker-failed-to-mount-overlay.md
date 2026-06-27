---
title: "Docker Failed to Mount Overlay"
slug: docker-failed-to-mount-overlay
technologies: [docker]
severity: high
tags: [docker, overlay2, storage-driver, filesystem, production]
related: [docker-no-space-left-on-device, docker-oci-runtime-create-failed]
last_reviewed: 2026-06-27
---

# Docker Failed to Mount Overlay

## Error Message

```text
failed to start container: error creating overlay mount to /var/lib/docker/overlay2/abc123.../merged: too many levels of symbolic links
```

```text
error mounting "overlay" to rootfs: invalid argument: unknown: failed to mount overlay: no such file or directory
```

## Description

Docker's default `overlay2` storage driver assembles a container's root filesystem
by overlaying image layers (lowerdirs) under a writable layer (upperdir) at a
`merged` mountpoint. This error means the kernel's `mount -t overlay` call failed.
It surfaces at container start, when the daemon tries to stack the layers. The
trailing kernel reason — `invalid argument`, `too many levels of symbolic links`,
`no such file or directory`, or `no space left on device` — identifies the cause.

## Technologies

- docker (overlay2 storage driver, Linux OverlayFS, containerd)

## Severity

**high** — affected containers cannot start. If `overlay2` metadata is corrupt at
the host level, *every* container on the host is impacted.

## Common Causes

1. Corrupted or partially-deleted `overlay2` layer directories (lowerdir missing).
2. Backing filesystem doesn't support overlay (e.g. overlay-on-overlay, some
   network/encrypted filesystems, or an unsupported `xfs` without `ftype=1`).
3. Disk or inode exhaustion under the data root (see related error).
4. An interrupted pull/build that left an inconsistent layer set.
5. SELinux/AppArmor or mount-namespace constraints blocking the overlay mount.

## Root Cause Analysis

`overlay2` writes a `link`/`lower` file in each layer dir pointing to the lowerdirs
it stacks. If one of those referenced directories is missing or unreadable, the
`mount` syscall returns `ENOENT`/`EINVAL` and the daemon can't build `merged`.
`xfs` only supports overlay when formatted with `ftype=1` (d_type); without it,
overlay refuses to mount. And because overlay must write the upperdir/workdir, a
full disk or exhausted inodes also breaks the mount. The kernel errno in the
message is the key to which of these applies.

## Diagnostic Commands

```bash
# Confirm overlay2 is the active driver and its state
docker info --format 'Driver: {{.Driver}}  Root: {{.DockerRootDir}}'

# Kernel-level mount failures (the real errno)
journalctl -u docker --no-pager -n 50

# Disk AND inode headroom under the data root
df -h /var/lib/docker && df -i /var/lib/docker

# Backing filesystem and (for xfs) the ftype flag
stat -f -c '%T' /var/lib/docker
xfs_info /var/lib/docker 2>/dev/null | grep ftype
```

## Expected Results

```text
$ journalctl -u docker | grep overlay
... failed to mount overlay: invalid argument

$ xfs_info /var/lib/docker | grep ftype
naming   =version 2   bsize=4096  ascii-ci=0  ftype=0     # ftype=0 -> overlay2 unsupported

$ df -i /var/lib/docker
... IUse% 100%                                            # inode exhaustion
```

## Resolution

1. If disk/inodes are exhausted, prune to free space (review first):

   ```bash
   docker system prune -af
   ```
2. If the backing filesystem is the problem (xfs `ftype=0`), reformat that volume
   with `mkfs.xfs -n ftype=1` (destructive — back up first) or move the data root
   to a supported ext4/xfs(ftype=1) volume via `data-root` in `daemon.json`.
3. For corrupt overlay metadata affecting specific containers, remove and recreate
   them: `docker rm -f <ctr>` then re-run; re-pull the image if layers are bad.
4. As a last resort for pervasive corruption, stop the daemon, move
   `/var/lib/docker` aside, and let Docker recreate it (loses local images/state).

## Validation

```bash
docker run --rm hello-world
# Expect the container to mount its rootfs and run, with no overlay mount error.
```

## Prevention

- Format the data-root volume with overlay-compatible settings (xfs `ftype=1`).
- Monitor both byte and inode usage on `/var/lib/docker`.
- Avoid stacking Docker on top of another overlay or unsupported filesystem.
- Let pulls/builds finish cleanly; abrupt host kills can leave partial layers.

## Related Errors

- [Docker No Space Left on Device](./docker-no-space-left-on-device.md)
- [Docker OCI Runtime Create Failed](./docker-oci-runtime-create-failed.md)

## References

- [Docker: overlay2 storage driver](https://docs.docker.com/storage/storagedriver/overlayfs-driver/)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`docker` · `overlay2` · `storage-driver` · `filesystem` · `production`
