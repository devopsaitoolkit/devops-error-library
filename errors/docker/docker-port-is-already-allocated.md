---
title: "Docker Port Is Already Allocated"
slug: docker-port-is-already-allocated
technologies: [docker]
severity: medium
tags: [docker, networking, ports, bind, production]
related: [docker-oci-runtime-create-failed, docker-cannot-connect-to-docker-daemon]
last_reviewed: 2026-06-27
---

# Docker Port Is Already Allocated

## Error Message

```text
docker: Error response from daemon: driver failed programming external connectivity on endpoint web (abc123...): Bind for 0.0.0.0:8080 failed: port is already allocated.
```

```text
Error starting userland proxy: listen tcp4 0.0.0.0:8080: bind: address already in use
```

## Description

When you publish a port with `-p host:container`, Docker asks the host kernel to
bind the host-side port for its proxy/NAT rules. If another process — another
container, a leftover `docker-proxy`, or an unrelated host service — already holds
that port, the bind fails and the daemon refuses to start the container. The port
is a host-wide resource; only one listener can own a given address:port at a time.

## Technologies

- docker (libnetwork, `docker-proxy`, host networking stack)

## Severity

**medium** — the affected container won't start, but the rest of Docker and the
host are unaffected. It's typically a fast-to-fix conflict rather than an outage.

## Common Causes

1. Another running container already publishes the same host port.
2. A non-Docker host service (nginx, a dev server, another DB) holds the port.
3. A previous container exited uncleanly, leaving a stale `docker-proxy` bound.
4. Two services in the same Compose file map to the same host port.
5. The port is in the ephemeral range and was grabbed by an outbound connection.

## Root Cause Analysis

Docker binds the host port at container start via the userland proxy (or via
iptables/NAT). The kernel enforces exclusivity per `address:port`, returning
`EADDRINUSE` to the second binder. Docker reports this as *port is already
allocated*. The fix is always to identify the current owner of the port: if it's
another container, change one mapping; if it's a host process, stop it or pick a
different host port.

## Diagnostic Commands

```bash
# Which container (if any) already publishes this port
docker ps --format 'table {{.Names}}\t{{.Ports}}' | grep 8080

# Which process on the host owns the port (Docker or otherwise)
ss -ltnp | grep ':8080'

# Inspect the conflicting container's published ports
docker port <container>
```

## Expected Results

```text
$ ss -ltnp | grep ':8080'
LISTEN 0 4096 0.0.0.0:8080 0.0.0.0:* users:(("docker-proxy",pid=2410,fd=4))

# If a non-Docker process owns it:
LISTEN 0 511 0.0.0.0:8080 0.0.0.0:* users:(("nginx",pid=812,fd=6))

$ docker ps --format 'table {{.Names}}\t{{.Ports}}'
NAMES   PORTS
api     0.0.0.0:8080->8080/tcp     # this container already holds 8080
```

## Resolution

1. If another container owns the port, either stop it or remap the new one:

   ```bash
   docker run -p 8081:8080 myimage   # publish on a different host port
   ```
2. If a host process owns it, stop that service or choose a free host port.
3. If a stale `docker-proxy` is lingering after an unclean exit, removing the old
   container clears it:

   ```bash
   docker rm -f <old-container>
   ```
4. In Compose, ensure each service maps to a unique host port and run
   `docker compose down` before `up` to release prior bindings.

## Validation

```bash
docker run -d -p 8080:8080 myimage && docker ps
# Expect the container Up with the port mapping shown and no allocation error.
```

## Prevention

- Reserve a clear host-port scheme per service to avoid overlaps.
- Run `docker compose down` (not just stop) to release published ports.
- Let Docker pick a random host port (`-p 8080`, no host side) for ephemeral runs.
- Avoid publishing ports already used by host daemons; check `ss -ltnp` first.

## Related Errors

- [Docker OCI Runtime Create Failed](./docker-oci-runtime-create-failed.md)
- [Docker Cannot Connect to the Docker Daemon](./docker-cannot-connect-to-docker-daemon.md)

## References

- [Docker networking: published ports](https://docs.docker.com/network/)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`docker` · `networking` · `ports` · `bind` · `production`
