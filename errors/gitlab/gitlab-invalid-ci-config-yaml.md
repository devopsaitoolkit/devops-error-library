---
title: "GitLab Invalid CI Config — YAML / .gitlab-ci.yml Error"
slug: gitlab-invalid-ci-config-yaml
technologies: [gitlab]
severity: medium
tags: [gitlab, ci, yaml, config, production]
related: [gitlab-job-failed-exit-code-1, gitlab-job-stuck-no-runners-with-tags]
last_reviewed: 2026-06-27
---

# GitLab Invalid CI Config — YAML / .gitlab-ci.yml Error

## Error Message

```text
Found errors in your .gitlab-ci.yml:
  jobs:build config contains unknown keys: scripts
  jobs:test:rules config should be an array of hashes
```

```text
This GitLab CI configuration is invalid: jobs config should contain at least one visible job
```

## Description

GitLab validates `.gitlab-ci.yml` *before* creating any pipeline. If the file is
not valid YAML, or is valid YAML but violates the CI schema (unknown keywords,
wrong value types, undefined `extends`/`needs` targets), GitLab refuses to create
the pipeline and shows a red banner on the Pipelines page or in the Pipeline
Editor. No job runs — the whole pipeline is rejected at lint time. This is
distinct from a job that runs and fails; here nothing runs at all.

## Technologies

- gitlab (pipeline configuration parser/linter)

## Severity

**medium** — no pipeline is created, so merges and deploys are blocked, but the
fix is a config edit and there is no runtime breakage.

## Common Causes

1. YAML syntax errors: bad indentation, tabs instead of spaces, an unquoted value
   containing `:`, or a missing/misaligned list item.
2. A typo'd keyword (`scripts:` instead of `script:`, `stage:` vs `stages:`).
3. Wrong value type — e.g. `rules:` given a mapping instead of a list of mappings,
   or `tags:` given a string instead of a list.
4. `extends:` or `needs:` referencing a job/template that does not exist.
5. An `include:` target that is missing, on the wrong ref, or itself invalid.

## Root Cause Analysis

GitLab parses the YAML, merges all `include:` and `extends:` chains, then
validates the merged document against the CI schema. Two failure classes exist:
**parse errors** (the YAML itself is malformed) and **schema errors** (valid YAML,
illegal CI structure). The error message names the path that failed
(`jobs:build config contains unknown keys: scripts`), which points you to the
exact job and key. Because validation happens before scheduling, the failure is
fully deterministic and reproducible with the CI Lint tool.

## Diagnostic Commands

```bash
# 1) Check raw YAML validity first (parse errors)
yamllint .gitlab-ci.yml || python3 -c "import yaml,sys; yaml.safe_load(open('.gitlab-ci.yml'))"

# 2) Reveal hidden tabs/trailing whitespace that break YAML
grep -nP '\t' .gitlab-ci.yml          # tabs are illegal indentation in YAML
cat -A .gitlab-ci.yml | head -n 40    # ^I marks tabs, $ marks line ends

# 3) Inspect included files and extends targets referenced by the config
grep -nE 'include:|extends:|needs:|template:' .gitlab-ci.yml

# 4) Validate the merged config via the CI Lint API (read-only)
curl -s --header "PRIVATE-TOKEN: $GL_TOKEN" \
  "https://gitlab.com/api/v4/projects/<id>/ci/lint?include_merged_yaml=true"
```

## Expected Results

```text
# yamllint flags the structural problem:
.gitlab-ci.yml:14:1  error  found character '\t' that cannot start any token (syntax)

# CI Lint API returns:
{"valid":false,"errors":["jobs:build config contains unknown keys: scripts"]}

# Healthy:
{"valid":true,"errors":[],"warnings":[]}
```

## Resolution

1. Fix YAML structure first: replace tabs with spaces, align list items, quote any
   value containing `:`.
2. Correct the keyword the error names. For the example, `scripts` -> `script`:

   ```yaml
   build:
     stage: build
     script:            # not "scripts"
       - make build
   ```
3. Ensure `rules:` is a list of mappings:

   ```yaml
   test:
     rules:
       - if: '$CI_COMMIT_BRANCH == "main"'
   ```
4. Verify every `extends:`/`needs:` target exists and that `include:` files are on
   a reachable ref.

## Validation

```bash
# Re-lint after editing; expect "valid": true
curl -s --header "PRIVATE-TOKEN: $GL_TOKEN" \
  "https://gitlab.com/api/v4/projects/<id>/ci/lint" \
  --data-urlencode "content@.gitlab-ci.yml" | grep -o '"valid":[a-z]*'
```

## Prevention

- Run the CI Lint API (or the Pipeline Editor's live validation) in a pre-merge
  check on the `.gitlab-ci.yml` itself.
- Use the GitLab Pipeline Editor, which validates as you type and resolves
  `include`/`extends`.
- Add `yamllint` to a fast pre-commit hook to catch tabs/indentation early.

## Related Errors

- [GitLab CI Job Failed — Exit Code 1](./gitlab-job-failed-exit-code-1.md)
- [GitLab CI Job Stuck — No Runners With Required Tags](./gitlab-job-stuck-no-runners-with-tags.md)

## References

- [GitLab: Validate CI configuration (CI Lint)](https://docs.gitlab.com/ee/ci/yaml/lint.html)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`gitlab` · `ci` · `yaml` · `config` · `production`
