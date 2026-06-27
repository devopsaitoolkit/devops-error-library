---
title: "Terraform Reference to Undeclared Resource"
slug: terraform-reference-to-undeclared-resource
technologies: [terraform]
severity: medium
tags: [terraform, configuration, references, validation, production]
related: [terraform-unsupported-argument, terraform-dependency-cycle]
last_reviewed: 2026-06-27
---

# Terraform Reference to Undeclared Resource

## Error Message

```text
╷
│ Error: Reference to undeclared resource
│
│   on outputs.tf line 3, in output "instance_ip":
│    3:   value = aws_instance.web_server.private_ip
│
│ A managed resource "aws_instance" "web_server" has not been declared in the
│ root module.
╵
```

## Description

Terraform builds a dependency graph from the references in your configuration.
When an expression names a resource address (`<type>.<name>.<attr>`) that does
not correspond to any `resource` block in the current module, Terraform cannot
resolve it and aborts at the configuration-decoding stage. The same error appears
for data sources (`data.<type>.<name>`) and for module outputs that don't exist.

## Technologies

- terraform (HCL evaluator, reference resolution)

## Severity

**medium** — a configuration error caught before any provider call; no
infrastructure is touched. It blocks `plan`/`apply` until the reference is fixed.

## Common Causes

1. A typo in the resource's local name (`web_server` vs `webserver`).
2. The resource is declared in a child module, but referenced from the root as if
   it were local (must be reached via a module output instead).
3. The block was renamed or deleted but a reference to the old name remains.
4. Referencing a `data` source as a `resource` (missing the `data.` prefix), or
   vice-versa.
5. The resource only exists behind a `count`/`for_each` and is referenced without
   the required index/key.

## Root Cause Analysis

Resource addresses are scoped to the module that declares them. Terraform
resolves `aws_instance.web_server` strictly within the current module's namespace
— it does not search child modules. So a reference is "undeclared" either because
the name is misspelled, because the block lives in a different scope, or because
it was removed. Because this happens during static evaluation, the message points
at the exact file and line of the *reference*, not the missing declaration.

## Diagnostic Commands

```bash
# Reports every undeclared-reference error in the configuration
terraform validate

# List every resource address Terraform actually recognizes in this config
terraform state list

# Search the codebase for where the name is (and isn't) declared
grep -rn 'web_server' .

# Show module structure to confirm which scope owns the resource
terraform providers
```

## Expected Results

```text
$ grep -rn 'web_server' .
./outputs.tf:3:  value = aws_instance.web_server.private_ip
./modules/compute/main.tf:7:  resource "aws_instance" "web_server" {
```

This shows the resource is declared inside `modules/compute`, not the root — so
the root reference is out of scope and must go through a module output.

## Resolution

1. If it is a typo, correct the local name so the reference matches the
   `resource` block exactly.
2. If the resource lives in a child module, export it from that module and
   reference the module output:

   ```hcl
   # modules/compute/outputs.tf
   output "private_ip" { value = aws_instance.web_server.private_ip }

   # root outputs.tf
   output "instance_ip" { value = module.compute.private_ip }
   ```
3. If the block was deleted intentionally, remove the dangling reference too.
4. For `count`/`for_each` resources, add the index/key:
   `aws_instance.web_server[0]` or `aws_instance.web_server["a"]`.

## Validation

```bash
terraform validate
# Expect: "Success! The configuration is valid."
```

## Prevention

- Rename resources with editor refactor tools so every reference updates atomically.
- Keep module boundaries explicit: expose everything callers need via `output`.
- Run `terraform validate` in CI to catch dangling references before merge.

## Related Errors

- [Terraform Unsupported Argument](./terraform-unsupported-argument.md)
- [Terraform Dependency Cycle](./terraform-dependency-cycle.md)

## References

- [Terraform: References to Named Values](https://developer.hashicorp.com/terraform/language/expressions/references)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`terraform` · `configuration` · `references` · `validation` · `production`
