---
title: "GitLab CI — Could Not Read Username for CI_JOB_TOKEN"
slug: gitlab-could-not-read-username-ci-job-token
technologies: [gitlab]
severity: high
tags: [gitlab, ci, git, authentication, production]
related: [gitlab-not-allowed-to-download-code, gitlab-registry-401-unauthorized]
last_reviewed: 2026-06-27
---

# GitLab CI — Could Not Read Username for CI_JOB_TOKEN

## Error Message

```text
$ git clone https://gitlab.com/acme/shared-lib.git
Cloning into 'shared-lib'...
fatal: could not read Username for 'https://gitlab.com': No such device or address
```

```text
remote: HTTP Basic: Access denied. The provided password or token is incorrect...
fatal: Authentication failed for 'https://gitlab.com/acme/shared-lib.git/'
```

## Description

This error appears when a CI job tries to `git clone`/`fetch` (or `pip`/`go get`
/`npm install` from) **another** GitLab repository over HTTPS and Git cannot find
credentials. With no TTY, Git cannot prompt for a username, so it fails with
"could not read Username … No such device or address." The fix is to feed Git an
authenticated URL using `gitlab-ci-token:$CI_JOB_TOKEN`, and to ensure the target
project allows your project's job token.

## Technologies

- gitlab (CI job token, Git over HTTPS)

## Severity

**high** — jobs that pull dependent repositories (monorepo submodules,
shared libraries, private Go/PyPI deps) cannot fetch sources and fail early.

## Common Causes

1. Cloning another repo with a plain `https://gitlab.com/...` URL and no embedded
   credentials — Git has no username to use and cannot prompt.
2. A `.gitmodules` submodule URL points to an HTTPS repo without auth rewriting.
3. The target project does not allowlist the source project's `$CI_JOB_TOKEN`
   (returns "HTTP Basic: Access denied").
4. Using `$CI_JOB_TOKEN` as the *password* but omitting the required username
   `gitlab-ci-token`.
5. A package manager (`go get`, `pip`, `npm`) hitting a private GitLab repo without
   the credential helper configured.

## Root Cause Analysis

GitLab CI exposes `$CI_JOB_TOKEN`, a short-lived token valid for the duration of
the job. To authenticate a Git HTTPS request you must supply it as
`https://gitlab-ci-token:${CI_JOB_TOKEN}@gitlab.com/...`. When the URL has no
credentials, Git falls back to its credential helper, then to an interactive
prompt; in CI there is no terminal, so the read of "Username" fails with errno
`ENXIO` ("No such device or address"). Even with the token present, the **target**
project must list the source project in its job-token allowlist, or GitLab returns
`HTTP Basic: Access denied`.

## Diagnostic Commands

```bash
# Find the unauthenticated clone/submodule URLs in the repo
grep -nE 'git clone https://|url = https://' .gitlab-ci.yml .gitmodules 2>/dev/null

# Show whether the job rewrites HTTPS to embed the token
grep -nE 'CI_JOB_TOKEN|insteadOf|credential' .gitlab-ci.yml

# Verify the target project's job-token allowlist (read-only)
curl -s --header "PRIVATE-TOKEN: $GL_TOKEN" \
  "https://gitlab.com/api/v4/projects/<target-id>/job_token_scope/allowlist"

# Confirm git's view of credentials (no secret printed)
git config --get-regexp 'url\..*\.insteadof' 2>/dev/null
```

## Expected Results

```text
# Unauthenticated clone:
fatal: could not read Username for 'https://gitlab.com': No such device or address

# Token present but project not allowlisted:
remote: HTTP Basic: Access denied
fatal: Authentication failed

# Healthy: clone succeeds with no prompt.
```

## Resolution

1. Embed the CI job token in the clone URL:

   ```yaml
   script:
     - git clone "https://gitlab-ci-token:${CI_JOB_TOKEN}@gitlab.com/acme/shared-lib.git"
   ```
2. Better, rewrite all HTTPS GitLab URLs once (covers submodules and package
   managers):

   ```yaml
   before_script:
     - git config --global url."https://gitlab-ci-token:${CI_JOB_TOKEN}@gitlab.com/".insteadOf "https://gitlab.com/"
   ```
3. In the **target** project: Settings > CI/CD > Job token allowlist — add the
   source project and grant at least read access.
4. For Go modules set `GOPRIVATE` and rely on the `insteadOf` rewrite above.

## Validation

```bash
git clone "https://gitlab-ci-token:${CI_JOB_TOKEN}@gitlab.com/acme/shared-lib.git"
# Expect: "Cloning into 'shared-lib'..." with no Username prompt and exit 0.
```

## Prevention

- Always authenticate cross-repo access via the `insteadOf` rewrite in a shared
  `before_script`/CI template.
- Maintain job-token allowlists as part of project setup, not as an afterthought.
- Avoid hard-coding PATs in URLs; the ephemeral `$CI_JOB_TOKEN` is safer.

## Related Errors

- [GitLab — Not Allowed to Download Code](./gitlab-not-allowed-to-download-code.md)
- [GitLab CI — Registry 401 Unauthorized](./gitlab-registry-401-unauthorized.md)

## References

- [GitLab: CI/CD job token](https://docs.gitlab.com/ee/ci/jobs/ci_job_token.html)
- [GitLab: Use Git submodules in CI](https://docs.gitlab.com/ee/ci/git_submodules.html)

## Tags

`gitlab` · `ci` · `git` · `authentication` · `production`
