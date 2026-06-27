---
title: "Terraform Timeout While Waiting for Resource"
slug: terraform-timeout-while-waiting-for-resource
technologies: [terraform]
severity: high
tags: [terraform, apply, timeout, provisioning, production]
related: [terraform-provider-produced-inconsistent-result-after-apply, terraform-authentication-failed]
last_reviewed: 2026-06-27
---

# Terraform Timeout While Waiting for Resource

## Error Message

```text
╷
│ Error: waiting for RDS DB Instance (prod-db) to become available: timeout
│ while waiting for state to become 'available' (last state: 'creating',
│ timeout: 40m0s)
│
│   with aws_db_instance.prod,
│   on rds.tf line 1, in resource "aws_db_instance" "prod":
│    1: resource "aws_db_instance" "prod" {
╵
```

```text
│ Error: timeout while waiting for state to become 'success'
│ (last state: 'pending', timeout: 20m0s)
```

## Description

Many resources are not ready the instant the create/update API call returns —
databases, load balancers, clusters, and certificates provision asynchronously.
The provider therefore *polls* the cloud API until the resource reaches a desired
state (e.g. `available`) or a configured timeout elapses. This error means the
resource did not reach that state within the timeout. The resource often still
exists in the cloud, stuck mid-provisioning, even though Terraform reports
failure.

## Technologies

- terraform (provider state-change waiter)

## Severity

**high** — the apply fails and the resource is left in an indeterminate state;
state may record it as tainted or partially created, requiring cleanup or a
follow-up apply. Dependent resources downstream are blocked.

## Common Causes

1. The resource genuinely takes longer than the default timeout (large DB
   restore, big snapshot, slow region).
2. The resource is stuck/failed in the cloud (capacity error, invalid parameter,
   quota exhaustion) and will never reach the target state.
3. A dependency the resource needs at provision time (subnet, security group,
   KMS key, DNS validation) is missing or misconfigured.
4. Throttling/transient API errors slowing the polling loop.
5. ACM/DNS validation never completes because the validation record wasn't
   created.

## Root Cause Analysis

The provider's waiter loops on a "describe" call, checking the resource's status
against an expected target. A timeout has two very different meanings: either the
operation is *progressing but slow* (raise the timeout), or it is *stuck/failed*
(no amount of waiting helps — fix the underlying cause). The `last state` in the
message is the key signal: `creating`/`pending` that's still advancing suggests
slowness, while a state that flips to `failed`/`incompatible-parameters` (or never
moves) points at a real provisioning failure you must resolve in the cloud.

## Diagnostic Commands

```bash
# Check the resource's real status directly in the cloud (RDS example)
aws rds describe-db-instances --db-instance-identifier prod-db \
  --query 'DBInstances[0].DBInstanceStatus'

# Look for failure events explaining why it's stuck
aws rds describe-events --source-identifier prod-db --source-type db-instance \
  --duration 60

# See how Terraform recorded the resource (often tainted after timeout)
terraform state show aws_db_instance.prod

# Confirm quotas aren't the blocker
aws service-quotas get-service-quota --service-code rds --quota-code L-...
```

## Expected Results

```text
$ aws rds describe-db-instances --db-instance-identifier prod-db \
    --query 'DBInstances[0].DBInstanceStatus'
"creating"

$ aws rds describe-events ... 
"... Recovery of the DB instance has started" / "insufficient capacity ..."
```

A status still progressing (`creating`/`backing-up`) means it was just slow. A
failure event (capacity/parameter error) means it was genuinely stuck — extending
the timeout would not have helped.

## Resolution

1. If the operation is merely slow, raise the resource's timeout:

   ```hcl
   resource "aws_db_instance" "prod" {
     # ...
     timeouts {
       create = "90m"
       update = "90m"
     }
   }
   ```
   then re-run `terraform apply`.
2. If it failed in the cloud, fix the root cause (request quota, correct the
   parameter group, supply the missing subnet/KMS key/DNS validation record),
   then re-apply.
3. If state is left tainted/half-created, let Terraform replace it, or remove the
   stuck cloud resource manually and re-apply.
4. For ACM, ensure the DNS validation `CNAME` records are actually created so
   validation can complete.

## Validation

```bash
terraform apply
aws rds describe-db-instances --db-instance-identifier prod-db \
  --query 'DBInstances[0].DBInstanceStatus'
# Expect: apply completes and status is "available".
```

## Prevention

- Set realistic `timeouts` blocks for slow resources based on observed durations.
- Pre-create and validate dependencies (subnets, KMS, DNS) before the slow
  resource.
- Monitor quotas and request increases ahead of large provisioning runs.

## Related Errors

- [Terraform Provider Produced Inconsistent Result After Apply](./terraform-provider-produced-inconsistent-result-after-apply.md)
- [Terraform Authentication Failed](./terraform-authentication-failed.md)

## References

- [Terraform: Resource Timeouts](https://developer.hashicorp.com/terraform/language/resources/syntax#operation-timeouts)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`terraform` · `apply` · `timeout` · `provisioning` · `production`
