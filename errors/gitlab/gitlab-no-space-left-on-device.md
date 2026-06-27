---
title: "GitLab CI — No Space Left on Device"
slug: gitlab-no-space-left-on-device
technologies: [gitlab]
severity: high
tags: [gitlab, runner, disk, storage, production]
related: [gitlab-prepare-environment-exit-status-1, gitlab-cannot-connect-to-docker-daemon-dind]
last_reviewed: 2026-06-27
---

# GitLab CI — No Space Left on Device

## Error Message

```text
$ docker build -t app:ci .
write /var/lib/docker/tmp/buildkit-mount123/layer.tar: no space left on device
ERROR: Job failed: exit code 1
```

```text
fatal: write error: No space left on device
error: failed to write object
tar: write error: No space left on device
```

## Description

`No space left on device` (errno `ENOSPC`) means a write failed because the
underlying filesystem — or its inodes — filled up. On GitLab runners this almost
always means the **runner host's** disk is full: accumulated build directories,
Docker images/layers/volumes, the cache, or job artifacts have not been cleaned
up. It can also be the **DinD daemon's** storage filling during `docker build`.
The job that happens to be running when the disk hits 100% is the one that fails,
even if it didn't cause the buildup.

## Technologies

- gitlab (GitLab Runner host, Docker storage)

## Severity

**high** — once a runner's disk is full, *every* job on it fails until space is
reclaimed, taking the runner out of service.

## Common Causes

1. Accumulated Docker artifacts: dangling images, stopped containers, and unused
   volumes never pruned on the runner host.
2. Stale build directories under the runner's `builds_dir` from previous jobs.
3. Large or unbounded **cache** and **artifacts** growing over time.
4. A single job writing a huge file/layer (big image build, large test output)
   that exhausts a small volume.
5. **Inode** exhaustion from millions of tiny files even when bytes are free.

## Root Cause Analysis

The filesystem returns `ENOSPC` when there are no free blocks (or no free inodes)
to satisfy a write. GitLab Runner keeps per-job build directories, caches, and —
for Docker/DinD executors — image layers and volumes on the host. Without pruning,
these grow until the volume fills. Because the failure is whichever write happens
to cross the threshold, the error appears in an unrelated job (a `git fetch`, a
`tar`, a layer write), which is why it is easy to misattribute. Checking `df` and
`df -i` on the runner host immediately confirms the real cause.

## Diagnostic Commands

```bash
# Free space AND inodes on the runner host (both can trigger ENOSPC)
df -h
df -i

# Where the runner stores builds/cache (from config)
grep -nE 'builds_dir|cache_dir|\[runners\]' /etc/gitlab-runner/config.toml

# Biggest consumers under Docker and the runner build dir
docker system df -v 2>/dev/null
du -xhd1 /var/lib/docker /home/gitlab-runner/builds 2>/dev/null | sort -h | tail

# Confirm the message in recent runner logs
journalctl -u gitlab-runner --since "30 min ago" --no-pager | grep -i 'no space'
```

## Expected Results

```text
# Disk full:
$ df -h /var/lib/docker
Filesystem      Size  Used Avail Use% Mounted on
/dev/nvme0n1p1  100G  100G     0 100% /

# Or inodes full while bytes look fine:
$ df -i
/dev/nvme0n1p1  6.5M  6.5M  0    100% /
```

## Resolution

1. Reclaim Docker space (safe, removes only unused objects):

   ```bash
   docker system prune -af --volumes      # dangling images, stopped containers, unused volumes
   ```
2. Remove stale runner build directories (only when no jobs are running):

   ```bash
   sudo find /home/gitlab-runner/builds -mindepth 1 -maxdepth 1 -type d -mtime +2 -exec rm -rf {} +
   ```
3. Bound cache/artifacts: set `expire_in` on artifacts and cap cache size; clear
   old runner cache directories.
4. Grow the volume if the runner is legitimately undersized, or move
   `/var/lib/docker` to a larger disk.
5. For inode exhaustion, delete the directories with the most files (often old
   `node_modules`/cache) rather than chasing bytes.

## Validation

```bash
df -h && df -i      # Use% well below 100 on both
# Re-run a pipeline; the previously failing write step now completes, exit 0.
```

## Prevention

- Schedule periodic `docker system prune -af` and build-dir cleanup on every
  runner (cron/systemd timer).
- Set `expire_in` on all `artifacts:` and a sane cache policy.
- Alert on runner disk and inode usage crossing ~80%, before jobs start failing.

## Related Errors

- [GitLab Runner — Prepare Environment: Exit Status 1](./gitlab-prepare-environment-exit-status-1.md)
- [GitLab DinD — Cannot Connect to the Docker Daemon](./gitlab-cannot-connect-to-docker-daemon-dind.md)

## References

- [GitLab Runner: Advanced configuration](https://docs.gitlab.com/runner/configuration/advanced-configuration.html)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`gitlab` · `runner` · `disk` · `storage` · `production`
