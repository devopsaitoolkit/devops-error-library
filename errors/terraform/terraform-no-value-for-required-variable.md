---
title: "Terraform No Value for Required Variable"
slug: terraform-no-value-for-required-variable
technologies: [terraform]
severity: medium
tags: [terraform, variables, configuration, ci, production]
related: [terraform-unsupported-argument, terraform-module-not-installed]
last_reviewed: 2026-06-27
---

# Terraform No Value for Required Variable

## Error Message

```text
╷
│ Error: No value for required variable
│
│   on variables.tf line 1:
│    1: variable "environment" {
│
│ The root module input variable "environment" is not set, and has no default
│ value. Use a -var or -var-file command line argument to provide a value for
│ this variable.
╵
```

## Description

A `variable` block with no `default` is a *required* input. Terraform must have a
value for it before it can build the plan. In an interactive terminal Terraform
prompts for the value; in a non-interactive context (CI, `-input=false`) it
cannot prompt, so it fails immediately with this error. The same applies when a
module declares a required variable that the caller never passes.

## Technologies

- terraform (variable resolution, input handling)

## Severity

**medium** — a configuration/wiring error; no infrastructure changes occur. It is
most disruptive in CI, where it can silently break automated pipelines that ran
fine interactively.

## Common Causes

1. Running with `-input=false` (the CI default) without supplying the variable
   via `-var`, `-var-file`, or a `TF_VAR_` environment variable.
2. A `terraform.tfvars`/`*.auto.tfvars` file that defines the value exists locally
   but isn't present (or isn't committed) in CI.
3. A typo: `TF_VAR_enviroment` vs `TF_VAR_environment`, or the variable renamed in
   one place but not the other.
4. A module requires an input the caller forgot to pass.
5. Relying on a default that was removed during a refactor.

## Root Cause Analysis

Terraform resolves variable values from a fixed precedence chain: `-var`/`-var-file`
flags, then `*.auto.tfvars`, then `terraform.tfvars`, then `TF_VAR_*` environment
variables, then interactive prompt. If none of these supplies a value for a
variable that has no `default`, and prompting is disabled, the only outcome is
this error. Because CI runs with `-input=false`, a setup that "works on my
machine" (where the prompt fills the gap) breaks in the pipeline — the classic
trigger.

## Diagnostic Commands

```bash
# Reproduce the failure exactly as CI sees it (no prompt)
terraform plan -input=false

# Show which TF_VAR_* values are present in the environment
env | grep '^TF_VAR_'

# List the var files Terraform will auto-load
ls -1 *.auto.tfvars terraform.tfvars 2>/dev/null

# Confirm the variable is declared and lacks a default
grep -A3 'variable "environment"' variables.tf
```

## Expected Results

```text
$ env | grep '^TF_VAR_'
TF_VAR_region=us-east-1
# (note: TF_VAR_environment is absent — that is the missing value)

$ grep -A3 'variable "environment"' variables.tf
variable "environment" {
  type = string
}
```

The variable has a `type` but no `default`, and no source in the precedence chain
provides it — confirming the missing input.

## Resolution

1. Provide the value through whichever channel suits the context:

   ```bash
   terraform plan -input=false -var="environment=prod"
   # or
   export TF_VAR_environment=prod
   # or commit a prod.tfvars and pass -var-file=prod.tfvars
   ```
2. For modules, pass the input explicitly in the calling block:

   ```hcl
   module "app" {
     source      = "./modules/app"
     environment = var.environment   # was missing
   }
   ```
3. If a sensible safe default exists, add `default = "..."` to the `variable`
   block — but never default secrets or environment selectors that must be
   chosen deliberately.

## Validation

```bash
terraform plan -input=false
# Expect: plan runs to completion with no "No value for required variable" error.
```

## Prevention

- Always run `terraform plan -input=false` in CI to catch missing inputs early.
- Commit per-environment `*.tfvars` files (without secrets) and reference them
  explicitly.
- Document required variables in the module README and add `validation` blocks.

## Related Errors

- [Terraform Unsupported Argument](./terraform-unsupported-argument.md)
- [Terraform Module Not Installed](./terraform-module-not-installed.md)

## References

- [Terraform: Input Variables](https://developer.hashicorp.com/terraform/language/values/variables)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`terraform` · `variables` · `configuration` · `ci` · `production`
