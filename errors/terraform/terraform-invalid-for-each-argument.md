---
title: "Terraform Invalid for_each Argument"
slug: terraform-invalid-for-each-argument
technologies: [terraform]
severity: medium
tags: [terraform, for-each, meta-arguments, plan, production]
related: [terraform-invalid-index, terraform-reference-to-undeclared-resource]
last_reviewed: 2026-06-27
---

# Terraform Invalid for_each Argument

## Error Message

```text
╷
│ Error: Invalid for_each argument
│
│   on main.tf line 9, in resource "aws_subnet" "this":
│    9:   for_each = toset([for s in var.subnets : s.cidr])
│
│ The "for_each" map includes keys derived from resource attributes that cannot
│ be determined until apply, and so Terraform cannot determine the full set of
│ keys that will identify the instances of this resource.
╵
```

```text
│ Error: Invalid for_each argument
│ The given "for_each" argument value is unsuitable: the "for_each" argument must
│ be a map, or set of strings, and you have provided a value of type list of
│ string.
```

## Description

The `for_each` meta-argument creates one instance of a resource or module per
element of a map or a set of strings, keyed by the map key (or set value).
Terraform must know the *full set of keys* during planning, because each key
becomes a stable resource address. This error means the value you gave `for_each`
is either the wrong type (a list, a tuple, `null`) or its keys depend on values
that won't be known until apply.

## Technologies

- terraform (graph builder, plan phase)

## Severity

**medium** — blocks the plan; no resources are created or destroyed. Once the
collection is the right type and statically known, it resolves cleanly.

## Common Causes

1. Passing a **list** or **tuple** to `for_each` instead of a map or
   `set(string)`.
2. Keys derived from a *computed* attribute (e.g. an ID returned by another
   resource) that is unknown until apply.
3. The collection contains `null` or non-string elements in the set.
4. Using `for_each` over a value that is itself `null` or unset because an
   upstream variable wasn't provided.
5. Duplicate keys after a `for` transform collapse to fewer instances than
   expected.

## Root Cause Analysis

`for_each` instance addresses (`resource.name["key"]`) are recorded in state and
must be stable across plans, so Terraform requires the key set to be *known at
plan time*. Two distinct failures produce this message: a **type** failure (lists
have no inherent keys, so they're rejected — only maps and string sets carry
keys), and a **knowability** failure (keys that come from `aws_instance.x.id` or
similar can't be computed before apply, so the key set is unknown). The fix
differs depending on which of the two you hit, which the message text makes clear.

## Diagnostic Commands

```bash
# Confirms the type/knowability error at plan time
terraform plan

# Inspect the exact type and value being fed to for_each
terraform console <<'EOF'
type(var.subnets)
toset([for s in var.subnets : s.cidr])
EOF

# Validate basic structure before planning
terraform validate
```

## Expected Results

```text
> type(var.subnets)
list(object({ cidr = string, az = string }))

> toset([for s in var.subnets : s.cidr])
toset([
  "10.0.1.0/24",
  "10.0.2.0/24",
])
```

If `terraform console` errors with "(known after apply)" inside the expression,
the keys depend on a computed value — the knowability case. If `type()` shows a
list/tuple where a map is required, it's the type case.

## Resolution

1. For the type case, convert to a map keyed by a static field, or a set of
   strings:

   ```hcl
   resource "aws_subnet" "this" {
     for_each = { for s in var.subnets : s.name => s }   # map keyed by static name
     cidr_block        = each.value.cidr
     availability_zone = each.value.az
   }
   ```
2. For the knowability case, key on a value you control (an input variable, a
   name) rather than a computed ID. Never key `for_each` on `<resource>.id`.
3. Guard against `null` collections with `for_each = var.subnets == null ? {} : ...`.
4. Ensure the keying expression produces unique keys to avoid silent collapse.

## Validation

```bash
terraform plan
# Expect: plan shows one resource instance per key, e.g.
#   aws_subnet.this["public-a"], aws_subnet.this["public-b"]
```

## Prevention

- Always feed `for_each` a map keyed by a stable, human-meaningful identifier.
- Avoid deriving keys from any attribute marked "(known after apply)".
- Add a `precondition` or `validation` block to assert the collection is non-null
  and uniquely keyed.

## Related Errors

- [Terraform Invalid Index](./terraform-invalid-index.md)
- [Terraform Reference to Undeclared Resource](./terraform-reference-to-undeclared-resource.md)

## References

- [Terraform: The for_each Meta-Argument](https://developer.hashicorp.com/terraform/language/meta-arguments/for_each)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`terraform` · `for-each` · `meta-arguments` · `plan` · `production`
