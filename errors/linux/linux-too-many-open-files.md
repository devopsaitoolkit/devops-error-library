---
title: "Linux Too many open files"
slug: linux-too-many-open-files
technologies: [linux]
severity: high
tags: [linux, limits, file-descriptors, emfile, production]
related: [linux-systemd-failed-to-start-unit, linux-fork-cannot-allocate-memory]
last_reviewed: 2026-06-27
---

# Linux Too many open files

## Error Message

```text
Too many open files
```

```text
java.net.SocketException: Too many open files (errno 24)
nginx: [alert] accept4() failed (24: Too many open files)
```

## Description

`Too many open files` is the userspace text for the `EMFILE`/`ENFILE` errno
(24). It is returned by `open()`, `socket()`, `accept()`, `pipe()`, and similar
calls when a file-descriptor limit is reached. There are two distinct ceilings:
a **per-process** limit (`RLIMIT_NOFILE`, the `ulimit -n` soft/hard values) which
raises `EMFILE`, and a **system-wide** limit (`fs.file-max`) which raises
`ENFILE`. Network-heavy services hit this constantly because every socket,
including idle keep-alives, consumes a descriptor.

## Technologies

- linux (process resource limits, VFS file table)

## Severity

**high** — a service that cannot open new sockets stops accepting connections
while continuing to run, so health checks may pass while real traffic is
refused. For a reverse proxy or database this is a partial-to-full outage that
is easy to misdiagnose as a network problem.

## Common Causes

1. A file-descriptor leak — the app opens files/sockets without closing them, so
   the count climbs until the limit is hit.
2. A per-process `ulimit -n` (or systemd `LimitNOFILE=`) set too low for a
   high-connection workload (default soft limit is often 1024).
3. Genuinely high concurrency (thousands of simultaneous connections) exceeding
   a reasonable but finite limit.
4. The system-wide `fs.file-max` reached across all processes.
5. Inotify/epoll watches consuming descriptors at scale.

## Root Cause Analysis

The kernel keeps a per-process file-descriptor table capped by `RLIMIT_NOFILE`.
Each `open()`/`socket()` consumes the lowest free slot; when the table is full,
the syscall returns `EMFILE`. Crucially, `ulimit` is inherited from the process
that launched the service — a value set in your shell does **not** apply to a
systemd-managed daemon, whose limit comes from `LimitNOFILE=` in the unit. A
slow leak shows as a descriptor count that only ever rises across the process's
lifetime; true concurrency shows as a count that tracks active connections.

## Diagnostic Commands

```bash
# Soft and hard per-process limits in the current shell
ulimit -Sn ; ulimit -Hn

# The limits the RUNNING process actually has (systemd units differ from shell)
cat /proc/<pid>/limits | grep -i 'open files'

# How many descriptors the process currently holds
ls /proc/<pid>/fd | wc -l

# What those fds point to — reveals a leak (e.g. thousands of CLOSE_WAIT sockets)
ls -l /proc/<pid>/fd | awk '{print $NF}' | sort | uniq -c | sort -rn | head

# System-wide allocated vs maximum file handles
cat /proc/sys/fs/file-nr   # allocated  unused  max
```

## Expected Results

```text
$ cat /proc/4821/limits | grep -i 'open files'
Max open files            1024                 1024                 files

$ ls /proc/4821/fd | wc -l
1024
```

An fd count pinned at the limit confirms the diagnosis. If `ls -l /proc/<pid>/fd`
shows thousands of `socket:[...]` in `CLOSE_WAIT`, the app is leaking sockets it
never closes — raising the limit only delays the failure.

## Resolution

1. Raise the limit for the **running service** correctly. For a systemd unit:

   ```ini
   # /etc/systemd/system/myapp.service.d/limits.conf
   [Service]
   LimitNOFILE=65535
   ```
   Then `systemctl daemon-reload && systemctl restart myapp`.
2. For login sessions, set it in `/etc/security/limits.conf`
   (`* soft nofile 65535` / `* hard nofile 65535`).
3. If `fs.file-max` is the ceiling, raise it:
   `sysctl -w fs.file-max=2000000` and persist in `/etc/sysctl.d/`.
4. Fix the underlying leak — close descriptors/sockets, use connection pools with
   bounded size, and reuse keep-alive connections. **Risk:** raising limits
   without fixing a leak just postpones the outage.

## Validation

```bash
cat /proc/<pid>/limits | grep 'open files'   # new higher limit in effect
watch -n5 'ls /proc/<pid>/fd | wc -l'        # count stabilises, not climbing
```

## Prevention

- Set `LimitNOFILE=` explicitly in unit files for high-connection services.
- Load-test to size limits against real peak concurrency plus headroom.
- Add fd-usage metrics (`process_open_fds`) and alert near the limit.
- Code defensively: `defer close()`, bounded pools, and CLOSE_WAIT monitoring.

## Related Errors

- [Linux systemd Failed to start unit](./linux-systemd-failed-to-start-unit.md)
- [Linux fork: Cannot allocate memory](./linux-fork-cannot-allocate-memory.md)

## References

- [getrlimit / RLIMIT_NOFILE man page](https://man7.org/linux/man-pages/man2/getrlimit.2.html)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`linux` · `limits` · `file-descriptors` · `emfile` · `production`
