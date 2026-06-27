---
title: "Terraform Error Acquiring the State Lock"
slug: terraform-error-acquiring-state-lock
technologies: [terraform]
severity: high
tags: [terraform, state, locking, backend, production]
related: [terraform-backend-configuration-changed, terraform-authentication-failed]
last_reviewed: 2026-06-27
---

# Terraform Error Acquiring the State Lock

## Error Message

```text
╷
│ Error: Error acquiring the state lock
│
│ Error message: ConditionalCheckFailedException: The conditional request failed
│ Lock Info:
│   ID:        9a1f3c2e-7b4d-4e21-8a90-6f0c1d2e3f44
│   Path:      my-tf-state/prod/terraform.tfstate
│   Operation: OperationTypeApply
│   Who:       jdoe@ci-runner-7
│   Version:   1.8.5
│   Created:   2026-06-27 09:14:32.118293 +0000 UTC
│   Info:
╵
```

## Description

Terraform takes an advisory lock on the remote state before any operation that
could write to it (`plan -out`, `apply`, `destroy`, `state` subcommands). The
lock prevents two concurrent runs from corrupting state. This error means
Terraform could not acquire the lock because another process already holds it, or
a previous run crashed and left a stale lock behind. With an S3 backend the lock
lives in a DynamoDB table; with Terraform Cloud, Consul, GCS, or azurerm the
mechanism differs but the symptom is identical.

## Technologies

- terraform (state backend, locking subsystem)

## Severity

**high** — no `apply` can proceed while the lock is held, blocking all
infrastructure changes for that state. In a CI pipeline this stalls every
downstream deploy until the lock is released.

## Common Causes

1. A genuinely concurrent run — two CI jobs or two engineers applying the same
   state at once.
2. A stale lock from a previous run that was killed (Ctrl-C, CI timeout, OOM,
   network drop) before it could release the lock.
3. The DynamoDB lock table (S3 backend) is missing, throttled, or the caller
   lacks `dynamodb:PutItem`/`DeleteItem` permissions.
4. Clock skew or a hung provider call leaving the lock held far longer than the
   operation should take.

## Root Cause Analysis

The lock is a single record (for S3: an item in DynamoDB keyed by the state path,
for GCS: an object, for Terraform Cloud: a run lock). Terraform writes the record
on start and deletes it on clean exit. If the process dies between those two
points, the record persists and every subsequent run sees `ConditionalCheckFailed`
(or the equivalent) and refuses to continue. The `Lock Info` block in the error
identifies *who* holds it and *when* it was created — that timestamp is the key
signal for distinguishing an active run from an abandoned one.

## Diagnostic Commands

```bash
# Read the lock record directly (S3 + DynamoDB backend); LockID is "<bucket>/<key>"
aws dynamodb get-item \
  --table-name terraform-locks \
  --key '{"LockID":{"S":"my-tf-state/prod/terraform.tfstate"}}'

# Confirm no other terraform process is running on this host
ps -ef | grep '[t]erraform'

# Inspect current backend/state config without locking
terraform show -no-color | head

# List running CI jobs that might hold the lock (example: GitLab)
gitlab-ci-job-list --pipeline current
```

## Expected Results

```text
{
  "Item": {
    "LockID": { "S": "my-tf-state/prod/terraform.tfstate" },
    "Info":   { "S": "{\"ID\":\"9a1f3c2e...\",\"Who\":\"jdoe@ci-runner-7\",\"Created\":\"2026-06-27T09:14:32Z\"}" }
  }
}
```

A lock `Created` minutes or hours ago with no matching live process is a stale
lock. An empty `get-item` result means the lock is already gone and a retry will
succeed.

## Resolution

1. First confirm no run is genuinely in progress. Check CI, ask the team. Force-
   unlocking a live `apply` can corrupt state.
2. If the lock is stale, release it with its exact ID from the error:

   ```bash
   terraform force-unlock 9a1f3c2e-7b4d-4e21-8a90-6f0c1d2e3f44
   ```
3. For a transient concurrency collision, simply retry once the other run
   finishes; serialize CI so only one job touches a given state at a time.
4. If the DynamoDB table is missing or under-permissioned, create it and grant
   `GetItem`/`PutItem`/`DeleteItem`, then re-init.

## Validation

```bash
# A no-op refresh acquires and cleanly releases the lock; success means it is free
terraform plan -refresh-only -lock-timeout=30s
# Expect: plan completes with "No changes" and no lock error.
```

## Prevention

- Serialize state-mutating jobs per state in CI (concurrency groups / queues).
- Set `-lock-timeout=120s` so brief overlaps wait instead of failing immediately.
- Use a `trap` in CI wrappers to run `terraform force-unlock` only on confirmed
  abandoned locks, never blindly.
- Monitor DynamoDB throttling and provision/auto-scale the lock table.

## Related Errors

- [Terraform Backend Configuration Changed](./terraform-backend-configuration-changed.md)
- [Terraform Authentication Failed](./terraform-authentication-failed.md)

## References

- [Terraform: State Locking](https://developer.hashicorp.com/terraform/language/state/locking)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`terraform` · `state` · `locking` · `backend` · `production`
