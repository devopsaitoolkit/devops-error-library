---
title: "Grafana Plugin Unsigned"
slug: grafana-plugin-unsigned
technologies: [grafana]
severity: medium
tags: [grafana, plugin, signature, security, production]
related: [grafana-datasource-bad-gateway, grafana-failed-to-load-dashboards]
last_reviewed: 2026-06-27
---

# Grafana Plugin Unsigned

## Error Message

```text
t=2026-06-24T08:14:09+0000 lvl=warn msg="Skipping loading plugin due to problem with signature" logger=plugin.signature.validator pluginID=acme-custompanel status=unsigned
```

```text
Plugin error: signature check failed: unsigned plugin
```

```text
plugin "acme-custompanel" is unsigned and was not loaded
```

## Description

Since Grafana 7, plugins must be cryptographically signed by Grafana. On startup,
the `plugin.signature.validator` checks each installed plugin; any plugin with no
valid signature (`status=unsigned`), an `invalid` signature, or one whose files
have been modified (`modified`) is **not loaded** unless explicitly allowed. The
plugin then disappears from the UI and any data source/panel that depends on it
breaks. This is a security control, not a bug — it prevents loading tampered or
untrusted code.

## Technologies

- grafana (plugin signature validator / plugin loader)

## Severity

**medium** — only dashboards/data sources using the unsigned plugin are affected;
the rest of Grafana runs normally. It is higher if the unsigned plugin is a core
data source for many dashboards.

## Common Causes

1. A community/internal plugin was installed manually (copied into the plugins
   dir) and was never signed.
2. The plugin is genuinely unsigned/private (in-house panel or data source).
3. `status=modified` — files in a signed plugin were edited, invalidating the
   signature.
4. `status=invalid` — wrong signature type for the install location (e.g. a
   `private` sign for a different root URL).
5. Plugin version mismatch after a partial upgrade.

## Root Cause Analysis

At boot, Grafana reads each plugin's `MANIFEST.txt` and verifies it against
Grafana's signing key, then checks that the plugin files match the manifest
hashes. If verification fails or the manifest is absent, the validator marks the
plugin (`unsigned`/`invalid`/`modified`) and the loader skips it. Skipped plugins
do not register their panels or data sources, so anything referencing them errors
or vanishes. The `status` field is the key: `unsigned` (no manifest) is handled
differently from `modified` (tampered) or `invalid` (wrong sign).

## Diagnostic Commands

```bash
# Startup signature warnings/errors per plugin
journalctl -u grafana-server --since "20 min ago" | grep -i "signature\|plugin.*unsigned\|skipping loading plugin"

# List installed plugins and signature state via API (admin, read-only)
curl -s -H "Authorization: Bearer $GRAFANA_TOKEN" \
  http://localhost:3000/api/plugins | jq '.[] | {id, signature, signatureType, enabled}'

# List installed plugins on disk
grafana-cli plugins ls

# Current allow-list and plugins dir (read-only)
grep -Ei "allow_loading_unsigned_plugins|^\s*plugins\s*=" /etc/grafana/grafana.ini
```

## Expected Results

```text
{
  "id": "acme-custompanel",
  "signature": "unsigned",
  "signatureType": "",
  "enabled": false
}
```

`signature: unsigned` confirms the plugin was skipped for lack of a signature.
`modified` means files were changed; `valid` is the healthy state.

## Resolution

1. **Preferred:** install a properly signed build of the plugin from the Grafana
   catalog:

   ```bash
   grafana-cli plugins install acme-custompanel
   sudo systemctl restart grafana-server
   ```
2. For a genuinely private/in-house plugin, sign it with the Grafana plugin
   signing toolkit (`@grafana/sign-plugin`) for your root URL.
3. Only as a deliberate, audited exception, allow specific unsigned plugins:

   ```ini
   [plugins]
   allow_loading_unsigned_plugins = acme-custompanel
   ```
   Restart Grafana. **Risk:** this disables a security control — scope it to
   exact plugin IDs and never use it for plugins you do not control.
4. For `status=modified`, reinstall the plugin cleanly to restore original files.

## Validation

```bash
# Plugin now reports a valid signature and is enabled
curl -s -H "Authorization: Bearer $GRAFANA_TOKEN" \
  http://localhost:3000/api/plugins/acme-custompanel/settings \
  | jq '{signature, enabled}'   # Expect: signature "valid"/"internal", enabled true
```

## Prevention

- Install plugins from the official catalog so they arrive signed.
- Sign in-house plugins as part of CI and pin versions.
- Treat `allow_loading_unsigned_plugins` as a break-glass setting, reviewed in
  code review.

## Related Errors

- [Grafana Data Source Bad Gateway](./grafana-datasource-bad-gateway.md)
- [Grafana Failed to Load Dashboards](./grafana-failed-to-load-dashboards.md)

## References

- [Grafana plugin signature verification](https://grafana.com/docs/grafana/latest/administration/plugin-management/#plugin-signatures)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`grafana` · `plugin` · `signature` · `security` · `production`
