---
title: "GitLab CI Job Stuck — No Runners With Required Tags"
slug: gitlab-job-stuck-no-runners-with-tags
technologies: [gitlab]
severity: medium
tags: [gitlab, ci, runners, scheduling, production]
related: [gitlab-kubernetes-executor-pod-timed-out, gitlab-prepare-environment-exit-status-1]
last_reviewed: 2026-06-27
---

# GitLab CI Job Stuck — No Runners With Required Tags

## Error Message

```text
This job is stuck because you don't have any active runners online or available with any of these tags assigned to them: docker, linux
```

```text
This job is stuck because the project doesn't have any runners online assigned to it.
```

## Description

The pipeline is created and the job sits in `pending` indefinitely with a "stuck"
banner in the UI. GitLab's scheduler could not match the job to any runner because
no online runner satisfies the job's `tags:` set, the runner is paused/offline, or
the project has no eligible runner assigned. This is a *matching* failure inside
the GitLab coordinator, not a runner-side execution failure — the job never gets
dispatched.

## Technologies

- gitlab (CI coordinator, GitLab Runner)

## Severity

**medium** — pipelines do not progress, blocking merges and deployments, but
nothing is broken at runtime. Impact escalates to **high** when it blocks a
release pipeline.

## Common Causes

1. The job's `tags:` do not exactly match the tags configured on any runner
   (tags are case-sensitive and must match exactly, not as a subset).
2. The only matching runner is **paused**, **offline**, or has hit its
   concurrency limit.
3. The runner is configured to **run untagged jobs = off**, while the job has no
   tags (or vice versa).
4. A **project/group-specific** runner was expected but the runner is only
   assigned to a different project, or a shared-runner quota is exhausted.
5. The runner's `last contact` is stale because the `gitlab-runner` process is
   dead or cannot reach the GitLab URL.

## Root Cause Analysis

When a job enters `pending`, the GitLab coordinator looks for runners that (a) are
online (recent contact), (b) are assigned to the project (shared, group, or
specific), and (c) match the job's tags. A runner only picks up a tagged job when
its tag set is a **superset** of the job's tags. If the job declares
`tags: [docker, linux]` and the runner only has `docker`, no match occurs and the
job stays stuck. Untagged jobs require a runner with "Run untagged jobs" enabled.
If every candidate runner is filtered out, GitLab surfaces the "stuck" message.

## Diagnostic Commands

```bash
# List runners this host is registered as, and their tags/status
gitlab-runner list

# Verify the runner can reach GitLab and is registered/verified (read-only)
gitlab-runner verify

# Inspect tags + run_untagged for each registered runner
grep -E 'name|url|run_untagged|tag_list|executor' /etc/gitlab-runner/config.toml

# Confirm the runner process is alive and contacting GitLab
journalctl -u gitlab-runner --since "30 min ago" --no-pager | tail -n 40

# Show the job's required tags from the committed CI config
grep -nE '^\s*tags:|^\s*-\s' .gitlab-ci.yml
```

## Expected Results

```text
$ gitlab-runner list
Runtime platform   arch=amd64 os=linux
Listing configured runners       ConfigFile=/etc/gitlab-runner/config.toml
docker-runner   Executor=docker Token=glrt-xxxx URL=https://gitlab.com/

# config.toml shows the mismatch:
#   tag_list = ["docker"]          <- runner only has "docker"
#   run_untagged = false
# while .gitlab-ci.yml requires tags: [docker, linux]  -> no match -> stuck.
```

A healthy state shows the runner in **Admin > Runners** as online (green) with a
recent "last contact" and a tag set covering the job's tags.

## Resolution

1. Make the runner's tags a superset of the job's tags, or relax the job:

   ```yaml
   build:
     tags: [docker]        # match what the runner actually has
     script: [make build]
   ```
2. Or add the missing tag to the runner (Admin/Group/Project > Runners > Edit), or
   in `config.toml`:

   ```toml
   [[runners]]
     name = "docker-runner"
     tag_list = ["docker", "linux"]
   ```
   then restart: `sudo systemctl restart gitlab-runner`.
3. If the job is untagged, enable **Run untagged jobs** on the runner.
4. Un-pause the runner and confirm it is assigned to the project (shared vs.
   specific). For self-hosted, ensure the `gitlab-runner` service is running and
   the URL/token are correct.

## Validation

```bash
gitlab-runner verify    # runner is alive and verified against GitLab
# In the UI the job leaves "pending" and a runner picks it up within seconds.
```

## Prevention

- Standardize a small, documented tag vocabulary; reference it in every job.
- Add a smoke pipeline that runs on each runner pool so an offline pool is caught
  before a release.
- Alert on runner "last contact" age and on jobs pending > N minutes.

## Related Errors

- [GitLab Kubernetes Executor Pod Timed Out](./gitlab-kubernetes-executor-pod-timed-out.md)
- [GitLab Prepare Environment Exit Status 1](./gitlab-prepare-environment-exit-status-1.md)

## References

- [GitLab: Configuring runners — tags](https://docs.gitlab.com/ee/ci/runners/configure_runners.html)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`gitlab` · `ci` · `runners` · `scheduling` · `production`
