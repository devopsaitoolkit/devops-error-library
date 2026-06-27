---
title: "Linux No space left on device"
slug: linux-no-space-left-on-device
technologies: [linux]
severity: high
tags: [linux, disk, filesystem, enospc, production]
related: [linux-inode-exhaustion, linux-read-only-file-system]
last_reviewed: 2026-06-27
---

# Linux No space left on device

## Error Message

```text
write error: No space left on device
```

```text
$ touch /var/log/app.log
touch: cannot touch '/var/log/app.log': No space left on device
```

## Description

`No space left on device` is the userspace message for the `ENOSPC` errno (28).
It is returned by any write (`write()`, `creat()`, `mkdir()`, rename) when the
target filesystem cannot allocate the space the operation needs. Almost always
this means the filesystem's data blocks are full, but the *same* message is
returned when **inodes** are exhausted even though free blocks remain — a common
trap. The error surfaces from applications, package managers, log writers, and
databases the instant they try to grow a file.

## Technologies

- linux (filesystem / VFS layer)

## Severity

**high** — services that cannot write logs, sockets, lock files, or data abort
or hang. A full root filesystem can prevent logins and break package management,
turning a single full mount into a host-wide outage.

## Common Causes

1. Unrotated or runaway log files filling `/var` or `/`.
2. Large files left behind (core dumps, temp files, old releases, big tarballs).
3. **Deleted-but-open files** whose blocks aren't freed because a process still
   holds the file descriptor (`df` shows full, `du` shows less).
4. Inode exhaustion — millions of tiny files (see related error); blocks free but
   `ENOSPC` still returned.
5. A filling thin-provisioned volume or a full container overlay.

## Root Cause Analysis

A filesystem tracks free data blocks and free inodes separately. A write that
needs a new block fails with `ENOSPC` when no free blocks exist; a create that
needs a new inode fails with the *same* `ENOSPC` when no free inodes exist. The
deleted-but-open case is the subtlest: `unlink()` removes the directory entry,
but the kernel only reclaims the blocks when the last open file descriptor is
closed. Until then `df` (which reads filesystem accounting) reports the space as
used while `du` (which walks visible files) cannot see it.

## Diagnostic Commands

```bash
# Block usage per mounted filesystem — find the full mount
df -h

# Inode usage per filesystem — rules in/out inode exhaustion
df -i

# Biggest directories under the full mount (start at its root)
du -xh --max-depth=1 /var 2>/dev/null | sort -rh | head -20

# Deleted files still held open (space not reclaimed)
lsof -nP +L1 2>/dev/null | grep -i deleted

# Kernel messages — quotas, fs errors around the failure
dmesg -T | grep -iE 'no space|enospc|quota'
```

## Expected Results

```text
$ df -h
Filesystem      Size  Used Avail Use% Mounted on
/dev/sda1        50G   50G     0 100% /

$ df -i
Filesystem     Inodes  IUsed IFree IUse% Mounted on
/dev/sda1     3276800 102311 ...   4% /
```

Here `Use% 100%` with healthy `IUse%` confirms a **block** problem, not inodes.
If `lsof +L1` lists a multi-GB deleted log still open, the space is trapped by a
running process.

## Resolution

1. Find and remove or truncate the offender. To reclaim a deleted-but-open file
   without restarting the process, truncate via its fd:

   ```bash
   : > /proc/<pid>/fd/<n>        # zero the still-open deleted file
   ```
2. Rotate/compress logs immediately if logs are the cause
   (`journalctl --vacuum-size=500M` for the journal).
3. Delete stale artifacts (old releases, core dumps in `/var/crash`, `/tmp`).
4. If it is genuinely full with valid data, grow the filesystem/volume
   (`lvextend` + `resize2fs`, or expand the cloud disk).
5. Restart the process holding a deleted file if you cannot truncate it safely.

## Validation

```bash
df -h /var          # Use% well below 100, Avail restored
touch /var/log/test && rm /var/log/test && echo OK   # writes succeed again
```

## Prevention

- Configure `logrotate` and journald `SystemMaxUse=` limits.
- Alert at 80% block usage, not at 100%.
- Put `/var/log`, `/tmp`, and data on separate filesystems from `/`.
- Cap core dumps (`ulimit -c`, `/proc/sys/kernel/core_pattern`).
- Monitor thin-pool and overlay usage on container hosts.

## Related Errors

- [Linux Inode exhaustion](./linux-inode-exhaustion.md)
- [Linux Read-only file system](./linux-read-only-file-system.md)

## References

- [util-linux df documentation](https://man7.org/linux/man-pages/man1/df.1.html)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`linux` · `disk` · `filesystem` · `enospc` · `production`
