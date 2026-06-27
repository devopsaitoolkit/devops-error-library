---
title: "PostgreSQL No pg_hba.conf Entry"
slug: postgresql-no-pg-hba-conf-entry
technologies: [postgresql]
severity: high
tags: [postgresql, authentication, pg-hba, security, production]
related: [postgresql-password-authentication-failed, postgresql-connection-refused]
last_reviewed: 2026-06-27
---

# PostgreSQL No pg_hba.conf Entry

## Error Message

```text
FATAL:  no pg_hba.conf entry for host "10.0.4.88", user "app_user", database "appdb", no encryption
```

```text
FATAL:  no pg_hba.conf entry for host "10.0.4.88", user "app_user", database "appdb", SSL off
```

## Description

`pg_hba.conf` (Host-Based Authentication) is PostgreSQL's connection firewall: an
ordered list of rules matched on connection type, source address, database, and
user. When a connection reaches the server but no rule matches the
`(type, address, database, user, SSL state)` tuple, PostgreSQL rejects it with
`FATAL: no pg_hba.conf entry`. This means the network path is fine — the server
heard the client — but the policy has no rule permitting that combination. It is
the layer *after* `Connection refused` (which is purely transport) and *before*
the password check.

## Technologies

- postgresql (host-based authentication, `pg_hba.conf`)

## Severity

**high** — affected clients cannot authenticate at all over that path. Often
appears suddenly after a network change (new subnet, new pod CIDR) and blocks a
whole class of clients.

## Common Causes

1. The client's source IP/subnet is not covered by any `host` rule's CIDR — the
   most common cause after infra changes.
2. No rule for that specific database or user (rules are filtered on both).
3. An SSL-state mismatch: only `hostssl` rules exist but the client connected
   without TLS (`SSL off`), or only `hostnossl` rules exist and the client used TLS.
4. The rule exists but a more-specific earlier rule (e.g. a `reject` line) matched
   first — order matters; the first match wins.
5. `pg_hba.conf` was edited but never reloaded, so the running config is stale.

## Root Cause Analysis

On each connection PostgreSQL scans `pg_hba.conf` top to bottom and uses the
**first** line whose type, client address, database, and user all match the
incoming connection; that line's method decides authentication. If it scans off
the end without a match, it emits this `FATAL`. Because matching is exhaustive on
all four fields plus SSL state, a connection from an un-whitelisted subnet, or a
plaintext connection where only `hostssl` rules exist, simply finds no match. The
"first match wins" rule also means a broad `reject` placed above your `host` rule
will shadow it — so reading rules in order, not just grepping for the user, is
essential.

## Diagnostic Commands

```bash
# Inspect the live, parsed HBA rules WITHOUT opening files (read-only catalog)
psql -c "SELECT line_number, type, database, user_name, address, auth_method
         FROM pg_hba_file_rules ORDER BY line_number;"

# Any parse errors in pg_hba.conf?
psql -c "SELECT line_number, error FROM pg_hba_file_rules WHERE error IS NOT NULL;"

# What address does the client present? (run from the client host)
curl -s ifconfig.me; echo
# and confirm the server saw it in the FATAL log line:
sudo journalctl -u postgresql --since "20 min ago" --no-pager | grep "no pg_hba.conf entry"

# Where is the config and is SSL on?
psql -c "SHOW hba_file; SHOW ssl;"
```

## Expected Results

```text
 line_number | type    | database | user_name | address       | auth_method
-------------+---------+----------+-----------+---------------+--------------
          88 | host    | appdb    | app_user  | 10.0.3.0/24   | scram-sha-256
```

If the failing client is `10.0.4.88` but the only rule covers `10.0.3.0/24`, the
source subnet is not whitelisted — no rule matches and the connection is rejected.

## Resolution

1. Add a rule covering the client's subnet, database, and user, using a strong
   method. Append to `pg_hba.conf`:

   ```conf
   # TYPE  DATABASE  USER      ADDRESS        METHOD
   hostssl appdb     app_user  10.0.4.0/24    scram-sha-256
   ```
2. Reload so the new rules take effect (no restart needed for HBA changes):

   ```bash
   sudo systemctl reload postgresql
   # or: psql -c "SELECT pg_reload_conf();"
   ```
3. For an SSL-state mismatch, make the client connect with the matching mode
   (e.g. `sslmode=require`) or add the appropriate `hostssl`/`hostnossl` rule.
4. Check rule order — ensure no earlier `reject`/broader line shadows yours.

## Validation

```bash
# Confirm the new rule is loaded
psql -c "SELECT line_number, address, auth_method FROM pg_hba_file_rules WHERE database = '{appdb}';"
# Then connect from the previously rejected host:
psql "host=db.internal user=app_user dbname=appdb sslmode=require" -c "SELECT 1;"
```

## Prevention

- Manage `pg_hba.conf` in version control / IaC so subnet changes update the rules.
- Prefer narrow CIDRs and `hostssl` over broad `0.0.0.0/0` `host` rules.
- Validate parse errors via `pg_hba_file_rules` in CI before reloading.
- Alert on `no pg_hba.conf entry` log lines — they flag both misconfig and probes.

## Related Errors

- [PostgreSQL password authentication failed](./postgresql-password-authentication-failed.md)
- [PostgreSQL Connection Refused](./postgresql-connection-refused.md)

## References

- [PostgreSQL: The pg_hba.conf File](https://www.postgresql.org/docs/current/auth-pg-hba-conf.html)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`postgresql` · `authentication` · `pg-hba` · `security` · `production`
