---
title: "GitLab DinD — Cannot Connect to the Docker Daemon"
slug: gitlab-cannot-connect-to-docker-daemon-dind
technologies: [gitlab]
severity: high
tags: [gitlab, ci, docker, dind, production]
related: [gitlab-prepare-environment-exit-status-1, gitlab-registry-401-unauthorized]
last_reviewed: 2026-06-27
---

# GitLab DinD — Cannot Connect to the Docker Daemon

## Error Message

```text
$ docker info
Cannot connect to the Docker daemon at unix:///var/run/docker.sock. Is the docker daemon running?
ERROR: Job failed: exit code 1
```

```text
error during connect: Get "http://docker:2375/v1.24/info": dial tcp: lookup docker on 10.0.0.10:53: no such host
```

## Description

This error appears in jobs that run `docker build`/`docker push` using the
Docker-in-Docker (DinD) pattern. The Docker **client** in the job cannot reach a
Docker **daemon**. Either no `docker:dind` service was started, the
`DOCKER_HOST`/TLS settings are wrong, or the client is looking at a local
`unix:///var/run/docker.sock` that does not exist inside the container. DinD
requires a `services:` daemon plus correct host/TLS variables wired between client
and daemon.

## Technologies

- gitlab (GitLab Runner, Docker executor, DinD service)

## Severity

**high** — image build/push jobs fail entirely, blocking any pipeline that
packages containers for release.

## Common Causes

1. The `docker:dind` **service is not declared** under `services:`, so there is no
   daemon to connect to.
2. `DOCKER_HOST` / `DOCKER_TLS_CERTDIR` mismatch — TLS enabled on one side but not
   the other (the classic `tcp://docker:2375` vs `2376` + certs confusion).
3. The runner is not configured with `privileged = true` (DinD needs it) or lacks
   the host `/certs` volume.
4. The job assumes `unix:///var/run/docker.sock` but no socket is mounted.
5. DNS for the `docker` service alias is unavailable (custom network / FF off).

## Root Cause Analysis

In DinD, GitLab starts a sidecar container from the `docker:dind` image that runs
`dockerd` and is reachable at the network alias `docker`. The job's `docker` CLI
must point at that daemon via `DOCKER_HOST=tcp://docker:2376` with TLS, or
`tcp://docker:2375` without. Modern `docker:dind` enables TLS by default and
publishes certs under `DOCKER_TLS_CERTDIR=/certs`; if the client doesn't mount
`/certs/client` and use port 2376, the handshake fails. If `services:` is missing
entirely, there is simply no daemon and the client falls back to the non-existent
local socket — hence "Cannot connect … unix:///var/run/docker.sock." DinD also
requires the runner to run the helper container **privileged**.

## Diagnostic Commands

```bash
# Confirm the job declares the dind service and the TLS/host variables
grep -nE 'services:|docker:dind|DOCKER_HOST|DOCKER_TLS_CERTDIR|DOCKER_DRIVER' .gitlab-ci.yml

# Confirm the runner runs containers privileged (required for DinD)
grep -nE 'privileged|volumes|\[runners.docker\]' /etc/gitlab-runner/config.toml

# From a debug session inside the job: is the daemon reachable?
docker info                              # client/daemon versions if connected
getent hosts docker                      # the dind service alias should resolve
ls -la /certs/client 2>/dev/null         # TLS certs present when TLS is on

# Runner-side logs for the service container
journalctl -u gitlab-runner --since "15 min ago" --no-pager | grep -i dind
```

## Expected Results

```text
# Broken (no service / wrong host):
Cannot connect to the Docker daemon at unix:///var/run/docker.sock

# Healthy:
$ docker info
Server Version: 25.x
$ getent hosts docker
10.0.x.x   docker
```

## Resolution

1. Declare the DinD service and wire TLS correctly:

   ```yaml
   build-image:
     image: docker:25
     services: [docker:25-dind]
     variables:
       DOCKER_HOST: tcp://docker:2376
       DOCKER_TLS_CERTDIR: "/certs"
       DOCKER_CERT_PATH: "/certs/client"
       DOCKER_TLS_VERIFY: "1"
     script:
       - docker info
       - docker build -t "$CI_REGISTRY_IMAGE:$CI_COMMIT_SHA" .
   ```
   To disable TLS instead, set `DOCKER_TLS_CERTDIR: ""` and
   `DOCKER_HOST: tcp://docker:2375` (less secure).
2. Configure the runner with `privileged = true`:

   ```toml
   [runners.docker]
     privileged = true
     volumes = ["/certs/client", "/cache"]
   ```
   then `sudo systemctl restart gitlab-runner`.
3. Match client major version to the dind image to avoid API-version skew.

## Validation

```bash
docker info     # inside the job: prints both Client and Server sections, exit 0
docker build .  # proceeds past the daemon connection step
```

## Prevention

- Keep a shared CI template for image builds with the DinD/TLS variables baked in.
- Pin `docker` and `docker:*-dind` to the same major version.
- Where the security model allows, prefer rootless builders (BuildKit/Kaniko) to
  avoid privileged DinD entirely.

## Related Errors

- [GitLab Runner — Prepare Environment: Exit Status 1](./gitlab-prepare-environment-exit-status-1.md)
- [GitLab CI — Registry 401 Unauthorized](./gitlab-registry-401-unauthorized.md)

## References

- [GitLab: Use Docker to build Docker images (DinD)](https://docs.gitlab.com/ee/ci/docker/using_docker_build.html)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`gitlab` · `ci` · `docker` · `dind` · `production`
