---
title: "Terraform Authentication Failed"
slug: terraform-authentication-failed
technologies: [terraform]
severity: high
tags: [terraform, authentication, credentials, cloud, production]
related: [terraform-error-configuring-provider, terraform-error-acquiring-state-lock]
last_reviewed: 2026-06-27
---

# Terraform Authentication Failed

## Error Message

```text
╷
│ Error: error creating EC2 Instance: UnauthorizedOperation: You are not
│ authorized to perform this operation. Encoded authorization failure message:
│ x1Ft...
│   status code: 403, request id: 8b2c1f0e-...
╵
```

```text
│ Error: creating S3 Bucket: AccessDenied: The AWS Access Key Id you provided
│ does not exist in our records. status code: 403
│
│ Error: ExpiredToken: The security token included in the request is expired
```

## Description

This is an authentication or authorization failure returned by the cloud API
during `plan` or `apply`, after the provider configured successfully. The
credentials resolved (so configuration was fine), but the cloud rejected them:
they are invalid, expired, or lack the IAM permissions for the specific action
(`ec2:RunInstances`, `s3:CreateBucket`, etc.). It is distinct from "error
configuring provider," which fails earlier, before any API call.

## Technologies

- terraform (provider API calls, cloud IAM)

## Severity

**high** — affected resources cannot be created, read, or modified. A broad
permission or expired-token problem can block an entire apply mid-run, sometimes
after partial changes have been made.

## Common Causes

1. Expired short-lived credentials (STS session token, OIDC token, SSO session)
   during a long apply.
2. The IAM principal lacks permission for the specific action or resource
   (missing `ec2:RunInstances`, an SCP/permission boundary blocking it).
3. Wrong account/profile selected — credentials valid but for a different
   account/subscription/project than intended.
4. A revoked or rotated access key still referenced in the environment.
5. Assume-role trust or condition (MFA, source IP, external ID) not satisfied.

## Root Cause Analysis

The provider's configured credentials are attached to each API request and
evaluated by the cloud's IAM engine per call. A `403`/`AccessDenied`/
`UnauthorizedOperation` means the *request was authenticated but not authorized*,
or the credential is no longer valid (`ExpiredToken`, `InvalidClientTokenId`).
Because authorization is per-action, a run can read fine yet fail on a single
privileged write — which is why these errors often appear deep into an apply
rather than at the start. AWS's `UnauthorizedOperation` even returns an *encoded*
message you must decode to see exactly which action/condition was denied.

## Diagnostic Commands

```bash
# Who Terraform is actually authenticating as (and whether the token is valid)
aws sts get-caller-identity

# Decode the encoded authorization failure to see the denied action (AWS)
aws sts decode-authorization-message --encoded-message <x1Ft...> \
  --query DecodedMessage --output text | jq .

# Confirm which profile/credentials the environment points at
env | grep -E '^(AWS_|ARM_|GOOGLE_)'

# Re-run the read-only plan to see whether reads also fail
terraform plan
```

## Expected Results

```text
$ aws sts get-caller-identity
An error occurred (ExpiredToken) when calling the GetCallerIdentity operation:
The security token included in the request is expired.
```

An expired/invalid identity here confirms a credential problem. If
`get-caller-identity` succeeds but a specific action is denied, the decoded
authorization message names the exact action and condition that failed.

## Resolution

1. Refresh expired credentials before (re)running:

   ```bash
   aws sso login --profile prod        # or re-assume the role / renew OIDC token
   export AWS_PROFILE=prod
   terraform plan
   ```
2. Grant the missing permission to the principal (add the action to its IAM
   policy, or adjust the SCP/permission boundary) following least privilege.
3. Verify you are targeting the intended account/subscription/project; correct the
   profile/credentials if not.
4. For assume-role, satisfy the trust conditions (MFA, external ID, source IP) and
   confirm the trust policy allows the caller.

## Validation

```bash
aws sts get-caller-identity   # confirms a valid identity in the right account
terraform plan
# Expect: plan completes and no 403/AccessDenied/UnauthorizedOperation appears.
```

## Prevention

- Use short-lived OIDC/role-based credentials in CI and ensure sessions outlast
  the longest apply.
- Scope IAM policies to the exact actions Terraform needs; test them in a
  non-prod account first.
- Pre-flight every pipeline with `sts get-caller-identity` to fail fast on bad
  credentials.

## Related Errors

- [Terraform Error Configuring Provider](./terraform-error-configuring-provider.md)
- [Terraform Error Acquiring the State Lock](./terraform-error-acquiring-state-lock.md)

## References

- [Terraform AWS Provider: Authentication](https://registry.terraform.io/providers/hashicorp/aws/latest/docs#authentication-and-configuration)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`terraform` · `authentication` · `credentials` · `cloud` · `production`
