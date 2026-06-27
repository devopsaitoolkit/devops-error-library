---
title: "Terraform Invalid Function Argument"
slug: terraform-invalid-function-argument
technologies: [terraform]
severity: medium
tags: [terraform, functions, expressions, validation, production]
related: [terraform-invalid-index, terraform-unsupported-argument]
last_reviewed: 2026-06-27
---

# Terraform Invalid Function Argument

## Error Message

```text
╷
│ Error: Invalid function argument
│
│   on locals.tf line 5, in locals:
│    5:   config = jsondecode(file("${path.module}/config.json"))
│
│ Invalid value for "str" parameter: a number is required.
╵
```

```text
│ Error: Error in function call
│   Call to function "cidrsubnet" failed: prefix extension of 8 does not
│   accommodate a subnet numbered 300.
```

## Description

Terraform's built-in functions (`jsondecode`, `cidrsubnet`, `lookup`,
`templatefile`, `format`, …) each declare parameter types and value constraints.
This error means a function was called with an argument of the wrong type, or a
value that the function rejects at evaluation time (an out-of-range index, malformed
JSON, a missing file, a subnet number too large for the prefix). It surfaces
during expression evaluation in `validate`, `plan`, or `console`.

## Technologies

- terraform (expression evaluator, built-in functions)

## Severity

**medium** — a configuration error caught before any provider call; no
infrastructure changes. It can be tricky when the bad value comes from data the
function consumed (a file, a variable, an upstream output).

## Common Causes

1. A type mismatch — passing a string where a number is expected, or a list where
   a string is expected.
2. Malformed input data: `jsondecode`/`yamldecode` on a file that isn't valid
   JSON/YAML.
3. An out-of-range value: `cidrsubnet` with a `netnum` too large for the prefix,
   or `element` with a negative index.
4. A missing file passed to `file()`/`templatefile()`.
5. A `null` argument where the function requires a concrete value.

## Root Cause Analysis

Function arguments are validated in two passes: a static type check (does this
argument's type match the parameter?) and a runtime value check inside the
function body (is this value usable?). The first produces messages like "a number
is required"; the second produces function-specific messages like the
`cidrsubnet` range error. Because functions are often fed data loaded at runtime
(`file`, variables, resource outputs), the bad value frequently originates
upstream — so the fix may be in the data source, not the call site.

## Diagnostic Commands

```bash
# Reports the invalid-function-argument error with file and line
terraform validate

# Evaluate the call interactively to see the exact failing value
terraform console <<'EOF'
jsondecode(file("config.json"))
cidrsubnet("10.0.0.0/24", 8, 300)
EOF

# If decoding a file, lint the file itself
jq . config.json
```

## Expected Results

```text
> jsondecode(file("config.json"))
Error: Error in function call
Call to function "jsondecode" failed: invalid character '}' looking for
beginning of object key string.

$ jq . config.json
parse error: Expected another key-value pair at line 4, column 1
```

The `jq` parse error pinpoints the malformed JSON the function choked on,
confirming the bad argument came from the file rather than the HCL.

## Resolution

1. Correct the argument type or value at the call site:

   ```hcl
   # cidrsubnet: netnum must fit in newbits (2^8 = 256 max, so 0..255)
   subnet = cidrsubnet("10.0.0.0/16", 8, 12)
   ```
2. If the input data is malformed, fix the file/variable feeding the function and
   re-run; validate JSON/YAML with `jq`/`yq` first.
3. Convert types explicitly where intended: `tonumber(var.port)`,
   `tostring(local.id)`.
4. Guard against `null`/empty inputs with `coalesce`/`try`:
   `try(jsondecode(file(...)), {})`.

## Validation

```bash
terraform console <<'EOF'
cidrsubnet("10.0.0.0/16", 8, 12)
EOF
# Expect: "10.0.12.0/24" — a concrete result with no error.
```

## Prevention

- Validate external JSON/YAML data in CI before Terraform consumes it.
- Use `terraform console` to prototype function calls on representative values.
- Add `variable` type constraints and `validation` blocks so bad inputs fail
  early with a clear message.

## Related Errors

- [Terraform Invalid Index](./terraform-invalid-index.md)
- [Terraform Unsupported Argument](./terraform-unsupported-argument.md)

## References

- [Terraform: Built-in Functions](https://developer.hashicorp.com/terraform/language/functions)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`terraform` · `functions` · `expressions` · `validation` · `production`
