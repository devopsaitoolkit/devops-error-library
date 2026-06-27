---
title: "Terraform Unsupported Argument"
slug: terraform-unsupported-argument
technologies: [terraform]
severity: medium
tags: [terraform, configuration, schema, validation, production]
related: [terraform-reference-to-undeclared-resource, terraform-invalid-function-argument]
last_reviewed: 2026-06-27
---

# Terraform Unsupported Argument

## Error Message

```text
╷
│ Error: Unsupported argument
│
│   on main.tf line 14, in resource "aws_instance" "web":
│   14:   user_data_base64_encoded = true
│
│ An argument named "user_data_base64_encoded" is not expected here.
╵
```

## Description

Terraform validates every argument inside a resource, data source, provider, or
module block against the schema published by the relevant provider (or, for
modules, against the module's declared `variable` blocks). This error means you
supplied an argument name that does not exist in that schema. It is a
configuration-time error caught during `validate`, `plan`, or `init`, before any
API call is made.

## Technologies

- terraform (HCL parser, provider schema validation)

## Severity

**medium** — purely a config error; nothing is changed in your infrastructure.
It blocks the run but is safe and fast to fix once the correct argument name is
known.

## Common Causes

1. A typo or wrong casing in the argument name (`tag` vs `tags`,
   `user_data_base64_encoded` vs `user_data_base64`).
2. Using an argument from a newer (or older) provider version than the one
   installed — the schema changed between releases.
3. Copying HCL written for a different resource type or a different provider.
4. Passing a variable to a module that the module never declared as a `variable`.
5. Nesting an argument at the wrong level (top-level vs inside a nested block).

## Root Cause Analysis

Provider schemas are versioned and shipped inside the provider plugin. When
Terraform decodes your `.tf` files it maps each argument to a schema attribute;
any unmapped name is rejected with `Unsupported argument`. Because the schema is
version-specific, the same config can be valid on one provider version and
invalid on another — so the fix is often as much about the pinned version as the
spelling. For modules, the "schema" is the set of `variable` blocks, so an
unsupported argument means a missing or renamed input variable.

## Diagnostic Commands

```bash
# Surfaces every unsupported-argument error in the config at once
terraform validate

# Show which provider versions are actually installed
terraform version
terraform providers

# Inspect the exact schema for the resource to find the correct argument name
terraform providers schema -json | \
  jq '.provider_schemas[].resource_schemas["aws_instance"].block.attributes | keys'
```

## Expected Results

```text
$ terraform validate
Error: Unsupported argument
  on main.tf line 14, in resource "aws_instance" "web":
  14:   user_data_base64_encoded = true
An argument named "user_data_base64_encoded" is not expected here.
```

The `providers schema` output lists the *valid* attribute names — the correct one
(`user_data_base64`) appears there, confirming the offending name was a typo or
version mismatch.

## Resolution

1. Open the provider documentation for the exact installed version and find the
   correct argument name; compare it against `terraform providers schema -json`.
2. Fix the spelling/casing, or move the argument into the correct nested block:

   ```hcl
   resource "aws_instance" "web" {
     ami           = var.ami_id
     instance_type = "t3.micro"
     user_data_base64 = base64encode(file("init.sh"))  # correct attribute
   }
   ```
3. If the argument genuinely exists only in a newer provider, bump the version in
   `required_providers` and run `terraform init -upgrade`.
4. For modules, add the missing `variable "..." {}` declaration to the module.

## Validation

```bash
terraform validate
# Expect: "Success! The configuration is valid."
```

## Prevention

- Pin provider versions with `~>` and read the changelog before upgrading.
- Run `terraform validate` in CI on every commit.
- Enable editor LSP (terraform-ls) so unsupported arguments are flagged as you
  type.

## Related Errors

- [Terraform Reference to Undeclared Resource](./terraform-reference-to-undeclared-resource.md)
- [Terraform Invalid Function Argument](./terraform-invalid-function-argument.md)

## References

- [Terraform: Resource Syntax](https://developer.hashicorp.com/terraform/language/resources/syntax)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`terraform` · `configuration` · `schema` · `validation` · `production`
