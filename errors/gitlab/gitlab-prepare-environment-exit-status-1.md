---
title: "GitLab Runner — Prepare Environment: Exit Status 1"
slug: gitlab-prepare-environment-exit-status-1
technologies: [gitlab]
severity: high
tags: [gitlab, runner, executor, environment, production]
related: [gitlab-cannot-connect-to-docker-daemon-dind, gitlab-kubernetes-executor-pod-timed-out]
last_reviewed: 2026-06-27
---

# GitLab Runner — Prepare Environment: Exit Status 1

## Error Message

```text
Preparing environment
Running on runner-abc123-project-456-concurrent-0 via gitlab-runner-host...
ERROR: Job failed (system failure): prepare environment: exit status 1.
Check https://docs.gitlab.com/runner/shells/index.html#shell-profile-loading for more information
```

## Description

`prepare environment: exit status 1` is a **system failure**, not a script
failure. It happens during the runner's *Preparing environment* phase — before any
`before_script`/`script` runs — when the executor cannot set up the shell or
container in which the job will execute. The most common trigger on the shell
executor is a profile script (`.bashrc`, `.bash_logout`, `.bash_profile`) that
exits non-zero on login, which aborts the whole environment setup.

## Technologies

- gitlab (GitLab Runner, executor / login shell)

## Severity

**high** — every job on the affected runner fails at setup, so the runner is
effectively down for that project/group until fixed.

## Common Causes

1. A login-shell profile (`~/.bashrc`, `~/.bash_logout`, `/etc/profile.d/*`) for
   the `gitlab-runner` user runs a command that exits non-zero (e.g. an
   interactive-only command, an `exit 1`, or a tool that errors when no TTY).
2. The runner user's home directory is missing, unwritable, or owned by root.
3. On Docker/Kubernetes executors, the image's entrypoint or a `pre_get_sources`
   helper step fails (e.g. unwritable build dir).
4. Disk full or permissions prevent creating the build/cache directories.
5. A broken `nvm`/`rbenv`/conda init line in the profile that errors under a
   non-interactive login.

## Root Cause Analysis

For the shell executor, GitLab Runner starts a **login shell** to run the
generated job script. A login shell sources the user's profile files. If any of
those sourced scripts returns a non-zero status (or a `set -e` profile hits an
error), the shell exits non-zero *before the job script runs*, and the runner
reports the failure as `prepare environment: exit status 1`. Because it happens in
the prepare phase, no job output appears — which is the tell that distinguishes it
from a normal `exit code 1` script failure.

## Diagnostic Commands

```bash
# Reproduce by opening a login shell as the runner user (read-only-ish probe)
sudo -u gitlab-runner bash -lc 'echo OK; echo "exit=$?"'

# Inspect the profile files that a login shell would source
ls -la /home/gitlab-runner/.bashrc /home/gitlab-runner/.bash_logout /home/gitlab-runner/.bash_profile
grep -nE 'exit|set -e|nvm|rbenv|conda' /home/gitlab-runner/.bashrc /etc/profile.d/*.sh 2>/dev/null

# Confirm home dir ownership/permissions and free disk
ls -ld /home/gitlab-runner
df -h /home/gitlab-runner

# Runner logs around the failure
journalctl -u gitlab-runner --since "15 min ago" --no-pager | tail -n 40
```

## Expected Results

```text
# A broken profile reveals itself:
$ sudo -u gitlab-runner bash -lc 'echo OK'
nvm: command not found            <- profile line errors
exit=127

# Healthy:
$ sudo -u gitlab-runner bash -lc 'echo OK'
OK
exit=0
```

## Resolution

1. Find the offending profile line and make it non-fatal / guard it for
   non-interactive shells:

   ```bash
   # ~/.bashrc — bail out early when there is no interactive TTY
   case $- in *i*) ;; *) return 0;; esac
   ```
2. Remove or fix `exit 1`, broken `nvm`/`rbenv` init, or any command that errors
   without a TTY.
3. Fix home-directory ownership and permissions:
   `sudo chown -R gitlab-runner:gitlab-runner /home/gitlab-runner`.
4. Free disk space if `df` shows the build volume full.
5. For Docker/K8s executors, confirm the image entrypoint succeeds and the build
   directory is writable.

## Validation

```bash
sudo -u gitlab-runner bash -lc 'echo OK'   # must print OK and exit 0
# Re-run a pipeline; the "Preparing environment" phase completes and the job runs.
```

## Prevention

- Keep `gitlab-runner` profile files minimal and non-interactive-safe.
- Monitor disk usage on runner build volumes and alert before full.
- Treat repeated `prepare environment` failures as a runner-health alert, not a
  per-job retry.

## Related Errors

- [GitLab DinD — Cannot Connect to the Docker Daemon](./gitlab-cannot-connect-to-docker-daemon-dind.md)
- [GitLab Kubernetes Executor Pod Timed Out](./gitlab-kubernetes-executor-pod-timed-out.md)

## References

- [GitLab Runner: Shell profile loading](https://docs.gitlab.com/runner/shells/index.html#shell-profile-loading)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`gitlab` · `runner` · `executor` · `environment` · `production`
