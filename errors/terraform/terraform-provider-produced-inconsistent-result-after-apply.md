---
title: "Terraform Provider Produced Inconsistent Result After Apply"
slug: terraform-provider-produced-inconsistent-result-after-apply
technologies: [terraform]
severity: medium
tags: [terraform, provider, apply, bug, production]
related: [terraform-error-configuring-provider, terraform-failed-to-install-provider]
last_reviewed: 2026-06-27
---

# Terraform Provider Produced Inconsistent Result After Apply

## Error Message

```text
╷
│ Error: Provider produced inconsistent result after apply
│
│ When applying changes to aws_lb.app, provider
│ "registry.terraform.io/hashicorp/aws" produced an unexpected new value:
│ .subnets: was cty.SetVal(...) with 3 elements, but now has 2 elements.
│
│ This is a bug in the provider, which should be reported in the provider's own
│ issue tracker.
╵
```

## Description

After Terraform applies a change, it asks the provider for the resource's new
state and checks that it matches what the plan promised. If the value the
provider returns differs from the planned value (a count changes, an attribute
that was set comes back empty, an unknown becomes a different concrete value),
Terraform raises this error. As the message says, it is almost always a provider
bug or a quirk in how the upstream API normalizes inputs — not a mistake in your
HCL.

## Technologies

- terraform (apply consistency check, provider plugin)

## Severity

**medium** — the resource was usually *created or modified* by the API, but
Terraform marks the apply as failed and the state may be partially recorded. It
can leave the run in a state that needs a follow-up `apply` or targeted refresh.

## Common Causes

1. The provider/API normalizes or reorders a value (sorts a set, lowercases a
   string, drops a default-equal element) so the post-apply value differs from
   the plan.
2. A known provider bug for a specific resource/attribute in the installed
   version.
3. An attribute that is "computed" but the provider declared as user-settable,
   so the server overwrites it.
4. Eventual-consistency: the API returns a transient/partial value immediately
   after create.
5. Two attributes that the API couples (setting one silently changes another).

## Root Cause Analysis

Terraform's apply contract requires the provider's returned new value to be a
*consistent refinement* of the planned value: anything the plan marked "known"
must come back identical, and only "(known after apply)" fields may take concrete
values. When the provider returns something that contradicts a known planned
value, Terraform cannot trust the state and aborts the apply for that resource.
Because the contract is enforced by Terraform core but fulfilled by the provider,
the fix lives in the provider (or in pinning to a version where the resource
behaves), not in your configuration.

## Diagnostic Commands

```bash
# Identify the installed provider version that exhibits the bug
terraform version
terraform providers

# Re-run a no-op plan to see whether the resource now converges or keeps drifting
terraform plan

# Inspect what actually landed in state for the affected resource
terraform state show aws_lb.app

# Capture a detailed provider log for a bug report (read-only run)
TF_LOG=trace TF_LOG_PATH=tf-trace.log terraform plan
```

## Expected Results

```text
$ terraform plan
# aws_lb.app will be updated in-place
~ subnets = [
    - "subnet-0c3...",
  ]
Plan: 0 to add, 1 to change, 0 to destroy.
```

A second plan that *still* wants to change the same attribute (flapping between
2 and 3 elements) confirms a normalization/provider inconsistency rather than a
real config drift.

## Resolution

1. Re-run `terraform apply`. Many of these are transient (eventual consistency)
   and converge on the second run.
2. If it persists, upgrade or pin the provider to a version where the resource is
   fixed:

   ```hcl
   terraform {
     required_providers {
       aws = { source = "hashicorp/aws", version = "~> 5.60" }
     }
   }
   ```
   then `terraform init -upgrade`.
3. Align your config with the API's normalized form (e.g. pre-sort a list, match
   casing) so plan and post-apply agree.
4. As a last resort, work around the coupled attribute with `lifecycle { ignore_changes = [subnets] }`, and file a provider issue with the `TF_LOG=trace` output.

## Validation

```bash
terraform plan
# Expect: "No changes. Your infrastructure matches the configuration." on the
# subsequent plan, proving the resource converged.
```

## Prevention

- Pin provider versions and test upgrades in a non-prod workspace first.
- Watch the provider changelog/issue tracker for consistency-bug fixes.
- Avoid setting attributes the API treats as server-computed.

## Related Errors

- [Terraform Error Configuring Provider](./terraform-error-configuring-provider.md)
- [Terraform Failed to Install Provider](./terraform-failed-to-install-provider.md)

## References

- [Terraform: Provider Resource Behavior](https://developer.hashicorp.com/terraform/plugin/framework/resources)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`terraform` · `provider` · `apply` · `consistency` · `production`
