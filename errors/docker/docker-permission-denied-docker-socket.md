---
title: "Docker Permission Denied on the Docker Socket"
slug: docker-permission-denied-docker-socket
technologies: [docker]
severity: medium
tags: [docker, socket, permissions, security, production]
related: [docker-cannot-connect-to-docker-daemon, oci-runtime-create-failed]
last_reviewed: 2026-06-27
---

# Docker Permission Denied on the Docker Socket

## Error Message

```text
permission denied while trying to connect to the Docker daemon socket at unix:///var/run/docker.sock: Get "http://%2Fvar%2Frun%2Fdocker.sock/v1.45/containers/json": dial unix /var/run/docker.sock: connect: permission denied
```

```text
Got permission denied while trying to connect to the Docker daemon socket
```

## Description

The Docker daemon socket `/var/run/docker.sock` is owned by `root` and the
`docker` group, with mode `0660`. The CLI client connects to it as the invoking
user. When that user is neither `root` nor a member of the `docker` group, the
kernel denies the `connect()` on the socket and the client reports *permission
denied*. Unlike "cannot connect", the daemon is running fine — the caller simply
isn't authorized to talk to it.

## Technologies

- docker (Unix socket, group permissions)

## Severity

**medium** — Docker works for privileged users, so this is usually a per-user or
CI-runner setup gap rather than an outage. Note that granting socket access is
effectively granting root on the host, so it is also a security-relevant decision.

## Common Causes

1. The user is not in the `docker` group.
2. The user *was* added to `docker` but their current shell/session predates the
   change, so the new group membership hasn't taken effect.
3. A CI runner or service runs as an unprivileged user without group access.
4. The socket was bind-mounted into a container whose process UID has no access.

## Root Cause Analysis

Group membership is evaluated at login/session creation. Running
`usermod -aG docker $USER` updates `/etc/group`, but the running shell still
carries the old supplementary-group set from when it started. The kernel checks
the socket's `0660 root:docker` permissions against that stale set and denies the
connection until a fresh session is started. So a "permission denied" right after
adding the user is almost always a not-re-logged-in problem, not a misconfiguration.

## Diagnostic Commands

```bash
# Socket ownership and mode (expect: srw-rw---- root docker)
ls -l /var/run/docker.sock

# Groups the CURRENT session actually has
id

# Is the user listed in the docker group on disk?
getent group docker

# Confirm the daemon is up (rules out "cannot connect")
systemctl is-active docker
```

## Expected Results

```text
$ ls -l /var/run/docker.sock
srw-rw---- 1 root docker 0 Jun 27 05:00 /var/run/docker.sock

$ id
uid=1001(deploy) gid=1001(deploy) groups=1001(deploy)   # no "docker" -> denied

$ getent group docker
docker:x:998:deploy   # user is in the group on disk, but session is stale
```

## Resolution

1. Add the user to the `docker` group:

   ```bash
   sudo usermod -aG docker "$USER"
   ```
2. Apply the new group **in this session** without a full logout:

   ```bash
   newgrp docker      # or log out and back in / restart the service
   ```
3. For a systemd service, set `Group=docker` (or `SupplementaryGroups=docker`)
   in the unit and `systemctl daemon-reload && systemctl restart <svc>`.
4. If you must avoid granting host-root via the socket, run Docker in rootless
   mode instead of broadening socket access.

## Validation

```bash
id | grep -o docker        # docker now appears in groups
docker ps                  # lists containers with no permission error
```

## Prevention

- Bake `docker` group membership into host/runner provisioning (cloud-init, AMI).
- Treat `docker` group membership as root-equivalent in your access reviews.
- Prefer rootless Docker for untrusted or shared multi-tenant hosts.

## Related Errors

- [Docker Cannot Connect to the Docker Daemon](./docker-cannot-connect-to-docker-daemon.md)
- [Docker OCI Runtime Create Failed](./docker-oci-runtime-create-failed.md)

## References

- [Docker post-install: manage Docker as a non-root user](https://docs.docker.com/engine/install/linux-postinstall/)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`docker` · `socket` · `permissions` · `security` · `production`
