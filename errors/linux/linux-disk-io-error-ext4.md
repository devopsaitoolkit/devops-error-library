---
title: "Linux Disk I/O error (ext4)"
slug: linux-disk-io-error-ext4
technologies: [linux]
severity: critical
tags: [linux, disk, ext4, io-error, production]
related: [linux-read-only-file-system, linux-kernel-panic-not-syncing]
last_reviewed: 2026-06-27
---

# Linux Disk I/O error (ext4)

## Error Message

```text
kernel: blk_update_request: I/O error, dev sda, sector 1953120 op 0x0:(READ) flags 0x0 phys_seg 1 prio class 0
kernel: EXT4-fs warning (device sda1): ext4_end_bio:343: I/O error 10 writing to inode 786433
```

```text
kernel: critical medium error, dev sda, sector 1953120
kernel: Buffer I/O error on dev sda1, logical block 244140, lost async page write
```

## Description

A disk I/O error means the kernel's block layer asked the storage device to read
or write a sector and the device **failed or returned bad data**. The
`blk_update_request: I/O error` line names the device and sector; the
accompanying `EXT4-fs` / `Buffer I/O error` lines show the filesystem reacting to
the failed block. Unlike a full disk (`ENOSPC`) or a permissions issue, this is a
storage-reliability fault: a failing drive, a bad cable/controller, a degraded
SAN/cloud volume, or media errors. Left unaddressed it leads ext4 to abort the
journal and remount read-only, and risks data loss.

## Technologies

- linux (block layer, ext4, storage device drivers)

## Severity

**critical** — I/O errors mean reads may return corrupt data and writes may be
silently lost, putting data integrity at risk. They commonly cascade into an
emergency read-only remount (full service outage) and, on the root device, into
an unbootable system. Treat any sustained I/O error as a failing-disk incident.

## Common Causes

1. A physically failing drive — reallocated/pending sectors, media/medium errors
   (the device itself reports `critical medium error`).
2. A bad SATA/SAS/NVMe cable, backplane, or HBA/controller corrupting transfers.
3. A degraded or detached cloud block volume / SAN LUN (network storage that went
   away or returned errors).
4. Controller/driver firmware bugs or a RAID array in a degraded/failed state.
5. Overheating or power issues causing the device to drop off the bus.

## Root Cause Analysis

When the block layer submits a request, the device driver returns the completion
status. A non-zero error (`-EIO`) makes the kernel log `blk_update_request: I/O
error` with the exact `dev` and `sector`. ext4, which had queued that block for a
journal commit or page writeback, then logs `EXT4-fs ... I/O error` or `Buffer
I/O error ... lost async page write` — meaning a dirty page could not be persisted
and its data is now lost from durable storage. If the journal commit itself
fails, ext4 invokes its `errors=remount-ro` policy. SMART attributes
(`Reallocated_Sector_Ct`, `Current_Pending_Sector`, `Offline_Uncorrectable`)
typically show the device degrading before total failure — confirming hardware,
not software, as the cause.

## Diagnostic Commands

```bash
# The authoritative evidence: I/O errors, device, sector, ext4 reaction
dmesg -T | grep -iE 'i/o error|blk_update_request|medium error|ext4-fs (error|warning)|buffer i/o'

# Drive health and the telltale failing-sector counters
sudo smartctl -a /dev/sda | grep -iE 'health|reallocated|pending|uncorrectable|crc'

# Run/read the drive self-test log
sudo smartctl -l selftest /dev/sda

# Which device/partition maps to the failing node, and the mount
lsblk -o NAME,SIZE,TYPE,MOUNTPOINT,MODEL
findmnt /dev/sda1

# RAID array state, if applicable
cat /proc/mdstat 2>/dev/null
```

## Expected Results

```text
$ dmesg -T | grep -i 'i/o error'
blk_update_request: I/O error, dev sda, sector 1953120 op 0x0:(READ)
critical medium error, dev sda, sector 1953120

$ smartctl -a /dev/sda | grep -i pending
197 Current_Pending_Sector  0x0032   100   100   000   ...  -  48
198 Offline_Uncorrectable   0x0030   100   100   000   ...  -  48
```

Non-zero `Current_Pending_Sector` / `Offline_Uncorrectable`, or a SMART overall
health of `FAILED`, confirms the drive is dying. Repeating errors on the *same*
sector point at media defects; errors across random sectors with CRC errors point
at cabling/controller.

## Resolution

1. Treat it as a hardware incident. **Back up / snapshot data immediately** while
   the device is still partly readable — every further access risks more loss.
2. Identify the device from `dmesg`/`smartctl`. If SMART shows failing/pending
   sectors or `FAILED` health, plan to **replace the drive** (or detach/replace
   the cloud volume).
3. For a RAID array, replace the failed member and let it rebuild
   (`/proc/mdstat` shows resync); for cloud, restore from snapshot to a healthy
   volume.
4. After replacement, restore data and run `fsck` on the new device to clear any
   metadata damage. **Risk:** never run `fsck` on a physically failing disk — it
   can finish the job of destroying it; copy data off first.
5. If the cause is cabling/controller (CRC errors, random sectors), reseat/replace
   the cable or HBA before condemning the drive.

## Validation

```bash
dmesg -T | grep -i 'i/o error' | tail   # expect: no new errors after replacement
sudo smartctl -H /dev/sdX               # expect: PASSED on the replacement
findmnt /dev/sdX1                        # filesystem mounts rw cleanly
```

## Prevention

- Run scheduled SMART self-tests and alert on reallocated/pending/CRC counters.
- Use redundancy (RAID/replication, multi-AZ volumes) so one disk failure is
  survivable.
- Maintain tested backups/snapshots; assume any disk can fail.
- Monitor `dmesg` for `I/O error` and page it immediately — it rarely improves.
- Replace drives proactively past their reliability window; track temperatures.

## Related Errors

- [Linux Read-only file system](./linux-read-only-file-system.md)
- [Linux Kernel panic - not syncing](./linux-kernel-panic-not-syncing.md)

## References

- [smartmontools / SMART attributes](https://www.smartmontools.org/)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`linux` · `disk` · `ext4` · `io-error` · `production`
