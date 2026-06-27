---
title: "Terraform Failed to Install Provider"
slug: terraform-failed-to-install-provider
technologies: [terraform]
severity: high
tags: [terraform, init, providers, checksum, production]
related: [terraform-failed-to-query-available-provider-packages, terraform-error-configuring-provider]
last_reviewed: 2026-06-27
---

# Terraform Failed to Install Provider

## Error Message

```text
╷
│ Error: Failed to install provider
│
│ Error while installing hashicorp/aws v5.60.0: the local package for
│ registry.terraform.io/hashicorp/aws 5.60.0 doesn't match any of the checksums
│ recorded in the dependency lock file. If you recently updated the lock file,
│ you may need to run "terraform providers lock" again with the appropriate
│ platform arguments.
╵
```

```text
│ Error while installing hashicorp/aws v5.60.0: open
│ /home/ci/.terraform.d/plugins/...: permission denied
```

## Description

After Terraform has *selected* a provider version, it downloads (or copies from
cache/mirror) the actual provider package, verifies its checksum against the
`.terraform.lock.hcl` dependency lock file, and unpacks it into `.terraform/`.
This error means the installation step itself failed — the download was
corrupted, the checksum didn't match the lock file, the platform isn't recorded
in the lock, or the local plugin directory couldn't be written.

## Technologies

- terraform (init, provider installer, dependency lock)

## Severity

**high** — without an installed provider, `init` fails and no `plan`/`apply` can
run. Checksum mismatches are also a security signal that must not be bypassed
blindly.

## Common Causes

1. The `.terraform.lock.hcl` records checksums only for some platforms, and you
   are running on one (e.g. `linux_arm64`) that isn't covered.
2. A corrupted or truncated download (flaky network, partial cache).
3. The lock file is stale after a manual provider version bump.
4. Filesystem permission/disk-space problems writing into the plugin cache or
   `.terraform/` directory.
5. A registry mirror serving a package whose hash genuinely differs from the
   lock — a real integrity warning.

## Root Cause Analysis

The dependency lock file pins both the exact provider version *and* a set of
`h1:`/`zh:` checksums, one group per platform Terraform has previously seen. On
install, Terraform recomputes the package hash and demands it match a recorded
checksum for the *current* platform. If your team generated the lock only on
macOS but CI runs on Linux ARM, the running platform's checksum is absent and the
install is rejected — even though the package is legitimate. This platform-
coverage gap is the most common (and most surprising) trigger; genuine
corruption and permission errors are the others.

## Diagnostic Commands

```bash
# Verbose install to see exactly which step failed
TF_LOG=debug terraform init 2>&1 | tail -40

# Show which platforms the lock file covers for the provider
grep -A8 'hashicorp/aws' .terraform.lock.hcl

# Confirm the current platform Terraform is running on
terraform version

# Check permissions and free space on the plugin cache location
ls -ld ~/.terraform.d/plugin-cache .terraform/providers 2>/dev/null
df -h .
```

## Expected Results

```text
$ grep -A8 'hashicorp/aws' .terraform.lock.hcl
provider "registry.terraform.io/hashicorp/aws" {
  version     = "5.60.0"
  hashes = [
    "h1:darwin_arm64checksum...",
  ]
}
```

A `hashes` list that lacks the running platform (no `linux_amd64`/`linux_arm64`
entry) confirms the platform-coverage gap. A `permission denied` line in the
debug log points at the filesystem case instead.

## Resolution

1. For the platform-coverage gap, regenerate the lock to include every platform
   CI uses, then commit it:

   ```bash
   terraform providers lock \
     -platform=linux_amd64 -platform=linux_arm64 -platform=darwin_arm64
   ```
2. For a corrupted download, clear the cache and re-init:

   ```bash
   rm -rf .terraform/providers
   terraform init
   ```
3. Fix directory permissions / free disk space for the plugin cache.
4. If the checksum mismatch is from an untrusted mirror, do **not** override it —
   verify the provider source and integrity before proceeding.

## Validation

```bash
terraform init
# Expect: "Installed hashicorp/aws v5.60.0 ... (signed by HashiCorp)" and
# "Terraform has been successfully initialized!"
```

## Prevention

- Run `terraform providers lock` for all target platforms and commit the lock
  file; keep it under review.
- Use a shared `plugin_cache_dir` to reduce repeated downloads.
- Treat checksum mismatches as integrity events, not nuisances.

## Related Errors

- [Terraform Failed to Query Available Provider Packages](./terraform-failed-to-query-available-provider-packages.md)
- [Terraform Error Configuring Provider](./terraform-error-configuring-provider.md)

## References

- [Terraform: Dependency Lock File](https://developer.hashicorp.com/terraform/language/files/dependency-lock)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`terraform` · `init` · `providers` · `checksum` · `production`
