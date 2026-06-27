---
title: "OpenStack Heat Stack Create Failed (CREATE_FAILED)"
slug: openstack-heat-stack-create-failed
technologies: [openstack, heat]
severity: high
tags: [openstack, heat, orchestration, create-failed, stack, production]
related: [openstack-nova-no-valid-host-was-found]
last_reviewed: 2026-06-27
---

# OpenStack Heat Stack Create Failed (CREATE_FAILED)

## Error Message

```text
$ openstack stack show my-stack -c stack_status -c stack_status_reason -f value
CREATE_FAILED
Resource CREATE failed: ResourceInError: resources.web_server: \
Went to status ERROR due to "Message: No valid host was found., Code: 500"
```

```text
heat-engine[2410]: INFO heat.engine.stack [req-...] Stack CREATE FAILED (my-stack): \
Resource CREATE failed: NotFound: resources.web_net: Network <id> could not be found.
```

## Description

A Heat stack moved to `CREATE_FAILED` because at least one resource in the
template could not be created. Heat orchestrates resources in dependency order by
calling the underlying service APIs (Nova, Neutron, Cinder, etc.). When any of
those calls fails, the owning resource goes to `CREATE_FAILED`, the whole stack is
marked `CREATE_FAILED`, and `stack_status_reason` carries the first underlying
error. The real fault almost always lives in the downstream service, not in Heat.

## Technologies

- openstack (heat-engine, plus the services Heat calls: nova, neutron, cinder, glance)

## Severity

**high** — the entire stack deployment fails; dependent automation (autoscaling,
CI environments, tenant self-service) is blocked. Already-running stacks are
unaffected.

## Common Causes

1. A downstream resource genuinely fails — Nova `NoValidHost`, Neutron quota or
   subnet exhaustion, Cinder no storage, Glance image missing.
2. Template references a resource that does not exist — bad image/flavor/network
   name or ID, or a `get_resource`/`get_attr` to a sibling that already failed.
3. Quota exceeded for the tenant (instances, cores, RAM, floating IPs, volumes).
4. A circular or missing dependency / parameter the template never sets a value
   for.
5. Insufficient roles — the stack user lacks permission to create one of the
   resource types (e.g. missing `creator` role for Barbican secrets).

## Root Cause Analysis

heat-engine builds a dependency graph from the template and creates resources
bottom-up. For each resource it invokes the service client and polls until the
resource reaches its expected status. The first resource that errors propagates a
`ResourceInError`/`NotFound`/`Forbidden` up the graph; Heat stops, records the
reason on that resource, and fails the stack. Because Heat surfaces only the first
failure, the fix is to drill into the specific failed resource and then into the
service that owns it.

## Diagnostic Commands

```bash
# Top-level reason
openstack stack show my-stack -c stack_status -c stack_status_reason -f value

# Per-resource status — find the FAILED resource(s)
openstack stack resource list my-stack -n 5

# Full detail and the raw status reason for the failed resource
openstack stack resource show my-stack <resource-name>

# Chronological events for the stack (most recent failure last)
openstack stack event list my-stack --nested-depth 5

# heat-engine log for the request
journalctl -u devstack@h-eng --since "20 min ago" | grep -iE "FAILED|error|req-"

# If the failure is Nova/Neutron, drill into that service
openstack server show <id> -c fault -f value
openstack quota show
```

## Expected Results

```text
$ openstack stack resource list my-stack
+---------------+-------------------+-----------------+
| resource_name | resource_type     | resource_status |
+---------------+-------------------+-----------------+
| web_net       | OS::Neutron::Net  | CREATE_COMPLETE |
| web_server    | OS::Nova::Server  | CREATE_FAILED   |
+---------------+-------------------+-----------------+

# resource show then reveals the true cause, e.g.:
resource_status_reason | ResourceInError: ... No valid host was found.

# Healthy: every resource is CREATE_COMPLETE and stack_status is CREATE_COMPLETE.
```

## Resolution

1. Identify the failed resource with `stack resource list`, then read its
   `resource_status_reason` for the underlying error.
2. Fix the underlying service problem — add capacity for `NoValidHost`, raise
   quota, correct a missing network/image/flavor reference, or grant the missing
   role. (See the linked Nova runbook for `NoValidHost`.)
3. Correct the template if the reference itself is wrong:
   ```bash
   openstack stack update my-stack -t fixed-template.yaml \
     --parameter image=ubuntu-2204 --parameter flavor=m1.small
   ```
4. If the stack is unrecoverable, delete and recreate after the fix:
   ```bash
   openstack stack delete --yes my-stack
   openstack stack create -t template.yaml my-stack
   ```

## Validation

```bash
openstack stack show my-stack -c stack_status -f value   # Expect: CREATE_COMPLETE
openstack stack resource list my-stack                   # All CREATE_COMPLETE
```

## Prevention

- Validate templates before deploying: `openstack orchestration template validate
  -t template.yaml`.
- Pre-check tenant quotas against the template's resource counts.
- Pin image/flavor/network references to stable IDs or parameters with sane
  defaults.
- Test stacks in a staging tenant in CI before promoting templates.

## Related Errors

- [OpenStack Nova NoValidHost: No Valid Host Was Found](../nova/openstack-nova-no-valid-host-was-found.md)

## References

- [Heat troubleshooting](https://docs.openstack.org/heat/latest/admin/index.html)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`openstack` · `heat` · `orchestration` · `create-failed` · `stack` · `production`
