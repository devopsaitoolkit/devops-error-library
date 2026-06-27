---
title: "Linux Inode exhaustion"
slug: linux-inode-exhaustion
technologies: [linux]
severity: high
tags: [linux, filesystem, inodes, enospc, production]
related: [linux-no-space-left-on-device, linux-read-only-file-system]
last_reviewed: 2026-06-27
---

# Linux Inode exhaustion

## Error Message

```text
cannot create directory 'cache': No space left on device
```

```text
$ df -h /var
Filesystem      Size  Used Avail Use% Mounted on
/dev/sdb1        50G   12G   36G  25% /var
```

## Description

Inode exhaustion is the confusing case of `No space left on device` (`ENOSPC`,
errno 28) where there is plenty of **free disk space** but **no free inodes**. An
inode is the on-disk structure that stores a file's metadata; ext2/3/4 allocate a
fixed number of them at `mkfs` time. Every file, directory, symlink, and socket
consumes one. When they run out, the filesystem cannot create any new entry even
though gigabytes of blocks are free — which is why `df -h` looks fine while every
create fails. The giveaway is that `df -h` and `df -i` disagree.

## Technologies

- linux (ext-family filesystem inode allocation)

## Severity

**high** — identical operational impact to a full disk: no new files, sockets,
or lock files can be created, so write-dependent services fail. It is more
dangerous because the obvious metric (`df -h`) shows free space, so the cause is
easily missed and outages drag on.

## Common Causes

1. Millions of tiny files in one tree — session files, mail spools, cache
   fragments, npm/`node_modules` sprawl, or per-request temp files never cleaned.
2. A runaway process creating files in a tight loop (e.g. a misconfigured logger
   writing one file per event).
3. A filesystem formatted with too few inodes for its workload (large
   `bytes-per-inode` ratio at `mkfs` time).
4. Unrotated maildir/queue directories accumulating small messages.
5. Orphaned `.nfsXXXX` or temp files from interrupted operations.

## Root Cause Analysis

At `mkfs.ext4` time the kernel computes a fixed inode count from the
`bytes-per-inode` ratio (default ~16 KiB per inode). That count is the hard
ceiling for the life of the filesystem — it cannot grow without a reformat. Each
named object consumes exactly one inode regardless of size, so a filesystem full
of 1-byte files exhausts inodes long before blocks. When the free-inode count
hits zero, the allocator returns `ENOSPC` from `creat()`/`mkdir()` — the same
errno as a block-full filesystem, which is why the two failure modes are
indistinguishable from the error text alone.

## Diagnostic Commands

```bash
# THE decisive command: inode usage per filesystem (IUse% at/near 100%)
df -i

# Compare with block usage — the contradiction confirms inode exhaustion
df -h

# Find which directory holds the most files (counts inodes by subtree)
for d in /var/*; do echo "$(find "$d" -xdev 2>/dev/null | wc -l) $d"; done | sort -rn | head

# Directories with the most immediate entries
find /var -xdev -type d -printf '%h\n' 2>/dev/null | sort | uniq -c | sort -rn | head

# How a filesystem was provisioned (total inode count)
sudo dumpe2fs -h /dev/sdb1 2>/dev/null | grep -i 'inode count'
```

## Expected Results

```text
$ df -i
Filesystem      Inodes   IUsed IFree IUse% Mounted on
/dev/sdb1      3276800 3276800     0  100% /var

$ df -h /var
/dev/sdb1        50G   12G   36G   25% /var
```

`IUse% 100%` with `Use% 25%` is the unambiguous signature: inodes are exhausted
while blocks are nearly empty. The `find | wc -l` pass then names the directory
holding the offending file count.

## Resolution

1. Locate the directory with the runaway file count and delete the junk. Deleting
   millions of files is slow; do it in batches to avoid pinning I/O:

   ```bash
   find /var/cache/app -xdev -type f -mtime +7 -delete   # prune old files
   ```
2. Stop the producer (fix the loop/logger creating files; add rotation/cleanup).
3. If the filesystem is genuinely too small in inodes for its purpose, back up,
   reformat with more inodes (`mkfs.ext4 -i 4096 ...` for many small files), and
   restore. **Risk:** reformatting destroys data — back up first.
4. Consider XFS for workloads with huge file counts (dynamic inode allocation).

## Validation

```bash
df -i /var           # IFree restored, IUse% well below 100
mkdir /var/_t && rmdir /var/_t && echo "creates OK"   # creation succeeds again
```

## Prevention

- Alert on **inode** usage (`df -i`) in addition to block usage.
- Add cleanup/rotation for any directory that accumulates small files.
- Choose `-i` (bytes-per-inode) appropriately at `mkfs` for small-file workloads.
- Use XFS where extreme small-file counts are expected.
- Cap per-process temp-file creation and clean `/tmp` (tmpfiles.d).

## Related Errors

- [Linux No space left on device](./linux-no-space-left-on-device.md)
- [Linux Read-only file system](./linux-read-only-file-system.md)

## References

- [mke2fs and bytes-per-inode](https://man7.org/linux/man-pages/man8/mke2fs.8.html)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`linux` · `filesystem` · `inodes` · `enospc` · `production`
