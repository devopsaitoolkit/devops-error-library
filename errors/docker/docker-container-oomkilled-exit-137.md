---
title: "Docker Container OOMKilled (Exit 137)"
slug: docker-container-oomkilled-exit-137
technologies: [docker]
severity: high
tags: [docker, memory, oomkilled, cgroups, production]
related: [docker-no-space-left-on-device, docker-oci-runtime-create-failed]
last_reviewed: 2026-06-27
---

# Docker Container OOMKilled (Exit 137)

## Error Message

```text
$ docker ps -a
CONTAINER ID   IMAGE        STATUS                       NAMES
a1b2c3d4e5f6   myorg/api    Exited (137) 12 seconds ago  api
```

```text
$ docker inspect api --format '{{.State.OOMKilled}} {{.State.ExitCode}}'
true 137
```

## Description

Exit code `137` means the container's main process received `SIGKILL`
(128 + 9 = 137). When `State.OOMKilled` is also `true`, the kill came from the
kernel's out-of-memory killer because the container exceeded its memory cgroup
limit (`--memory`) — or the host ran out of memory overall. The process gets no
chance to clean up; it is hard-killed and the container exits. This is the
container-level analog of the Kubernetes OOMKilled condition.

## Technologies

- docker (memory cgroups, Linux OOM killer)

## Severity

**high** — the container dies abruptly mid-work, risking dropped requests or
partial writes. With a restart policy it can enter a kill/restart loop if the
limit is simply too low for the workload.

## Common Causes

1. The container's memory limit (`--memory`) is lower than its real working set.
2. A genuine memory leak in the application that grows until it hits the cap.
3. A workload spike (large request, big batch job) that exceeds the limit briefly.
4. JVM/Node/Go heap settings that ignore the cgroup limit and over-allocate.
5. Host-wide memory pressure killing the heaviest process even without a per-container limit.

## Root Cause Analysis

Docker places each container in a memory cgroup with `memory.max` set from
`--memory`. When the cgroup's usage hits that ceiling and reclaim can't free
enough, the kernel OOM killer terminates a process in the cgroup with `SIGKILL`;
the container exits 137 and the daemon records `OOMKilled: true`. Distinguish a
**too-low limit** (workload is legitimately bigger) from a **leak** (usage climbs
unbounded over time) by watching `docker stats` against the limit over the
container's lifetime.

## Diagnostic Commands

```bash
# Confirm it was an OOM kill, not a plain crash
docker inspect api --format '{{.State.OOMKilled}} {{.State.ExitCode}}'

# The configured memory limit for the container
docker inspect api --format '{{.HostConfig.Memory}}'

# Live memory usage vs limit (watch it approach the cap)
docker stats --no-stream api

# Kernel OOM-killer lines naming the killed process
journalctl -k --no-pager | grep -i 'killed process'
```

## Expected Results

```text
$ docker inspect api --format '{{.State.OOMKilled}} {{.State.ExitCode}}'
true 137

$ docker stats --no-stream api
CONTAINER  MEM USAGE / LIMIT     MEM %
api        511.8MiB / 512MiB     99.96%      # pinned at the cap -> OOM

$ journalctl -k | grep -i 'killed process'
... Memory cgroup out of memory: Killed process 4123 (node) total-vm:...
```

## Resolution

1. If the limit is genuinely too small, raise it to match observed peak usage
   plus headroom:

   ```bash
   docker run --memory=1g --memory-swap=1g myorg/api
   ```
2. If it's a leak, fix the application; a higher limit only delays the kill.
3. Make runtimes cgroup-aware so they size heaps to the limit:
   - JVM: `-XX:MaxRAMPercentage=75` (modern JDKs honor cgroup limits).
   - Node: `--max-old-space-size=<MB>` below the container limit.
4. For host-wide pressure, add memory or reduce co-located workloads; set
   per-container limits so one process can't starve the host.

## Validation

```bash
docker stats --no-stream api
# Expect MEM % to stabilize well under 100% under load; State.OOMKilled stays false.
```

## Prevention

- Set `--memory` from measured peak usage, not guesses; load-test to find it.
- Make every runtime cgroup-aware (heap sized below the container limit).
- Alert on container memory nearing its limit before the kill happens.
- Track memory over time in CI/staging to catch leaks before production.

## Related Errors

- [Docker No Space Left on Device](./docker-no-space-left-on-device.md)
- [Docker OCI Runtime Create Failed](./docker-oci-runtime-create-failed.md)

## References

- [Docker: runtime resource constraints (memory)](https://docs.docker.com/config/containers/resource_constraints/)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`docker` · `memory` · `oomkilled` · `cgroups` · `production`
