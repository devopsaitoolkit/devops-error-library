---
title: "GitLab CI — You Are Not Allowed to Download Code"
slug: gitlab-not-allowed-to-download-code
technologies: [gitlab]
severity: high
tags: [gitlab, ci, permissions, job-token, production]
related: [gitlab-could-not-read-username-ci-job-token, gitlab-registry-401-unauthorized]
last_reviewed: 2026-06-27
---

# GitLab CI — You Are Not Allowed to Download Code

## Error Message

```text
Getting source from Git repository
$ git fetch origin ...
remote: You are not allowed to download code from this project.
fatal: unable to access 'https://gitlab.com/acme/private-dep.git/': The requested URL returned error: 403
ERROR: Job failed: exit code 1
```

## Description

`You are not allowed to download code from this project` is a GitLab
**authorization** error (HTTP 403) returned when a CI job authenticates
successfully but the identity it used does not have permission to read the target
project's repository. Unlike a 401 (no/invalid credentials), here the credential
is valid — it simply lacks access. It most often appears when one project's
`$CI_JOB_TOKEN` clones another, private, project that has not granted access, or
when a project becomes private/archived.

## Technologies

- gitlab (CI job token, project authorization)

## Severity

**high** — dependent-repo fetches fail and the pipeline cannot build, blocking
merges and deploys for any job that needs that source.

## Common Causes

1. The **target** project's *CI/CD job token allowlist* does not include the
   project whose pipeline is running (default-deny on newer GitLab).
2. The target project is **private** and the token's identity has no membership.
3. A submodule points to a private repo the job token cannot read.
4. The target project was **archived** or moved, removing fetch access.
5. Group/instance setting "Limit access to this project" tightened after the
   pipeline was written.

## Root Cause Analysis

GitLab authenticates the `gitlab-ci-token:$CI_JOB_TOKEN` request, then checks
**authorization**: does the pipeline's project (and its token scope) have read
access to the requested repository? Recent GitLab versions default the inbound
job-token scope to *only the same project*, so cross-project fetches are denied
unless explicitly allowlisted. When the check fails, GitLab returns 403 with "You
are not allowed to download code from this project." This is distinct from a
missing-credentials 401 — the token is fine; the access policy says no.

## Diagnostic Commands

```bash
# Identify the cross-project repos the job tries to fetch
grep -nE 'git clone|git fetch|url = https://|submodule' .gitlab-ci.yml .gitmodules 2>/dev/null

# Inspect the TARGET project's inbound job-token allowlist (read-only)
curl -s --header "PRIVATE-TOKEN: $GL_TOKEN" \
  "https://gitlab.com/api/v4/projects/<target-id>/job_token_scope/allowlist"

# Confirm whether the inbound scope is enabled (default-deny) on the target
curl -s --header "PRIVATE-TOKEN: $GL_TOKEN" \
  "https://gitlab.com/api/v4/projects/<target-id>/job_token_scope" | tr ',' '\n'

# Confirm target project visibility/archive state
curl -s --header "PRIVATE-TOKEN: $GL_TOKEN" \
  "https://gitlab.com/api/v4/projects/<target-id>" | tr ',' '\n' | grep -iE 'visibility|archived'
```

## Expected Results

```text
# Empty allowlist + enabled inbound scope -> 403 on fetch:
{"inbound_enabled":true}
[]                      <- source project NOT listed

# Healthy: source project appears in the allowlist, and visibility is internal/public
{"id":<source-id>,"path_with_namespace":"acme/source-app"}
```

## Resolution

1. In the **target** project: Settings > CI/CD > Job token permissions — add the
   source project to the **allowlist** (or, less ideal, disable the inbound scope
   limit). Via API:

   ```bash
   curl --request POST --header "PRIVATE-TOKEN: $GL_TOKEN" \
     "https://gitlab.com/api/v4/projects/<target-id>/job_token_scope/allowlist" \
     --data "target_project_id=<source-id>"
   ```
2. If a human/Deploy token is more appropriate (e.g. read across many repos), use a
   Group Deploy Token or PAT with `read_repository` instead of `$CI_JOB_TOKEN`.
3. Un-archive or restore visibility of the target project if it was changed.
4. For submodules, ensure each referenced project is allowlisted.

## Validation

```bash
# Re-run the job; the fetch step now succeeds:
git fetch origin    # no 403, "You are not allowed..." gone, exit 0
```

## Prevention

- Treat the job-token allowlist as part of every new cross-project dependency.
- Prefer least-privilege read tokens scoped to the exact repos needed.
- Add a CI check that fails clearly ("repo X not allowlisted") rather than a raw
  403 deep in a build step.

## Related Errors

- [GitLab — Could Not Read Username (CI Job Token)](./gitlab-could-not-read-username-ci-job-token.md)
- [GitLab CI — Registry 401 Unauthorized](./gitlab-registry-401-unauthorized.md)

## References

- [GitLab: Control job token access](https://docs.gitlab.com/ee/ci/jobs/ci_job_token.html#control-job-token-access-to-your-project)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`gitlab` · `ci` · `permissions` · `job-token` · `production`
