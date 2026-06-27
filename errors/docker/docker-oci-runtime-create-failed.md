---
title: "Docker OCI Runtime Create Failed"
slug: docker-oci-runtime-create-failed
technologies: [docker]
severity: high
tags: [docker, runc, oci, container-start, production]
related: [docker-invalid-mount-config-for-type-bind, docker-cannot-connect-to-docker-daemon]
last_reviewed: 2026-06-27
---

# Docker OCI Runtime Create Failed

## Error Message

```text
docker: Error response from daemon: failed to create task for container: failed to create shim task: OCI runtime create failed: runc create failed: unable to start container process: exec: "/app/start.sh": stat /app/start.sh: no such file or directory: unknown.
```

```text
OCI runtime create failed: runc create failed: unable to start container process: exec: "node": executable file not found in $PATH: unknown
```

## Description

This error comes from the low-level OCI runtime (`runc` by default) that the
daemon invokes to actually create and start the container process. The image
pulled fine and the container was created, but `runc` failed at the moment it
tried to set up the namespaces/cgroups and `exec` the entrypoint. The text after
`unable to start container process` is the real diagnosis — most often a missing
or non-executable binary, a bad mount, or an unsupported runtime setting.

## Technologies

- docker (containerd shim, `runc` OCI runtime)

## Severity

**high** — the container never reaches a running state, so the workload is down.
In an orchestrated setting it produces a restart loop because every start attempt
fails identically.

## Common Causes

1. The entrypoint/command binary does not exist in the image or isn't on `$PATH`.
2. The entrypoint exists but is not executable (missing `+x` bit), or has CRLF
   line endings / a wrong shebang.
3. A bind/volume mount path is invalid or a mounted file shadows the binary.
4. A device, cgroup, or seccomp/AppArmor constraint blocks process creation.
5. Architecture mismatch — the binary is for a different CPU arch than the host.

## Root Cause Analysis

`runc` performs the final `execve()` of the configured entrypoint inside the new
namespaces. If the target path can't be `stat`'d, isn't executable, or isn't a
valid binary for the host architecture, `execve` fails and `runc` bubbles the
errno back up through containerd to the daemon. Because this happens *after*
create, the failure is about the container's runtime config and filesystem, not
about pulling or connectivity. The exact `exec:` clause names the offending path.

## Diagnostic Commands

```bash
# The full daemon-side error with the exact failing exec path
journalctl -u docker --no-pager -n 50

# Inspect what entrypoint/cmd the container was created with
docker inspect <container> --format '{{.Config.Entrypoint}} {{.Config.Cmd}}'

# Verify the binary exists/executable in the image filesystem
docker run --rm --entrypoint sh <image> -c 'ls -l /app/start.sh; command -v node'

# Confirm image architecture matches the host
docker image inspect <image> --format '{{.Architecture}}'
uname -m
```

## Expected Results

```text
$ docker run --rm --entrypoint sh <image> -c 'ls -l /app/start.sh'
ls: /app/start.sh: No such file or directory      # missing entrypoint

# or, not executable:
-rw-r--r-- 1 root root 412 Jun 27 /app/start.sh    # no x bit -> exec fails

# Healthy:
-rwxr-xr-x 1 root root 412 Jun 27 /app/start.sh
```

## Resolution

1. If the binary is missing or off `$PATH`, fix the `ENTRYPOINT`/`CMD` or
   `COPY` the script into the image and reference its real path.
2. If it exists but isn't executable, mark it in the Dockerfile:

   ```dockerfile
   COPY start.sh /app/start.sh
   RUN chmod +x /app/start.sh
   ```
3. For CRLF/shebang issues, normalize line endings (`dos2unix`) and ensure the
   shebang points at an interpreter present in the image.
4. For an architecture mismatch, rebuild for the host arch or run under emulation
   (`--platform linux/amd64`).
5. If a mount is shadowing the path, correct the `-v`/`--mount` target.

## Validation

```bash
docker run --rm <image>
# Expect the process to start and produce its normal startup logs, no OCI error.
```

## Prevention

- Add a smoke-test stage in CI that actually runs the built image.
- Lint Dockerfiles to ensure entrypoint scripts get `chmod +x`.
- Pin and verify `--platform` in multi-arch build pipelines.
- Keep `.gitattributes` set to `* text eol=lf` so scripts never get CRLF.

## Related Errors

- [Docker Invalid Mount Config for Type "bind"](./docker-invalid-mount-config-for-type-bind.md)
- [Docker Cannot Connect to the Docker Daemon](./docker-cannot-connect-to-docker-daemon.md)

## References

- [OCI runtime specification](https://github.com/opencontainers/runtime-spec)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`docker` · `runc` · `oci` · `container-start` · `production`
