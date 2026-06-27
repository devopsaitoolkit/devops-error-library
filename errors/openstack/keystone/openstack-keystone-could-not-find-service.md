---
title: "OpenStack Keystone Could Not Find Service"
slug: openstack-keystone-could-not-find-service
technologies: [openstack, keystone]
severity: high
tags: [openstack, keystone, catalog, endpoint, service, production]
related: [openstack-keystone-401-unauthorized]
last_reviewed: 2026-06-27
---

# OpenStack Keystone Could Not Find Service

## Error Message

```text
public endpoint for image service in RegionOne region not found
```

```text
Could not find service nova. (HTTP 404) (Request-ID: req-...)
EndpointNotFound: public endpoint for compute service in RegionOne region not found
```

## Description

The OpenStack client (or one service calling another) asked Keystone's service
catalog for an endpoint of a given service type and region, and the catalog had
no matching entry. Every API client resolves the target URL through the catalog
returned with the token; if the requested `service-type`/`interface`/`region`
combination is absent, the client cannot even form a request URL. This is a
catalog/discovery failure, distinct from authentication (401) or a service being
down.

## Technologies

- openstack (keystone catalog: services + endpoints, keystoneauth in clients)

## Severity

**high** — clients cannot locate the affected service at all, so every operation
against it fails immediately. If it is a core service (compute, image, network),
large parts of the cloud become unusable from the CLI/API.

## Common Causes

1. The endpoint was never created, or only some interfaces (`public`/`internal`/
   `admin`) were registered, while the client requested a missing one.
2. Region mismatch — the endpoint is in `RegionOne` but the client requests
   `regionTwo` (or `OS_REGION_NAME` is unset/wrong).
3. The service or its endpoints were deleted/disabled during maintenance.
4. A typo in the registered `service-type` (e.g. `volume` vs `volumev3`) or
   `interface` so it does not match the client's lookup.
5. Wrong `OS_INTERFACE`/`--os-interface` (asking for `internal` when only
   `public` exists).

## Root Cause Analysis

Keystone's catalog is built from two tables: services (type + name) and endpoints
(URL + interface + region, tied to a service). When a token is issued, the catalog
is rendered for the scope. `keystoneauth` filters that catalog by service type,
interface, and region. If the filter matches zero rows, it raises
`EndpointNotFound`. So the root cause is always a missing or mismatched catalog
row — either it was never created, lives in another region, was deleted, or uses a
type/interface string the client is not looking for.

## Diagnostic Commands

```bash
# Full catalog as seen for the current token — the source of truth
openstack catalog list

# Focused view for the failing service type
openstack catalog show compute     # or image, network, volumev3, etc.

# Registered endpoints with their region and interface
openstack endpoint list --service compute

# Registered services and their types
openstack service list

# What region/interface is the client actually requesting?
env | grep -E "^OS_(REGION_NAME|INTERFACE)"
```

## Expected Results

```text
$ openstack endpoint list --service compute
+----------------------------------+-----------+--------------+--------------+
| ID                               | Region    | Service Type | Interface    |
+----------------------------------+-----------+--------------+--------------+
| a1b2...                          | RegionOne | compute      | public       |
| c3d4...                          | RegionOne | compute      | internal     |
+----------------------------------+-----------+--------------+--------------+
# Missing 'admin' interface, or no row for the requested region -> EndpointNotFound.

# Healthy: a row exists for the requested service-type + region + interface.
```

## Resolution

1. Confirm which interface/region the client needs, then create the missing
   endpoint:
   ```bash
   openstack endpoint create --region RegionOne compute public \
     http://compute.example.com:8774/v2.1
   ```
2. Re-enable a disabled service or endpoint:
   ```bash
   openstack service set --enable nova
   openstack endpoint set --enable <endpoint-id>
   ```
3. Fix a region/interface mismatch on the client side instead of the catalog when
   the catalog is correct:
   ```bash
   export OS_REGION_NAME=RegionOne
   export OS_INTERFACE=public
   ```
4. Correct a wrong `service-type` by re-registering the service/endpoint with the
   exact type the clients expect (e.g. `volumev3`).

## Validation

```bash
openstack catalog show compute        # now lists the endpoint
openstack server list                 # resolves and returns without EndpointNotFound
```

## Prevention

- Manage catalog entries via config management/IaC so all three interfaces and
  every region are created consistently.
- After adding a region or service, run a smoke test that calls each service type.
- Avoid deleting endpoints during maintenance; disable services instead, and keep
  a backup of the catalog.

## Related Errors

- [OpenStack Keystone 401 Unauthorized](./openstack-keystone-401-unauthorized.md)

## References

- [Keystone service catalog](https://docs.openstack.org/keystone/latest/admin/manage-services.html)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`openstack` · `keystone` · `catalog` · `endpoint` · `service` · `production`
