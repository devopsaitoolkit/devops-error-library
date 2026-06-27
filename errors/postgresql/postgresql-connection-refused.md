---
title: "PostgreSQL Connection Refused"
slug: postgresql-connection-refused
technologies: [postgresql]
severity: high
tags: [postgresql, connectivity, networking, startup, production]
related: [postgresql-no-pg-hba-conf-entry, postgresql-too-many-connections]
last_reviewed: 2026-06-27
---

# PostgreSQL Connection Refused

## Error Message

```text
psql: error: connection to server at "db.internal" (10.0.3.21), port 5432 failed: Connection refused
	Is the server running on that host and accepting TCP/IP connections?
```

```text
psql: error: connection to server on socket "/var/run/postgresql/.s.PGSQL.5432" failed: No such file or directory
	Is the server running locally and accepting connections on that socket?
```

## Description

`Connection refused` is a TCP/transport-level failure: the client reached the
target host, but nothing was listening on the requested port, so the kernel
returned `ECONNREFUSED`. This happens *before* any PostgreSQL authentication or
`pg_hba.conf` evaluation — the server process either is not running, is not bound
to the address/port the client used, or a firewall is rejecting the packet. The
Unix-socket variant (`No such file or directory`) means the local server is not
running or its socket lives in a different directory than the client expects.

## Technologies

- postgresql (postmaster / listener, libpq client)

## Severity

**high** — no client can connect over the affected path. For a single-instance
database this is a full outage; for an HA setup it may be a failover trigger.

## Common Causes

1. The PostgreSQL service is stopped or crashed (most common).
2. `listen_addresses` is `localhost` (or empty), so the server never binds the
   network interface the client is using.
3. The client used the wrong port, or PostgreSQL is running on a non-default port.
4. A host firewall (firewalld/iptables/ufw) or a cloud security group is dropping
   or rejecting traffic to port 5432.
5. Unix-socket directory mismatch: client expects `/tmp` but the server writes its
   socket to `/var/run/postgresql` (or vice versa).

## Root Cause Analysis

libpq attempts a TCP `connect()` (or a Unix-domain `connect()` for local socket
hosts). If the destination port has no listening socket, the kernel immediately
replies with a TCP RST and libpq surfaces `Connection refused`. This is distinct
from a *timeout* (`Connection timed out`), which indicates packets are being
silently dropped — typically a firewall in `DROP` mode or an unreachable host.
Because the rejection happens at the transport layer, PostgreSQL never logs the
attempt: the client error is the only evidence. The job, then, is to prove
whether the server is up, what address/port it is bound to, and whether anything
in the network path is blocking the SYN.

## Diagnostic Commands

```bash
# Fastest health probe — does the server answer on host:port?
pg_isready -h db.internal -p 5432

# Is the service actually running?
systemctl status postgresql

# What is the server bound to? Look for 0.0.0.0:5432 or 127.0.0.1:5432
ss -ltnp | grep 5432

# Confirm the configured listen address and port from inside (if reachable locally)
sudo -u postgres psql -c "SHOW listen_addresses;" -c "SHOW port;"

# Recent server-side startup/crash messages
journalctl -u postgresql --since "30 min ago" --no-pager
```

## Expected Results

```text
# pg_isready when the listener is down:
db.internal:5432 - no response

# ss showing the server bound ONLY to loopback (remote clients get refused):
LISTEN 0  244  127.0.0.1:5432  0.0.0.0:*  users:(("postgres",pid=812,fd=6))

# Healthy: bound to all interfaces
LISTEN 0  244  0.0.0.0:5432    0.0.0.0:*  users:(("postgres",pid=812,fd=6))
```

## Resolution

1. If the service is down, start it and check why it stopped:

   ```bash
   sudo systemctl start postgresql
   sudo journalctl -u postgresql --since "1 hour ago" --no-pager
   ```
2. To accept remote connections, set `listen_addresses` in `postgresql.conf` and
   reload (a restart is required for `listen_addresses` changes):

   ```conf
   listen_addresses = '*'   # or a comma-separated list of specific IPs
   port = 5432
   ```

   ```bash
   sudo systemctl restart postgresql
   ```
3. Open the firewall to the trusted client range (example, firewalld):

   ```bash
   sudo firewall-cmd --add-rich-rule='rule family=ipv4 source address=10.0.0.0/16 port port=5432 protocol=tcp accept' --permanent
   sudo firewall-cmd --reload
   ```
4. For the socket variant, point the client at the correct directory with the
   `host` parameter, e.g. `psql -h /var/run/postgresql`.

## Validation

```bash
pg_isready -h db.internal -p 5432
# Expect: db.internal:5432 - accepting connections
psql -h db.internal -p 5432 -U app -d appdb -c "SELECT 1;"
```

## Prevention

- Monitor the listener with `pg_isready` from outside the host, not just locally.
- Manage `listen_addresses`, `port`, and firewall rules in configuration code so
  drift does not silently break connectivity.
- Add a startup health check / alert on the `postgresql` systemd unit so crashes
  page someone instead of being discovered by clients.

## Related Errors

- [PostgreSQL no pg_hba.conf entry](./postgresql-no-pg-hba-conf-entry.md)
- [PostgreSQL too many connections](./postgresql-too-many-connections.md)

## References

- [PostgreSQL: Connection Settings](https://www.postgresql.org/docs/current/runtime-config-connection.html)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`postgresql` · `connectivity` · `networking` · `startup` · `production`
