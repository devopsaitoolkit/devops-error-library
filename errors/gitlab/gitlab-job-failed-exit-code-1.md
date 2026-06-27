---
title: "GitLab CI Job Failed — Exit Code 1"
slug: gitlab-job-failed-exit-code-1
technologies: [gitlab]
severity: medium
tags: [gitlab, ci, script, exit-code, production]
related: [gitlab-invalid-ci-config-yaml, gitlab-prepare-environment-exit-status-1]
last_reviewed: 2026-06-27
---

# GitLab CI Job Failed — Exit Code 1

## Error Message

```text
$ npm run build
> build
> tsc -p tsconfig.json
src/index.ts(42,7): error TS2322: Type 'string' is not assignable to type 'number'.
Cleaning up project directory and file based variables
ERROR: Job failed: exit code 1
```

## Description

`Job failed: exit code 1` is GitLab Runner reporting that a command in the job's
`script:` (or `before_script`/`after_script`) returned a non-zero status, so the
runner aborted the job. This is the most common — and most generic — CI failure.
The exit code is the *symptom*; the real error is the command output printed
immediately above the `ERROR:` line. Exit code 1 specifically means "a command
ran and failed," as opposed to environment-setup failures (prepare stage) or the
job being killed.

## Technologies

- gitlab (GitLab Runner, shell/script execution)

## Severity

**medium** — the pipeline fails and blocks the merge/deploy, but it is a
deterministic, fixable application or test failure rather than infrastructure
breakage.

## Common Causes

1. A real failure in the underlying tool: failing tests, a compile/type error, a
   linter violation, a build step that returns non-zero.
2. A missing dependency, binary, or environment variable that the script needs.
3. The script relies on a file or artifact that a previous stage did not produce
   or pass via `artifacts:`/`dependencies:`.
4. A shell pitfall — `set -e` aborting on an unexpected non-zero, or a piped
   command failing while only the last exit code is checked.
5. Permission or path issues inside the job container (wrong working directory,
   non-executable script).

## Root Cause Analysis

GitLab Runner executes the `script:` block line by line in a shell with `set -o
errexit` semantics for the generated script wrapper. The moment any command
returns non-zero, the runner stops, marks the job failed, and surfaces that
command's exit code. Exit code 1 is the conventional "general error" code most
tools use for "I ran but something was wrong" (test failure, lint failure, type
error). To find the cause you read the **last command's output before the ERROR
line**, not the ERROR line itself.

## Diagnostic Commands

```bash
# Reproduce the exact job locally with the same image (read-only inspection first)
grep -nE 'image:|script:|before_script:|after_script:' .gitlab-ci.yml

# Run the failing image and command interactively to reproduce
docker run --rm -it -v "$PWD":/src -w /src node:20 bash -lc 'npm ci && npm run build'

# Confirm artifacts/dependencies the job expects are declared upstream
grep -nE 'artifacts:|dependencies:|needs:' .gitlab-ci.yml

# Check the runner picked the intended image/executor
journalctl -u gitlab-runner --since "20 min ago" --no-pager | grep -i image
```

## Expected Results

```text
# Local reproduction prints the SAME failing line:
src/index.ts(42,7): error TS2322: Type 'string' is not assignable to type 'number'.

# A healthy run ends with the command succeeding and:
Job succeeded
```

## Resolution

1. Read the command output directly above `ERROR: Job failed: exit code 1` and
   fix that specific failure (test, type error, lint, missing file).
2. If a dependency is missing, install it in `before_script` or bake it into the
   image:

   ```yaml
   build:
     image: node:20
     before_script: [npm ci]
     script: [npm run build]
   ```
3. If the failure is a missing upstream artifact, declare it:

   ```yaml
   test:
     needs: [build]
     dependencies: [build]
   ```
4. For flaky pipe-related exits, make scripts robust (`set -euo pipefail`) and
   surface the failing sub-command.

## Validation

```bash
# Re-run the job in the UI, or locally:
docker run --rm -v "$PWD":/src -w /src node:20 bash -lc 'npm ci && npm run build'
# Expect exit status 0 and "Job succeeded" in the pipeline.
```

## Prevention

- Run the same lint/test/build commands locally and as a pre-commit hook so
  failures are caught before pushing.
- Pin the job `image:` so local reproduction matches CI exactly.
- Keep `script:` blocks small and fail-fast so the failing step is obvious.

## Related Errors

- [GitLab Invalid CI Config YAML](./gitlab-invalid-ci-config-yaml.md)
- [GitLab Prepare Environment Exit Status 1](./gitlab-prepare-environment-exit-status-1.md)

## References

- [GitLab CI/CD: script keyword](https://docs.gitlab.com/ee/ci/yaml/#script)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`gitlab` · `ci` · `script` · `exit-code` · `production`
