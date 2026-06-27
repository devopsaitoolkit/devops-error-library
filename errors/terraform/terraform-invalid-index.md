---
title: "Terraform Invalid Index"
slug: terraform-invalid-index
technologies: [terraform]
severity: medium
tags: [terraform, expressions, indexing, count, production]
related: [terraform-invalid-for-each-argument, terraform-invalid-function-argument]
last_reviewed: 2026-06-27
---

# Terraform Invalid Index

## Error Message

```text
╷
│ Error: Invalid index
│
│   on outputs.tf line 2, in output "first_subnet":
│    2:   value = aws_subnet.this[0].id
│
│ The given key does not identify an element in this collection value: the
│ collection has no elements.
╵
```

```text
│ Error: Invalid index
│   The given key does not identify an element in this collection value:
│   the given index value "web-c" does not match any key in the map.
```

## Description

This error occurs when you index into a list, map, tuple, or a `count`/`for_each`
resource using a key or position that doesn't exist. With `count` resources you
index by integer position (`[0]`); with `for_each` resources you index by string
key (`["web-a"]`). Indexing past the end of a list, into an empty collection, or
with a key that was never created all produce `Invalid index`.

## Technologies

- terraform (expression evaluator, resource indexing)

## Severity

**medium** — a configuration/evaluation error; no infrastructure is changed. It
often appears only for certain inputs (e.g. an empty list), so it can slip past
tests that always use populated data.

## Common Causes

1. Referencing `resource[0]` when `count = 0` made the collection empty.
2. Using an integer index on a `for_each` resource (which is keyed by string), or
   a string key on a `count` resource (keyed by integer).
3. A hard-coded index larger than the collection's length.
4. A map lookup with a key that doesn't exist (`local.ports["http"]` when only
   `"https"` is defined).
5. An off-by-one after a list shrank or a variable changed shape.

## Root Cause Analysis

Terraform collections are addressed by their actual keys: lists/`count` resources
by zero-based integers `0..n-1`, maps/`for_each` resources by their string keys.
Indexing is strict — there is no implicit "return null if absent" — so any key
outside the present set is an error. The empty-collection case is the most common
production trigger: a `count` driven by `length(var.x)` legitimately becomes `0`,
yet code elsewhere still references `[0]`. The fix is to make the access
defensive or to align it with how the collection is actually keyed.

## Diagnostic Commands

```bash
# Surfaces the invalid-index error with the offending expression
terraform validate
terraform plan

# Inspect the real keys/length of the collection
terraform console <<'EOF'
length(aws_subnet.this)
keys(local.ports)
EOF

# List instances actually present in state for a count/for_each resource
terraform state list | grep aws_subnet
```

## Expected Results

```text
> length(aws_subnet.this)
0

> keys(local.ports)
[
  "https",
]
```

A length of `0` (or a key set missing the one you indexed) confirms the access
targets an element that doesn't exist.

## Resolution

1. Make list/`count` access safe against empty collections:

   ```hcl
   # null when empty instead of erroring
   value = try(aws_subnet.this[0].id, null)
   # or guard with the count itself
   value = var.create ? aws_subnet.this[0].id : null
   ```
2. Match the index type to the resource: use `["web-a"]` for `for_each`, `[0]`
   for `count`.
3. For map lookups, supply a default: `lookup(local.ports, "http", 80)`.
4. If iterating, prefer `for`/splat (`aws_subnet.this[*].id`) over fixed indices.

## Validation

```bash
terraform console <<'EOF'
try(aws_subnet.this[0].id, "none")
EOF
# Expect: a value or "none" with no "Invalid index" error.
```

## Prevention

- Use `try()`, `lookup()` defaults, and splat expressions instead of bare indices.
- Test configs with empty/edge-case inputs, not just the happy path.
- Prefer `for_each` (named keys) over `count` (positional) for stable addressing.

## Related Errors

- [Terraform Invalid for_each Argument](./terraform-invalid-for-each-argument.md)
- [Terraform Invalid Function Argument](./terraform-invalid-function-argument.md)

## References

- [Terraform: Indices and Attributes](https://developer.hashicorp.com/terraform/language/expressions/references#indices-and-attributes)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`terraform` · `expressions` · `indexing` · `count` · `production`
