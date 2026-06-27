---
title: "Terraform Module Not Installed"
slug: terraform-module-not-installed
technologies: [terraform]
severity: medium
tags: [terraform, modules, init, configuration, production]
related: [terraform-no-value-for-required-variable, terraform-failed-to-query-available-provider-packages]
last_reviewed: 2026-06-27
---

# Terraform Module Not Installed

## Error Message

```text
╷
│ Error: Module not installed
│
│   on main.tf line 8:
│    8: module "network" {
│
│ This module is not yet installed. Run "terraform init" to install all modules
│ required by this configuration.
╵
```

```text
│ Error: Module source has changed
│ The source address for module "network" has changed. Run "terraform init"
│ to install the new module source.
```

## Description

Terraform must download and record every `module` block referenced in your
configuration before it can plan or apply. The installed modules and their
sources are tracked in `.terraform/modules/modules.json`. This error means a
module declared in your config has not been installed (no `init` after adding or
checking out the config) or its `source`/`version` changed since the last init,
so the cached copy no longer matches.

## Technologies

- terraform (module installer, init)

## Severity

**medium** — `plan`/`apply` are blocked, but it is a routine, low-risk fix: run
`init`. It commonly bites in CI when the `.terraform/` cache isn't present or
isn't refreshed after a module bump.

## Common Causes

1. A fresh checkout (or a CI job) where `terraform init` hasn't run yet, so no
   modules are installed.
2. A new `module` block was added but `init` wasn't re-run.
3. The module `source` or `version` was changed (registry version bump, Git ref,
   relative-path move) without re-initializing.
4. `.terraform/modules/` was deleted or excluded, losing the installed copies.
5. A private module registry/Git source that is unreachable or needs auth at
   install time.

## Root Cause Analysis

Module installation is an `init`-time step separate from provider installation:
Terraform resolves each `source` (local path, registry, Git, S3), fetches it, and
writes the mapping into `.terraform/modules/modules.json`. `plan`/`apply` read
only from that installed cache — they never fetch modules themselves. So any time
the config's module references and the installed cache disagree (new module,
changed source, missing cache), Terraform refuses to proceed and directs you to
`init`. This is by design: it keeps planning offline and deterministic.

## Diagnostic Commands

```bash
# Shows whether modules are installed and what sources are recorded
cat .terraform/modules/modules.json | jq '.Modules[] | {Key, Source, Version}'

# Compare against module blocks in the config
grep -A4 'module "' *.tf

# Confirm the module source is reachable (registry example)
curl -sS https://registry.terraform.io/v1/modules/terraform-aws-modules/vpc/aws/versions | jq '.modules[0].versions[-1]'

# List installed module directories
ls -1 .terraform/modules/ 2>/dev/null
```

## Expected Results

```text
$ cat .terraform/modules/modules.json | jq '.Modules[].Key'
# (empty / file missing)  -> modules were never installed

$ grep -A4 'module "' main.tf
module "network" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"
}
```

A missing/empty `modules.json` against a config that declares modules confirms the
install step was skipped or the cache was wiped.

## Resolution

1. Install (or reinstall) modules:

   ```bash
   terraform init
   ```
2. If the source changed and the cache is stale, force a refresh:

   ```bash
   terraform init -upgrade   # re-resolves module versions/sources
   ```
3. For private Git/registry sources, provide credentials (Git token, netrc,
   registry auth) so the install can fetch them.
4. In CI, ensure `terraform init` runs before `plan`, and either persist or
   rebuild the `.terraform/` cache each run.

## Validation

```bash
terraform init
terraform plan
# Expect: init reports "Downloading/Installing modules" then plan runs with no
# "Module not installed" error.
```

## Prevention

- Always run `terraform init` as the first step in CI, before validate/plan.
- Pin module `version` constraints and bump them deliberately, re-running init.
- Keep `.terraform/` out of source control; treat it as a rebuildable cache.

## Related Errors

- [Terraform No Value for Required Variable](./terraform-no-value-for-required-variable.md)
- [Terraform Failed to Query Available Provider Packages](./terraform-failed-to-query-available-provider-packages.md)

## References

- [Terraform: Modules](https://developer.hashicorp.com/terraform/language/modules)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`terraform` · `modules` · `init` · `configuration` · `production`
