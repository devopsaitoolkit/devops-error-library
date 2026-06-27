---
title: "Docker Cannot Connect to the Docker Daemon"
slug: docker-cannot-connect-to-docker-daemon
technologies: [docker]
severity: high
tags: [docker, daemon, socket, connectivity, production]
related: [permission-denied-docker-socket, oci-runtime-create-failed]
last_reviewed: 2026-06-27
---

# Docker Cannot Connect to the Docker Daemon

## Error Message

```text
Cannot connect to the Docker daemon at unix:///var/run/docker.sock. Is the docker daemon running?
```

```text
error during connect: Get "http://%2F%2F.%2Fpipe%2Fdocker_engine/v1.45/version": open //./pipe/docker_engine: The system cannot find the file specified.
```

## Description

The Docker CLI (`docker`) is a thin client that talks to a separate long-running
server, `dockerd`. This error is emitted by the **client** when it cannot reach
the daemon's API endpoint — by default the Unix socket `/var/run/docker.sock` on
Linux or the named pipe `//./pipe/docker_engine` on Windows. It does not mean
Docker is broken; it means the client could not open a connection to wherever it
expects the daemon to be listening.

## Technologies

- docker (CLI client, `dockerd` daemon, systemd)

## Severity

**high** — no Docker operation works while the client cannot reach the daemon.
On a CI runner or a host whose workloads are managed by Docker, this halts builds
and can take running services with it if the daemon itself has crashed.

## Common Causes

1. The `docker` daemon is not running (stopped, crashed, or never started).
2. `DOCKER_HOST` is set to a host/socket that is wrong or unreachable.
3. The daemon listens on a non-default socket and the client wasn't told about it.
4. The user lacks permission to the socket (this usually surfaces as
   *permission denied* — see related error — but a missing socket reads as this).
5. Inside a container, `/var/run/docker.sock` was not mounted (Docker-in-Docker).

## Root Cause Analysis

The client resolves its endpoint in this order: `-H`/`--host` flag, the
`DOCKER_HOST` environment variable, the active `docker context`, then the
built-in default socket. If the resolved endpoint has no listener — because
`dockerd` is down or the path is wrong — the connect syscall fails and the CLI
prints this message. Distinguishing "daemon down" from "wrong endpoint" is the
whole job: check the service state, then check what endpoint the client is
actually using.

## Diagnostic Commands

```bash
# Is the daemon service up?
systemctl status docker

# What endpoint is the client trying to use?
docker context inspect
echo "$DOCKER_HOST"

# Does the socket exist and who owns it?
ls -l /var/run/docker.sock

# Is anything listening on the socket?
ss -lx | grep docker.sock

# Recent daemon logs (why it failed to start, if it did)
journalctl -u docker --no-pager -n 50
```

## Expected Results

```text
$ systemctl status docker
   Active: inactive (dead)        # daemon is down -> start it

$ ls -l /var/run/docker.sock
ls: cannot access '/var/run/docker.sock': No such file or directory

# Healthy host:
$ systemctl status docker
   Active: active (running)
$ ss -lx | grep docker.sock
u_str LISTEN 0 4096 /var/run/docker.sock 12345 * 0
```

## Resolution

1. If the service is down, start and enable it:

   ```bash
   sudo systemctl start docker
   sudo systemctl enable docker
   ```
2. If `dockerd` fails to start, read `journalctl -u docker` for the real reason
   (corrupt `daemon.json`, a port/socket conflict, storage-driver error) and fix
   that before retrying.
3. If `DOCKER_HOST` or the active context points at the wrong place, unset/correct
   it:

   ```bash
   unset DOCKER_HOST
   docker context use default
   ```
4. Inside a container that needs the host daemon, mount the socket:
   `-v /var/run/docker.sock:/var/run/docker.sock`.

## Validation

```bash
docker info
# Expect server fields (Server Version, Storage Driver) printed without error.
```

## Prevention

- Enable the service so it survives reboots: `systemctl enable docker`.
- Validate `daemon.json` with `dockerd --validate` before restarting in CI.
- Standardize the endpoint via `docker context` rather than ad-hoc `DOCKER_HOST`.
- Add a `docker info` readiness check at the top of CI jobs that use Docker.

## Related Errors

- [Docker Permission Denied on the Docker Socket](./docker-permission-denied-docker-socket.md)
- [Docker OCI Runtime Create Failed](./docker-oci-runtime-create-failed.md)

## References

- [Docker daemon documentation](https://docs.docker.com/config/daemon/)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`docker` · `daemon` · `socket` · `connectivity` · `production`
