---
title: "Kubernetes x509 certificate signed by unknown authority"
slug: kubernetes-x509-certificate-signed-by-unknown-authority
technologies: [kubernetes]
severity: high
tags: [kubernetes, tls, certificates, api-server, production]
related: [kubernetes-node-not-ready, kubernetes-errimagepull]
last_reviewed: 2026-06-27
---

# Kubernetes x509 certificate signed by unknown authority

## Error Message

```text
Unable to connect to the server: x509: certificate signed by unknown authority
```

```text
E0627 09:31:02.114	1 reflector.go:138 k8s.io/client-go/...: Failed to watch
  *v1.Endpoints: failed to list *v1.Endpoints: Get
  "https://10.96.0.1:443/api/v1/endpoints": x509: certificate signed by
  unknown authority (possibly because of "crypto/rsa: verification error"
  while trying to verify candidate authority certificate "kubernetes")
```

## Description

`x509: certificate signed by unknown authority` is a TLS trust failure: the client
(kubectl, a controller, the kubelet, or a webhook) received a server certificate
whose signing CA is not in the client's trust bundle. In Kubernetes this most
often means the CA the client trusts does not match the CA that signed the API
server (or a webhook, registry, or admission endpoint) it is talking to — typically
after a cluster rebuild, a CA rotation, or a stale `kubeconfig`.

## Technologies

- kubernetes (API server TLS, client-go, kubelet, admission webhooks)

## Severity

**high** — affected clients cannot talk to the endpoint at all. If the kubelet or
core controllers cannot reach the API server, nodes go NotReady and the control
plane effectively loses those components; a broken webhook CA can block all writes
to a resource.

## Common Causes

1. A stale `kubeconfig` with the old `certificate-authority-data` after the cluster
   (and its CA) was recreated.
2. CA rotation where clients were not updated with the new CA bundle.
3. A self-signed or private-CA endpoint (registry, webhook, OIDC) whose CA is not
   in the trust store.
4. Connecting to the API server via an IP/hostname not in the cert's SANs (related
   but distinct: that yields a hostname mismatch, often alongside trust errors).
5. A mutating/validating webhook whose `caBundle` no longer matches the serving
   cert (e.g. cert-manager re-issued without updating the webhook config).

## Root Cause Analysis

TLS clients verify a server's certificate chain up to a trusted root. The client
holds a CA bundle (in kubeconfig `certificate-authority-data`, the kubelet's CA
file, or a webhook's `caBundle`). When the presented server cert was signed by a CA
not present in that bundle, chain verification fails and Go's crypto library
returns `x509: certificate signed by unknown authority`. The fix is always to make
the client trust the *correct, current* CA — not to disable verification. Identify
which client and which endpoint by reading the failing component's logs.

## Diagnostic Commands

```bash
# Which CA the current kubeconfig trusts (decode and inspect)
kubectl config view --raw \
  -o jsonpath='{.clusters[0].cluster.certificate-authority-data}' \
  | base64 -d | openssl x509 -noout -issuer -subject -dates

# The cert the API server actually presents (and its issuer/SANs)
echo | openssl s_client -connect <api-host>:6443 2>/dev/null \
  | openssl x509 -noout -issuer -subject -ext subjectAltName

# Webhook caBundle vs the serving cert it points to
kubectl get validatingwebhookconfiguration <name> \
  -o jsonpath='{.webhooks[0].clientConfig.caBundle}' | base64 -d \
  | openssl x509 -noout -issuer -dates

# kubelet TLS errors reaching the API server
journalctl -u kubelet -n 100 --no-pager | grep -i x509
```

## Expected Results

```text
issuer= CN = kubernetes      # what the client trusts
issuer= CN = kubernetes-new  # what the server actually presents -> mismatch
```

If the kubeconfig's trusted issuer/serial differs from the issuer of the cert the
server presents, that is the mismatch. A healthy setup shows the same CA on both
sides and unexpired dates.

## Resolution

1. Refresh the client's CA bundle from the live cluster's current CA (do not skip
   TLS verification in production):

   ```bash
   # Regenerate kubeconfig from the cluster's real CA
   kubectl config set-cluster <cluster> \
     --certificate-authority=/etc/kubernetes/pki/ca.crt --embed-certs=true
   ```
2. For private-CA endpoints (registry/OIDC), install the CA into the node trust
   store or the relevant component's CA config.
3. For webhooks, update `clientConfig.caBundle` to the current serving CA
   (cert-manager's `ca-injector` can keep this in sync automatically).
4. After CA rotation, distribute the new CA to every kubeconfig and controller
   before retiring the old one.

## Validation

```bash
kubectl get --raw='/readyz'
# Expect: "ok" with no x509 error, confirming the client trusts the API server.
```

## Prevention

- Automate CA bundle distribution and webhook `caBundle` injection
  (cert-manager ca-injector).
- Treat `kubeconfig` files as cluster-specific; regenerate after any rebuild.
- Never set `insecure-skip-tls-verify` in production as a "fix."
- Alert on certificate expiry across API server, kubelet, and webhooks.

## Related Errors

- [Kubernetes Node NotReady](./kubernetes-node-not-ready.md)
- [Kubernetes ErrImagePull](./kubernetes-errimagepull.md)

## References

- [Kubernetes: PKI Certificates and Requirements](https://kubernetes.io/docs/setup/best-practices/certificates/)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`kubernetes` · `tls` · `certificates` · `api-server` · `production`
