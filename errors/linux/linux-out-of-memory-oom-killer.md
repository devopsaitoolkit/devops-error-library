---
title: "Linux Out of Memory (OOM Killer)"
slug: linux-out-of-memory-oom-killer
technologies: [linux]
severity: high
tags: [linux, memory, oom, kernel, production]
related: [linux-fork-cannot-allocate-memory, linux-kernel-panic-not-syncing]
last_reviewed: 2026-06-27
---

# Linux Out of Memory (OOM Killer)

## Error Message

```text
[12345.678901] Out of memory: Killed process 4821 (java) total-vm:8392104kB, anon-rss:7611232kB, file-rss:0kB, shmem-rss:0kB, UID:1000 pgtables:15004kB oom_score_adj:0
[12345.679210] oom_reaper: reaped process 4821 (java), now anon-rss:0kB, file-rss:0kB, shmem-rss:0kB
```

```text
kernel: java invoked oom-killer: gfp_mask=0x140dca(GFP_HIGHUSER_MOVABLE|__GFP_COMP|__GFP_ZERO), order=0, oom_score_adj=0
```

## Description

The Linux kernel's out-of-memory (OOM) killer is a last-resort mechanism that
selects and terminates a process when the system can no longer satisfy a memory
allocation, even after reclaiming caches and swapping. It is the kernel itself —
not your application — that emits these lines, and they appear in `dmesg` / the
kernel ring buffer and are copied to the journal. The victim is chosen by an
`oom_score` heuristic that favours killing whatever frees the most memory while
respecting `oom_score_adj`. The killed process simply receives `SIGKILL` and
disappears, often with no log of its own.

## Technologies

- linux (kernel memory management, OOM killer)

## Severity

**high** — an unrelated, often critical process can be killed without warning,
producing a partial outage. On a node running many services the OOM killer can
cascade, and a wrongly-tuned `oom_score_adj` can let it kill `sshd` or a database.

## Common Causes

1. A genuine memory leak or unbounded growth in one process (heap, cache, or a
   runaway query) consuming all RAM.
2. No swap (or exhausted swap) so the kernel has no overflow space and reclaims
   to zero almost instantly.
3. Memory overcommit allowing more virtual memory to be promised than physically
   exists, so the shortfall surfaces only at fault time.
4. Too many concurrent workers/threads each with a large resident set.
5. A cgroup/container memory limit being hit (container OOM, exit code 137).

## Root Cause Analysis

When an allocation cannot be served from free pages, the kernel runs direct
reclaim — dropping page cache, writing back dirty pages, swapping anonymous
pages. If reclaim still cannot free a page, `out_of_memory()` is invoked. It
computes `oom_score` per process (proportional to RSS, adjusted by
`oom_score_adj`), picks the highest, and sends `SIGKILL`. The `oom_reaper`
kernel thread then asynchronously frees the victim's anonymous memory. The
process that *triggered* the allocation ("invoked oom-killer") is frequently
**not** the process that gets killed — that is the single most misread part of
these logs.

## Diagnostic Commands

```bash
# Kernel ring buffer with human timestamps — find the OOM event and the victim
dmesg -T | grep -iE 'oom|killed process|out of memory'

# Same from the persistent journal across reboots
journalctl -k -b -1 --no-pager | grep -iE 'oom|killed process'

# Current memory and swap headroom
free -h

# Per-process memory, top consumers first
ps -eo pid,comm,rss,%mem --sort=-rss | head -20

# OOM score the kernel currently assigns a process
cat /proc/<pid>/oom_score /proc/<pid>/oom_score_adj
```

## Expected Results

```text
$ free -h
               total        used        free      shared  buff/cache   available
Mem:           7.8Gi       7.5Gi       110Mi        12Mi       180Mi       95Mi
Swap:             0B          0B          0B
```

`available` near zero with `Swap: 0B` is the classic precondition. The `dmesg`
line names the victim (`Killed process 4821 (java)`) and its `anon-rss`, which
tells you which workload actually exhausted memory.

## Resolution

1. Identify the real consumer from `dmesg` (largest `anon-rss`) and fix the leak,
   cap its heap/cache, or move it to a larger node.
2. Add swap so reclaim has overflow space (this trades latency for survival):

   ```bash
   sudo fallocate -l 4G /swapfile && sudo chmod 600 /swapfile
   sudo mkswap /swapfile && sudo swapon /swapfile
   ```
3. For a containerised service, raise the cgroup limit or right-size the workload
   rather than letting the kernel kill it.
4. Protect critical daemons by lowering their OOM priority, e.g. for a systemd
   unit set `OOMScoreAdjust=-900`. **Risk:** never shield a leaking process this
   way — you only move the kill onto an innocent neighbour.
5. Consider `vm.overcommit_memory=2` with a sane `overcommit_ratio` to make
   allocations fail predictably (with ENOMEM) instead of triggering OOM.

## Validation

```bash
# After the fix, watch available memory stay above a safe margin under load
watch -n5 'free -h; echo; dmesg -T | grep -i oom | tail -3'
# Expect: no new OOM lines and a stable, non-trivial "available" value.
```

## Prevention

- Set memory requests/limits (or systemd `MemoryMax=`) from observed peak usage.
- Always provision some swap on memory-sensitive hosts.
- Alert on `available` memory and on swap-in rate before the killer fires.
- Cap per-service worker counts and per-worker memory (e.g. JVM `-Xmx`).
- Use `OOMScoreAdjust` to bias the killer away from `sshd` and databases.

## Related Errors

- [Linux fork: Cannot allocate memory](./linux-fork-cannot-allocate-memory.md)
- [Linux Kernel panic - not syncing](./linux-kernel-panic-not-syncing.md)

## References

- [Linux kernel: Out-of-memory management](https://docs.kernel.org/admin-guide/sysctl/vm.html)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`linux` · `memory` · `oom` · `kernel` · `production`
