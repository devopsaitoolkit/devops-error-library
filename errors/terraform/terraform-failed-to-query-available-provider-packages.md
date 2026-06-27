---
title: "Terraform Failed to Query Available Provider Packages"
slug: terraform-failed-to-query-available-provider-packages
technologies: [terraform]
severity: high
tags: [terraform, init, registry, providers, production]
related: [terraform-failed-to-install-provider, terraform-module-not-installed]
last_reviewed: 2026-06-27
---

# Terraform Failed to Query Available Provider Packages

## Error Message

```text
╷
│ Error: Failed to query available provider packages
│
│ Could not retrieve the list of available versions for provider hashicorp/aws:
│ could not connect to registry.terraform.io: Failed to request discovery
│ document: Get "https://registry.terraform.io/.well-known/terraform.json":
│ dial tcp: lookup registry.terraform.io: no such host
╵
```

```text
│ Could not retrieve the list of available versions for provider
│ hashicorp/aws: no available releases match the given constraints >= 6.0.0, < 5.0.0
```

## Description

During `terraform init`, Terraform contacts a provider registry (by default the
public `registry.terraform.io`) to discover which versions of each required
provider exist and satisfy your version constraints. This error means the
discovery/version-listing step failed: either Terraform could not reach the
registry (network/DNS/proxy/TLS), or it reached it but no published version
matches the constraints you specified.

## Technologies

- terraform (init, provider installer, registry protocol)

## Severity

**high** — `init` cannot complete, so no providers are installed and no
subsequent `plan`/`apply` is possible. In CI this fails the whole pipeline at the
first step.

## Common Causes

1. No network path to the registry — DNS failure, blocked egress, missing proxy
   on a locked-down runner.
2. Mutually exclusive or impossible version constraints (`>= 6.0.0, < 5.0.0`).
3. A typo in the provider `source` (`hashicorp/awss`) so no such provider exists.
4. A private/mirror registry that is down, misconfigured, or requires auth that
   isn't present.
5. Corporate TLS interception without the CA trusted, breaking the HTTPS request.

## Root Cause Analysis

The provider installer first fetches the registry's discovery document, then
queries the versions endpoint for each provider and intersects the results with
your `required_providers` constraints. A *connectivity* failure (DNS, TCP, TLS,
proxy) aborts before any version is listed — the message mentions `dial tcp` or
`Failed to request discovery document`. A *constraint* failure connects fine but
finds an empty intersection — the message says `no available releases match`.
The two failure modes need different fixes, and the error text tells you which.

## Diagnostic Commands

```bash
# Run init verbosely to see the exact request that failed
TF_LOG=debug terraform init 2>&1 | grep -i registry

# Test raw connectivity/DNS to the registry
curl -sS https://registry.terraform.io/.well-known/terraform.json | head

# Show the constraints actually declared
grep -A6 'required_providers' versions.tf

# Inspect proxy/CA environment the installer will use
env | grep -iE 'proxy|cafile|ssl_cert'
```

## Expected Results

```text
$ curl -sS https://registry.terraform.io/.well-known/terraform.json
curl: (6) Could not resolve host: registry.terraform.io
```

A DNS/connection failure here confirms the connectivity case. If `curl` succeeds
but `init` still fails with "no available releases match," the problem is your
version constraints — compare them against the versions the registry lists.

## Resolution

1. For connectivity, fix DNS/egress or configure the proxy and trusted CA that
   the runner needs:

   ```bash
   export HTTPS_PROXY=http://proxy.corp:3128
   export SSL_CERT_FILE=/etc/ssl/certs/corp-ca.pem
   terraform init
   ```
2. For impossible constraints, correct them to a satisfiable range:

   ```hcl
   required_providers {
     aws = { source = "hashicorp/aws", version = "~> 5.60" }
   }
   ```
3. Fix any typo in the `source` address.
4. For air-gapped environments, point at a filesystem/network mirror and use
   `terraform init -plugin-dir=` or a CLI `provider_installation` mirror block.

## Validation

```bash
terraform init
# Expect: "Terraform has been successfully initialized!" with the provider
# downloaded at a matching version.
```

## Prevention

- Run a private provider mirror so CI never depends on the public registry.
- Pin satisfiable constraints with `~>` and test upgrades deliberately.
- Pre-flight runners with a registry reachability check before `init`.

## Related Errors

- [Terraform Failed to Install Provider](./terraform-failed-to-install-provider.md)
- [Terraform Module Not Installed](./terraform-module-not-installed.md)

## References

- [Terraform: Provider Requirements](https://developer.hashicorp.com/terraform/language/providers/requirements)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`terraform` · `init` · `registry` · `providers` · `production`
