---
title: "Linux Segmentation fault"
slug: linux-segmentation-fault
technologies: [linux]
severity: medium
tags: [linux, process, sigsegv, crash, production]
related: [linux-systemd-failed-to-start-unit, linux-out-of-memory-oom-killer]
last_reviewed: 2026-06-27
---

# Linux Segmentation fault

## Error Message

```text
Segmentation fault (core dumped)
```

```text
kernel: myapp[4821]: segfault at 0 ip 00007f3c2a9b1c40 sp 00007ffd9c3a21b8 error 4 in libc.so.6[7f3c2a980000+1b6000]
```

```text
systemd-coredump[5012]: Process 4821 (myapp) of user 1000 dumped core.
```

## Description

A segmentation fault occurs when a process accesses a memory address it is not
allowed to touch — dereferencing a null or dangling pointer, writing to
read-only memory, or running off the end of a buffer. The CPU raises a page fault
the kernel cannot resolve, so it delivers `SIGSEGV` (signal 11) to the process,
which by default terminates it. The kernel logs a `segfault at <addr>` line to
`dmesg`, and if core dumps are enabled, `systemd-coredump` captures a core for
post-mortem analysis. The faulting address and instruction pointer in the kernel
line are the first clues.

## Technologies

- linux (kernel signal delivery, process memory protection)

## Severity

**medium** — a single process dies. Impact depends on the process: a one-off CLI
tool is a nuisance, but a crashing long-running daemon (especially one without a
supervisor restart) is a service outage. Repeated segfaults often indicate
memory corruption with data-integrity risk.

## Common Causes

1. A software bug: null-pointer dereference, use-after-free, or buffer overflow
   in the application or a library it links.
2. A library/ABI mismatch — a binary built against one libc/library version run
   against an incompatible one.
3. Corrupt or truncated binary/shared object (bad build, partial deploy).
4. Hardware: failing RAM flipping bits (faults move around addresses).
5. Stack exhaustion from unbounded recursion hitting the guard page.

## Root Cause Analysis

Every process has a virtual address space with regions marked readable,
writable, or executable. When code accesses an address with the wrong
permissions or that maps to nothing, the MMU traps into the kernel page-fault
handler. If the access cannot be made valid (it is not a swapped-out page or a
copy-on-write fault), the kernel sends `SIGSEGV`. The kernel log's `error` code
is a bitmask: bit 0 = page-present, bit 1 = write (vs read), bit 2 = user-mode.
`error 4` means a user-mode read of an unmapped page — a classic null/dangling
read. Pairing that with the core dump's backtrace pinpoints the faulting line.

## Diagnostic Commands

```bash
# Kernel segfault lines: faulting address, IP, and the library involved
dmesg -T | grep -i segfault

# Core dumps captured by systemd-coredump, with the crashing PID/exe
coredumpctl list

# Open a captured core in gdb for a backtrace (read-only inspection)
coredumpctl gdb <pid>

# Confirm core dumps are being collected and where they go
cat /proc/sys/kernel/core_pattern

# Verify the binary's linked libraries resolve (catch ABI mismatch)
ldd /usr/bin/myapp
```

## Expected Results

```text
$ coredumpctl list
TIME                         PID  UID  GID SIG     COREFILE EXE
Sat 2026-06-27 11:02:14 UTC 4821 1000 1000 SIGSEGV present  /usr/bin/myapp

(gdb) bt
#0  0x00007f3c2a9b1c40 in strlen () from /lib/x86_64-linux-gnu/libc.so.6
#1  0x000055d1f3a02b71 in handle_request (req=0x0) at server.c:142
```

A backtrace with a `req=0x0` argument confirms a null-pointer dereference at
`server.c:142`. If faulting addresses are random across runs, suspect RAM.

## Resolution

1. Get a backtrace via `coredumpctl gdb` and fix the offending code (guard the
   null deref, fix the buffer bound, correct the lifetime).
2. If it is an ABI mismatch, rebuild against the deployed library versions or
   pin matching package versions; confirm with `ldd`.
3. Re-deploy from a clean, checksum-verified build if the binary is corrupt.
4. If addresses are random, run a memory test (`memtester`, or `memtest86+` at
   boot) and replace failing DIMMs. **Risk:** memtest is intrusive and slow.
5. For recursion/stack overflow, fix the recursion or raise the stack limit
   (`ulimit -s`) only as a stopgap.

## Validation

```bash
# Re-run the workload and confirm no new core dumps appear
coredumpctl list --since "10 min ago"   # expect: No coredumps found
dmesg -T | grep -i segfault | tail -3   # expect: no new entries
```

## Prevention

- Run new code under ASan/Valgrind in CI to catch memory errors pre-prod.
- Pin and test library versions; deploy binary + its libraries together.
- Enable core dumps in production so crashes are diagnosable, not lost.
- Run a supervisor (systemd `Restart=on-failure`) so a crash auto-recovers.
- Use ECC RAM on critical hosts and monitor EDAC error counters.

## Related Errors

- [Linux systemd Failed to start unit](./linux-systemd-failed-to-start-unit.md)
- [Linux Out of Memory (OOM Killer)](./linux-out-of-memory-oom-killer.md)

## References

- [systemd-coredump documentation](https://www.freedesktop.org/software/systemd/man/systemd-coredump.html)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`linux` · `process` · `sigsegv` · `crash` · `production`
