---
title: "GitLab CI — Shallow Clone: reference is not a tree"
slug: gitlab-shallow-clone-reference-is-not-a-tree
technologies: [gitlab]
severity: medium
tags: [gitlab, ci, git, shallow-clone, production]
related: [gitlab-job-failed-exit-code-1, gitlab-could-not-read-username-ci-job-token]
last_reviewed: 2026-06-27
---

# GitLab CI — Shallow Clone: reference is not a tree

## Error Message

```text
Getting source from Git repository
$ git checkout -f -q 3f9a1c2b...   # full SHA
fatal: reference is not a tree: 3f9a1c2b4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f90
ERROR: Job failed: exit code 128
```

```text
fatal: not a tree object
error: Server does not allow request for unadvertised object 3f9a1c2b...
```

## Description

By default GitLab CI performs a **shallow clone** (`GIT_DEPTH` defaults to 20),
fetching only the most recent commits. When the runner then tries to check out a
specific commit SHA that is **older than the fetched depth**, that object is not
present in the local repository and Git aborts with `reference is not a tree`. It
typically hits delayed pipelines, retried old pipelines, or pipelines that
reference commits beyond the shallow window (e.g. `git diff` against an old base,
or tools that walk history).

## Technologies

- gitlab (GitLab Runner Git strategy, shallow fetch)

## Severity

**medium** — the affected job fails to check out and aborts, but it is a
configuration fix (clone depth) with no runtime or data impact.

## Common Causes

1. A pipeline runs (or is **retried**) long after creation, so the target SHA has
   been buried beyond `GIT_DEPTH: 20`.
2. A job step needs **full history** — `git describe`, `git log`, blame, changelog
   generation, or diffing against an older base — but only a shallow clone exists.
3. Submodules or merge-base calculations require commits outside the shallow
   window.
4. A force-push rewrote history and the pipeline references a now-orphaned SHA not
   in the shallow set.
5. `GIT_DEPTH` set very low (e.g. `1`) for speed, breaking any history-aware tool.

## Root Cause Analysis

A shallow clone fetches only `GIT_DEPTH` commits from the tip; older commit and
tree objects are simply not transferred. Git checks out by resolving the SHA to a
**tree** object; if that object was never fetched, resolution fails with
`reference is not a tree` (or `not a tree object`). Because GitLab passes the exact
pipeline SHA to `git checkout`, any gap between "commits we fetched" and "the
commit we must check out" produces this error. The remote may also reject fetching
an unadvertised object, yielding the related "Server does not allow request for
unadvertised object" message.

## Diagnostic Commands

```bash
# What clone depth/strategy does the project use?
grep -nE 'GIT_DEPTH|GIT_STRATEGY|GIT_SUBMODULE_STRATEGY|variables:' .gitlab-ci.yml

# Inside a debug job: confirm the clone is shallow and how deep
git rev-parse --is-shallow-repository      # true => shallow
git log --oneline | wc -l                  # number of commits actually present

# Check whether the target SHA exists locally
git cat-file -t 3f9a1c2b 2>&1              # "fatal: Not a valid object name" => missing

# Project-level CI Git depth setting (Settings > CI/CD > General pipelines), via API
curl -s --header "PRIVATE-TOKEN: $GL_TOKEN" \
  "https://gitlab.com/api/v4/projects/<id>" | tr ',' '\n' | grep -i 'ci_default_git_depth'
```

## Expected Results

```text
$ git rev-parse --is-shallow-repository
true
$ git cat-file -t 3f9a1c2b
fatal: Not a valid object name 3f9a1c2b     <- the SHA isn't in the shallow set

# Healthy (deep enough or full): the object resolves to "commit".
```

## Resolution

1. Increase the clone depth for jobs that need older commits:

   ```yaml
   variables:
     GIT_DEPTH: 100        # fetch enough history to cover delayed/retried pipelines
   ```
2. For tools that need **complete** history (e.g. `git describe`, changelogs), use
   a full clone for that job:

   ```yaml
   release-notes:
     variables:
       GIT_DEPTH: 0        # 0 = full clone, no shallow truncation
     script: [git describe --tags]
   ```
3. Or raise the project default: Settings > CI/CD > General pipelines > **Git
   shallow clone** depth.
4. Avoid retrying very old pipelines; create a fresh pipeline on the current SHA
   instead.

## Validation

```bash
git rev-parse --is-shallow-repository   # false  (for GIT_DEPTH: 0)
git cat-file -t <target-sha>            # prints: commit
# Re-run the job; the checkout step completes, exit 0.
```

## Prevention

- Set `GIT_DEPTH` to comfortably exceed the busiest branch's commit rate over your
  pipeline-delay window; use `0` for history-dependent jobs only.
- Prefer creating new pipelines over retrying stale ones.
- Document which jobs need full history so depth is tuned per-job, not globally.

## Related Errors

- [GitLab CI Job Failed — Exit Code 1](./gitlab-job-failed-exit-code-1.md)
- [GitLab — Could Not Read Username (CI Job Token)](./gitlab-could-not-read-username-ci-job-token.md)

## References

- [GitLab: Git shallow clone / GIT_DEPTH](https://docs.gitlab.com/ee/ci/runners/configure_runners.html#shallow-cloning)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`gitlab` · `ci` · `git` · `shallow-clone` · `production`
