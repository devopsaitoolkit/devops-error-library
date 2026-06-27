---
title: "Linux fork: Cannot allocate memory"
slug: linux-fork-cannot-allocate-memory
technologies: [linux]
severity: high
tags: [linux, memory, process-limits, enomem, production]
related: [linux-out-of-memory-oom-killer, linux-too-many-open-files]
last_reviewed: 2026-06-27
---

# Linux fork: Cannot allocate memory

## Error Message

```text
-bash: fork: Cannot allocate memory
```

```text
sshd[1042]: fork: retry: Resource temporarily unavailable
runtime: failed to create new OS thread (have 8 already; errno=11)
```

## Description

`fork: Cannot allocate memory` is what userspace prints when `fork()`/`clone()`
fails with `ENOMEM` (errno 12), and the closely related `Resource temporarily
unavailable` is `EAGAIN` (errno 11) from hitting a process/thread limit. Despite
the wording, this is often **not** a RAM shortage — it frequently means the
system or a cgroup has hit its **process/thread ceiling** (`pid_max`, the
`RLIMIT_NPROC` per-user process limit, or a cgroup `pids.max`). Because creating
new processes is broken, even basic commands (`ls`, `ssh`) may fail, making the
host feel completely stuck while top-level services still run.

## Technologies

- linux (process creation, cgroups, resource limits)

## Severity

**high** — when forking fails, shells, cron jobs, SSH logins, and any service
that spawns workers all break. It is especially nasty because the tools you'd use
to debug (`ssh`, new shells, `ps` via a wrapper) can themselves fail to fork,
risking a host you cannot log into.

## Common Causes

1. A process/thread **leak** (fork bomb, runaway worker spawn, leaked threads)
   filling the global PID space or the per-user `RLIMIT_NPROC`.
2. A cgroup `pids.max` reached (common in containers — "OOM"-like but it's PIDs).
3. True memory exhaustion: not enough free + swap to copy-on-write a new address
   space (overlaps with the OOM situation).
4. `kernel.pid_max` set too low for a high-concurrency workload.
5. `RLIMIT_NPROC` (`ulimit -u`) too low for the service user.

## Root Cause Analysis

`fork()` must (a) allocate kernel structures and a (copy-on-write) page-table for
the child, and (b) obtain a free PID under `kernel.pid_max` while respecting the
caller's `RLIMIT_NPROC` and any cgroup `pids.max`. If memory cannot be reserved
it returns `ENOMEM`; if a process/thread *count* limit is hit it returns
`EAGAIN`. The two errnos point at different fixes: `ENOMEM` → free memory or add
swap; `EAGAIN` → raise the relevant process/thread limit. Note each thread also
counts against `RLIMIT_NPROC`, so a thread-leaking app trips the *process* limit.

## Diagnostic Commands

```bash
# Total tasks (processes + threads) vs the global ceiling
ps -eLf | wc -l ; cat /proc/sys/kernel/pid_max

# Per-user process counts — find the user that's leaking
ps -eo user= | sort | uniq -c | sort -rn | head

# The per-user process limit the shell/service has
ulimit -u

# Memory + swap headroom (rules ENOMEM in or out)
free -h

# In a container/cgroup v2: current vs max PIDs
cat /sys/fs/cgroup/pids.current /sys/fs/cgroup/pids.max 2>/dev/null
```

## Expected Results

```text
$ ps -eLf | wc -l
32768
$ cat /proc/sys/kernel/pid_max
32768

$ ps -eo user= | sort | uniq -c | sort -rn | head
  29110 appuser
```

Total tasks pinned at `pid_max`, dominated by one user, points to a process/
thread leak (`EAGAIN`). If instead `free -h` shows near-zero available + no swap,
it is a genuine `ENOMEM`.

## Resolution

1. Identify and stop the leaking process tree. If you can still get a shell, kill
   the offending parent:

   ```bash
   pkill -TERM -u appuser <leaking-process>   # then fix the spawn loop
   ```
   If you cannot fork a new shell, use a built-in (`exec`) or the console/OOB.
2. For `EAGAIN`, raise the right limit: `RLIMIT_NPROC` via
   `/etc/security/limits.conf` (`appuser hard nproc 8192`) or the systemd unit
   (`TasksMax=8192`), or raise `kernel.pid_max` for global pressure.
3. For a container, raise `pids.max` (or the orchestrator's PID limit).
4. For genuine `ENOMEM`, free/right-size memory and add swap (see the OOM error).
5. Add `TasksMax=` to runaway services so one cannot starve the whole host.

## Validation

```bash
ps -eLf | wc -l                 # task count drops well below pid_max
bash -c 'echo fork OK'          # forking a child succeeds
ulimit -u                       # the raised nproc limit is in effect
```

## Prevention

- Set `TasksMax=` on every service so a fork bomb is contained.
- Monitor process/thread counts per user and per cgroup; alert before the cap.
- Fix thread/process leaks at the source; bound worker-pool sizes.
- Keep `pid_max` and `RLIMIT_NPROC` sized for real concurrency.
- Reserve headroom: never run a host at 100% of `pid_max`.

## Related Errors

- [Linux Out of Memory (OOM Killer)](./linux-out-of-memory-oom-killer.md)
- [Linux Too many open files](./linux-too-many-open-files.md)

## References

- [fork(2) error semantics](https://man7.org/linux/man-pages/man2/fork.2.html)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`linux` · `memory` · `process-limits` · `enomem` · `production`
