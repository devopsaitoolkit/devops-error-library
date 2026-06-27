---
title: "Linux Read-only file system"
slug: linux-read-only-file-system
technologies: [linux]
severity: high
tags: [linux, filesystem, ext4, remount, production]
related: [linux-disk-io-error-ext4, linux-no-space-left-on-device]
last_reviewed: 2026-06-27
---

# Linux Read-only file system

## Error Message

```text
-bash: /var/log/app.log: Read-only file system
```

```text
kernel: EXT4-fs error (device sda1): ext4_journal_check_start:83: comm kworker: Detected aborted journal
kernel: EXT4-fs (sda1): Remounting filesystem read-only
```

## Description

`Read-only file system` is the userspace text for the `EROFS` errno (30),
returned by any write to a filesystem that is currently mounted read-only.
Sometimes that is intentional (mounted `ro` on purpose), but in production it is
usually the kernel's **self-protection** response: when ext4 detects a filesystem
or I/O error it re-mounts read-only to prevent further corruption. The first log
above is the symptom an app sees; the second is the kernel explaining *why* — an
aborted journal forced the emergency remount.

## Technologies

- linux (ext4 / VFS, block layer)

## Severity

**high** — every write-dependent service on that mount fails simultaneously:
logs stop, databases error, lock/PID files cannot be created. An emergency
read-only remount of `/` is effectively a full host outage and often signals
underlying disk failure with data-loss risk.

## Common Causes

1. Underlying block-device I/O errors (failing disk, bad SATA/NVMe cable, dying
   cloud volume) causing ext4 to abort the journal and remount `ro`.
2. Filesystem corruption detected at runtime, triggering the
   `errors=remount-ro` mount option (the default on most distros).
3. The filesystem was deliberately mounted read-only (image, recovery, or a
   `ro` entry in `/etc/fstab`).
4. A read-only root in an immutable/container image or a snapshot.
5. A storage backend (SAN/NFS/EBS) that went away and returned degraded.

## Root Cause Analysis

ext4 mounts carry an `errors=` policy; the common default `errors=remount-ro`
tells the kernel that on any metadata inconsistency or journal abort it should
flip the mount to read-only rather than risk writing more bad data. When the
block layer returns I/O errors, the journal commit fails, ext4 logs `Detected
aborted journal`, and performs the remount. From that moment every `write()`
returns `EROFS`. The crucial point: read-only is the *consequence*; the *cause*
is in the `dmesg` I/O / EXT4-fs error lines that precede it. Treating it as a
mount problem and simply remounting `rw` without fixing the disk re-triggers it
and can worsen corruption.

## Diagnostic Commands

```bash
# How each filesystem is actually mounted right now (look for "ro")
mount | grep -E ' / | /var '
findmnt -o TARGET,SOURCE,FSTYPE,OPTIONS

# The kernel's reason: I/O errors, journal abort, remount-ro
dmesg -T | grep -iE 'ext4-fs error|aborted journal|remount|I/O error|medium error'

# SMART / device health hint (if smartctl available)
sudo smartctl -H /dev/sda 2>/dev/null | grep -i 'result'

# Confirm the configured fstab options/errors policy
cat /etc/fstab
```

## Expected Results

```text
$ mount | grep ' / '
/dev/sda1 on / type ext4 (ro,relatime,errors=remount-ro)

$ dmesg -T | grep -i ext4
[Sat Jun 27 10:58:01 2026] EXT4-fs error (device sda1): ext4_journal_check_start: Detected aborted journal
[Sat Jun 27 10:58:01 2026] EXT4-fs (sda1): Remounting filesystem read-only
```

The mount option `ro` where you expect `rw`, preceded by `aborted journal` /
`I/O error`, confirms an emergency remount triggered by a lower-layer fault.

## Resolution

1. Triage the **disk first**. If `dmesg` shows I/O/medium errors or SMART is
   failing, treat it as hardware: snapshot/back up data, then replace the device
   or cloud volume. Do not just remount.
2. Unmount and run a filesystem check (the FS must be unmounted or you must boot
   to rescue/single-user):

   ```bash
   sudo umount /dev/sda1
   sudo fsck -y /dev/sda1     # repairs detected corruption
   ```
3. Once the device is healthy and fsck is clean, remount read-write:

   ```bash
   sudo mount -o remount,rw /
   ```
4. If it was intentionally `ro` (image/fstab), change the `fstab` option to `rw`
   and remount.
5. Restore from backup if fsck reports unrecoverable inode/metadata loss.

## Validation

```bash
mount | grep ' / '                 # expect rw, not ro
touch /testfile && rm /testfile && echo "writes OK"
dmesg -T | grep -i ext4 | tail -3  # expect no new errors after remount
```

## Prevention

- Monitor SMART/EDAC and block-device errors; alert before total failure.
- Keep `errors=remount-ro` (it protects data) and alert on the remount event.
- Maintain tested backups/snapshots so fsck loss is recoverable.
- Replace aging disks proactively; use redundant storage (RAID/replication).
- Schedule periodic offline fsck on critical filesystems.

## Related Errors

- [Linux Disk I/O error (ext4)](./linux-disk-io-error-ext4.md)
- [Linux No space left on device](./linux-no-space-left-on-device.md)

## References

- [ext4 documentation](https://docs.kernel.org/admin-guide/ext4.html)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`linux` · `filesystem` · `ext4` · `remount` · `production`
