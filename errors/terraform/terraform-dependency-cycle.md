---
title: "Terraform Dependency Cycle"
slug: terraform-dependency-cycle
technologies: [terraform]
severity: medium
tags: [terraform, graph, dependencies, plan, production]
related: [terraform-reference-to-undeclared-resource, terraform-invalid-for-each-argument]
last_reviewed: 2026-06-27
---

# Terraform Dependency Cycle

## Error Message

```text
╷
│ Error: Cycle: aws_security_group.app, aws_security_group.db
╵
```

```text
│ Error: Cycle: aws_iam_role.lambda, aws_iam_policy.lambda,
│ aws_iam_role_policy_attachment.lambda
```

## Description

Terraform orders operations by building a directed acyclic graph (DAG) from the
references between resources. If those references form a loop — A depends on B and
B depends (directly or transitively) on A — there is no valid order in which to
create or destroy them, and Terraform refuses to proceed. The error lists the
resource addresses that participate in the cycle.

## Technologies

- terraform (dependency graph builder)

## Severity

**medium** — a configuration/graph error caught before any API call; nothing is
changed. It can be subtle to untangle when the loop spans modules or implicit
references.

## Common Causes

1. Two security groups that each reference the other's ID in a rule (the classic
   case).
2. An explicit `depends_on` that points back at something already downstream.
3. A resource whose argument references an attribute of a resource that, in turn,
   references it.
4. Module input/output wiring that loops (module A output feeds module B which
   feeds back into module A).
5. A `lifecycle`/replacement chain that creates a mutual dependency during
   destroy.

## Root Cause Analysis

Each reference (`aws_security_group.db.id` inside `aws_security_group.app`)
creates a graph edge "app depends on db." A cycle means the graph cannot be
topologically sorted, so Terraform has no first node to act on. Security groups
are the canonical example because two groups commonly need to allow traffic from
each other, and inlining both rules forces a mutual reference. The fix is almost
always to *break the edge* by extracting the cross-reference into a standalone
resource that depends on both endpoints rather than coupling them directly.

## Diagnostic Commands

```bash
# Triggers the cycle error and names the participating resources
terraform plan

# Emit the dependency graph to inspect the loop visually
terraform graph > graph.dot
# (render with: dot -Tsvg graph.dot -o graph.svg  — read-only)

# Search for the mutual references that form the loop
grep -rn 'security_group' .
```

## Expected Results

```text
$ terraform plan
Error: Cycle: aws_security_group.app, aws_security_group.db

$ grep -rn 'security_group' .
./main.tf:12:  security_groups = [aws_security_group.db.id]    # in app
./main.tf:24:  security_groups = [aws_security_group.app.id]   # in db
```

Seeing each group reference the other inside its inline rules confirms the
mutual-reference cycle.

## Resolution

1. Break inline mutual rules into standalone `aws_security_group_rule` (or
   `vpc_security_group_ingress_rule`) resources that reference both groups
   without the groups referencing each other:

   ```hcl
   resource "aws_security_group" "app" {}
   resource "aws_security_group" "db"  {}

   resource "aws_security_group_rule" "app_to_db" {
     type                     = "ingress"
     security_group_id        = aws_security_group.db.id
     source_security_group_id = aws_security_group.app.id
     from_port = 5432
     to_port   = 5432
     protocol  = "tcp"
   }
   ```
2. Remove unnecessary `depends_on` that recreate the loop; let implicit
   references express ordering instead.
3. For module loops, restructure so data flows one direction, or pass shared IDs
   in from the root.

## Validation

```bash
terraform plan
# Expect: a normal plan with no "Cycle:" error and a clear create/update order.
```

## Prevention

- Model bidirectional relationships (SG-to-SG, IAM role/policy) with separate
  rule/attachment resources from the start.
- Use `depends_on` sparingly and only for true hidden dependencies.
- Render `terraform graph` in review when adding cross-resource references.

## Related Errors

- [Terraform Reference to Undeclared Resource](./terraform-reference-to-undeclared-resource.md)
- [Terraform Invalid for_each Argument](./terraform-invalid-for-each-argument.md)

## References

- [Terraform: Resource Dependencies](https://developer.hashicorp.com/terraform/language/resources/behavior#resource-dependencies)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`terraform` · `graph` · `dependencies` · `cycle` · `production`
