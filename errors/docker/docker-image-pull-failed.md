---
title: "Docker Image Pull Failed"
slug: docker-image-pull-failed
technologies: [docker]
severity: high
tags: [docker, registry, network, pull, production]
related: [docker-pull-access-denied, docker-no-space-left-on-device]
last_reviewed: 2026-06-27
---

# Docker Image Pull Failed

## Error Message

```text
Error response from daemon: Get "https://registry-1.docker.io/v2/": net/http: request canceled while waiting for connection (Client.Timeout exceeded while awaiting headers)
```

```text
failed to resolve reference "registry.example.com/app:1.2": failed to do request: Head "https://registry.example.com/v2/app/manifests/1.2": dial tcp 10.0.0.5:443: connect: connection refused
```

## Description

This is the general "the pull did not complete" failure, distinct from the precise
`denied` (auth) and `manifest unknown` (bad reference) cases. The daemon could not
fetch the image because of a transport-level problem: it couldn't reach the
registry, the TLS handshake failed, a rate limit was hit, or a layer download was
interrupted. The exact wrapped error (`timeout`, `connection refused`, `x509`,
`toomanyrequests`) tells you which.

## Technologies

- docker (registry client, host networking, TLS, proxy)

## Severity

**high** — workloads that need a fresh image can't start or update, which blocks
deploys and autoscaling. If the image is already cached, running containers are
unaffected.

## Common Causes

1. Network/DNS/firewall blocks reaching the registry (proxy or egress rules).
2. Docker Hub anonymous **rate limit** (`toomanyrequests`).
3. TLS/cert failure against a private registry (`x509: certificate signed by unknown authority`).
4. Registry is down or overloaded; layer download times out mid-pull.
5. Local disk fills during extraction (see *no space left on device*).

## Root Cause Analysis

The daemon first does a `HEAD`/`GET` on `/v2/` to negotiate, then fetches the
manifest and pulls layers. A failure at the connection stage (`dial tcp`,
`timeout`, `connection refused`) is networking/registry availability; an `x509`
error is trust configuration; `429 toomanyrequests` is rate limiting; an `ENOSPC`
mid-extract is local disk. Reading the wrapped Go HTTP error in the daemon log
pinpoints which layer is responsible.

## Diagnostic Commands

```bash
# The full wrapped transport error from the daemon
journalctl -u docker --no-pager -n 50

# Can the host even reach the registry endpoint?
curl -sSI https://registry-1.docker.io/v2/ | head

# DNS resolution for the registry host
getent hosts registry.example.com

# Disk headroom for extraction (rules out ENOSPC masquerading as a pull failure)
df -h /var/lib/docker
```

## Expected Results

```text
$ curl -sSI https://registry-1.docker.io/v2/
HTTP/1.1 401 Unauthorized        # reachable (401 is normal here) -> network OK

# Rate limited:
HTTP/1.1 429 Too Many Requests

# Unreachable:
curl: (7) Failed to connect to registry.example.com port 443: Connection refused
```

## Resolution

1. For a network block, fix egress/DNS or configure the daemon's HTTP proxy in
   `/etc/systemd/system/docker.service.d/http-proxy.conf`, then
   `systemctl daemon-reload && systemctl restart docker`.
2. For Docker Hub `toomanyrequests`, authenticate (`docker login`) to raise the
   limit, or pull through a registry mirror / private cache.
3. For `x509` errors, install the registry CA into the host trust store (or
   `/etc/docker/certs.d/<registry>/ca.crt`) and restart the daemon.
4. For transient timeouts, retry; for `ENOSPC`, prune disk (see related error).

## Validation

```bash
docker pull registry.example.com/app:1.2
# Expect layers to download and "Status: Downloaded newer image" with no transport error.
```

## Prevention

- Run a pull-through registry mirror to dodge Hub rate limits and reduce egress.
- Authenticate pulls in CI even for public images to get higher rate limits.
- Manage private-registry CAs via configuration management, not by hand.
- Alert on `/var/lib/docker` disk so extraction never fails for space.

## Related Errors

- [Docker Pull Access Denied](./docker-pull-access-denied.md)
- [Docker No Space Left on Device](./docker-no-space-left-on-device.md)

## References

- [Docker: registry HTTP proxy and mirrors](https://docs.docker.com/config/daemon/)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`docker` · `registry` · `network` · `pull` · `production`
