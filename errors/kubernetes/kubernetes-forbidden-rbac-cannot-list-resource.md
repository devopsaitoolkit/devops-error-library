---
title: "Kubernetes Forbidden: cannot list resource (RBAC)"
slug: kubernetes-forbidden-rbac-cannot-list-resource
technologies: [kubernetes]
severity: medium
tags: [kubernetes, rbac, authorization, serviceaccount, production]
related: [kubernetes-x509-certificate-signed-by-unknown-authority, kubernetes-createcontainerconfigerror]
last_reviewed: 2026-06-27
---

# Kubernetes Forbidden: cannot list resource (RBAC)

## Error Message

```text
Error from server (Forbidden): pods is forbidden: User
"system:serviceaccount:monitoring:prometheus" cannot list resource "pods"
in API group "" at the cluster scope
```

```text
E0627 10:02:48.771	1 reflector.go:138 ...: Failed to watch *v1.Endpoints:
  failed to list *v1.Endpoints: endpoints is forbidden: User
  "system:serviceaccount:monitoring:prometheus" cannot list resource
  "endpoints" in API group "" at the cluster scope
```

## Description

A `Forbidden` error is an *authorization* denial: the request authenticated
successfully (the identity is known) but RBAC has no rule granting that identity
the requested verb (`list`, `watch`, `get`, …) on the resource at the requested
scope. It is the most common controller/operator startup failure — a ServiceAccount
that lacks the (Cluster)Role bindings its workload needs. Note it is distinct from
`Unauthorized` (401), which means authentication itself failed.

## Technologies

- kubernetes (API server RBAC authorizer)

## Severity

**medium** — the workload runs but cannot perform the denied operation, so a
controller, exporter, or operator silently does nothing useful (no metrics, no
reconciliation). It is rarely a hard crash but is a functional outage of that
capability.

## Common Causes

1. The ServiceAccount has no Role/ClusterRole binding granting the verb on the
   resource.
2. A binding exists but at the wrong scope — a namespaced `RoleBinding` when the
   workload lists cluster-wide (`at the cluster scope`).
3. The Role grants the wrong `apiGroup` (e.g. omitting the core group `""`, or
   using the wrong group for a CRD).
4. The pod runs as the namespace `default` ServiceAccount instead of the intended
   one, so it inherits no permissions.
5. The verb is missing — the rule grants `get` but the client needs `list`/`watch`.

## Root Cause Analysis

Every API request carries an authenticated identity (here a ServiceAccount). The
RBAC authorizer searches all Roles/ClusterRoles bound to that identity for a rule
matching the request's `verb` + `apiGroup` + `resource` + scope. RBAC is purely
additive and default-deny: if no rule matches, the request is denied with
`Forbidden`, and the message states the exact user, verb, resource, apiGroup, and
scope that failed. Each of those four fields is a place a binding can be wrong, so
the message is effectively a checklist for the missing rule.

## Diagnostic Commands

```bash
# Confirm exactly what the ServiceAccount can and cannot do
kubectl auth can-i list pods \
  --as=system:serviceaccount:monitoring:prometheus -A

# Which (Cluster)RoleBindings reference this ServiceAccount
kubectl get clusterrolebinding,rolebinding -A -o json | jq '
  .items[] | select(.subjects[]?
  | .kind=="ServiceAccount" and .name=="prometheus"
  and .namespace=="monitoring") | .metadata.name'

# The rules of the role that is (or should be) bound
kubectl get clusterrole <role> -o yaml

# Which ServiceAccount the pod actually runs as
kubectl get pod <pod> -n monitoring \
  -o jsonpath='{.spec.serviceAccountName}{"\n"}'
```

## Expected Results

```text
cannot list resource "pods" in API group "" at the cluster scope
```

```text
$ kubectl auth can-i list pods --as=system:serviceaccount:monitoring:prometheus -A
no
```

`at the cluster scope` means a ClusterRole/ClusterRoleBinding is required (a
namespaced RoleBinding will not satisfy it). API group `""` is the core group. A
granted identity returns `yes` from `kubectl auth can-i`.

## Resolution

1. Grant the missing permission with a ClusterRole and bind it to the
   ServiceAccount at the correct scope:

   ```yaml
   apiVersion: rbac.authorization.k8s.io/v1
   kind: ClusterRole
   metadata: { name: prometheus-reader }
   rules:
   - apiGroups: [""]
     resources: ["pods", "endpoints", "services", "nodes"]
     verbs: ["get", "list", "watch"]
   ---
   apiVersion: rbac.authorization.k8s.io/v1
   kind: ClusterRoleBinding
   metadata: { name: prometheus-reader }
   roleRef:
     apiGroup: rbac.authorization.k8s.io
     kind: ClusterRole
     name: prometheus-reader
   subjects:
   - kind: ServiceAccount
     name: prometheus
     namespace: monitoring
   ```
2. Ensure the workload sets `serviceAccountName` to the intended SA, not `default`.
3. Match the `apiGroups` to the resource (core = `""`; CRDs use their own group).
4. Include every verb the client uses (`list` and `watch` for informers, not just
   `get`).

## Validation

```bash
kubectl auth can-i list pods \
  --as=system:serviceaccount:monitoring:prometheus -A
# Expect: yes. The controller's reflector errors stop in its logs.
```

## Prevention

- Grant least privilege explicitly; avoid binding to `cluster-admin`.
- Verify SA permissions in CI with `kubectl auth can-i --list --as=<sa>`.
- Pin each workload to a dedicated ServiceAccount, never `default`.
- Review CRD bindings carefully — the apiGroup is easy to get wrong.

## Related Errors

- [Kubernetes x509 certificate signed by unknown authority](./kubernetes-x509-certificate-signed-by-unknown-authority.md)
- [Kubernetes CreateContainerConfigError](./kubernetes-createcontainerconfigerror.md)

## References

- [Kubernetes: Using RBAC Authorization](https://kubernetes.io/docs/reference/access-authn-authz/rbac/)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`kubernetes` · `rbac` · `authorization` · `serviceaccount` · `production`
