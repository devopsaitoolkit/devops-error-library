---
title: "Linux Kernel panic - not syncing"
slug: linux-kernel-panic-not-syncing
technologies: [linux]
severity: critical
tags: [linux, kernel, panic, boot, production]
related: [linux-out-of-memory-oom-killer, linux-disk-io-error-ext4]
last_reviewed: 2026-06-27
---

# Linux Kernel panic - not syncing

## Error Message

```text
Kernel panic - not syncing: VFS: Unable to mount root fs on unknown-block(0,0)
```

```text
Kernel panic - not syncing: Attempted to kill init! exitcode=0x00000100
CPU: 0 PID: 1 Comm: systemd Not tainted 6.8.0-31-generic #31-Ubuntu
Call Trace:
 <TASK>
 dump_stack_lvl+0x48/0x70
 panic+0x1a0/0x340
 do_exit+0x...
```

## Description

A kernel panic is the kernel's equivalent of an unrecoverable crash: it has
detected a condition from which it cannot safely continue, so it halts the entire
machine. "not syncing" means it is **not** flushing filesystem buffers to disk
first — it stops immediately to avoid writing corrupt data. The panic string
after the colon states the cause: a missing root filesystem, a dead `init`, a bad
driver, or hardware. The machine is frozen (or auto-reboots if `panic=` is set);
nothing on it runs until it is rebooted, usually via console.

## Technologies

- linux (kernel core, init, block/driver subsystems)

## Severity

**critical** — the entire host is down. Every workload on the machine stops at
once, and recovery requires console/out-of-band access. A panic at boot can make
a server unbootable until the root cause (initramfs, driver, hardware) is fixed.

## Common Causes

1. The kernel cannot mount the root filesystem — wrong root device/UUID, missing
   storage driver in the initramfs, or a corrupt/absent disk (the `unknown-block`
   variant).
2. A broken or mismatched kernel module/driver (especially out-of-tree GPU,
   storage, or network drivers) dereferencing bad memory in kernel space.
3. `init`/PID 1 (systemd) dying — "Attempted to kill init!".
4. Failing hardware: bad RAM, CPU, or a Machine Check Exception (MCE).
5. A corrupt kernel image or a botched kernel upgrade / initramfs regeneration.

## Root Cause Analysis

The kernel calls `panic()` whenever core invariants break: PID 1 exiting, an
unrecoverable oops in a critical path, or a failed early-boot step like mounting
root. Because the kernel can no longer trust its own state, it deliberately does
**not** sync — flushing buffers might commit corruption. It prints a panic
message and a call trace (the most useful artifact), then either hangs or reboots
after `kernel.panic` seconds. For boot-time panics, the message identifies the
phase: a VFS root-mount panic means the initramfs lacks the right driver or the
root UUID/device is wrong; a driver oops names the offending module in the trace.

## Diagnostic Commands

```bash
# After an auto-reboot, the panic from the PREVIOUS boot (if persistent journal)
journalctl -k -b -1 --no-pager | tail -60

# Crash dumps captured by kdump, if configured
ls -lh /var/crash/

# Whether the failing kernel actually contains the needed storage modules
lsinitramfs /boot/initrd.img-$(uname -r) | grep -iE 'nvme|virtio|ahci|xfs|ext4'

# Confirm the root device the bootloader is pointing at vs what exists
cat /proc/cmdline
blkid

# Hardware error log (MCE) that can precede a panic
journalctl -k -b -1 | grep -iE 'mce|hardware error|machine check'
```

## Expected Results

```text
$ journalctl -k -b -1 | tail -20
Kernel panic - not syncing: VFS: Unable to mount root fs on unknown-block(0,0)

$ cat /proc/cmdline
BOOT_IMAGE=/vmlinuz-6.8.0-31-generic root=UUID=ab12... ro

$ blkid
/dev/nvme0n1p1: UUID="cd34..." TYPE="ext4"
```

If the `root=UUID` in `/proc/cmdline` does not match any UUID in `blkid`, or the
initramfs lacks the `nvme`/`virtio` module for that disk, the kernel cannot find
root — the cause of the VFS panic.

## Resolution

1. For a root-mount panic, boot a known-good previous kernel from the GRUB menu,
   then fix the cause: correct the `root=UUID=` in `/etc/default/grub`
   (`update-grub`) or rebuild the initramfs with the storage driver
   (`update-initramfs -u -k <version>`).
2. For a driver oops, identify the module in the call trace and blacklist or
   update it; boot with `module_blacklist=<name>` as a stopgap.
3. If PID 1 died, boot to an earlier kernel/recovery and repair the broken
   systemd or its dependencies.
4. For suspected hardware (MCE in logs), run vendor diagnostics / memtest and
   replace the faulty component. **Risk:** continuing on failing RAM corrupts
   data.
5. Enable `kdump` so the *next* panic produces a vmcore for root-cause analysis.

## Validation

```bash
uname -r                                   # booted into the intended kernel
journalctl -k -b 0 | grep -i panic         # expect: nothing in current boot
systemctl is-system-running                # expect: running (or degraded, not stuck)
```

## Prevention

- Keep at least one known-good previous kernel installed and bootable.
- Test kernel upgrades in staging; verify initramfs contains storage drivers.
- Configure `kdump`/crashkernel so panics are diagnosable.
- Set `kernel.panic=10` to auto-reboot instead of hanging on remote hosts.
- Monitor MCE/EDAC counters; replace hardware before it panics.

## Related Errors

- [Linux Out of Memory (OOM Killer)](./linux-out-of-memory-oom-killer.md)
- [Linux Disk I/O error (ext4)](./linux-disk-io-error-ext4.md)

## References

- [Linux kernel: Kdump documentation](https://docs.kernel.org/admin-guide/kdump/kdump.html)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`linux` · `kernel` · `panic` · `boot` · `production`
