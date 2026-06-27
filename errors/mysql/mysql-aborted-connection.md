---
title: "MySQL Aborted Connection"
slug: mysql-aborted-connection
technologies: [mysql]
severity: medium
tags: [mysql, connections, networking, timeouts, production]
related: [mysql-too-many-connections, mysql-cant-connect-through-socket]
last_reviewed: 2026-06-27
---

# MySQL Aborted Connection

## Error Message

```text
[Note] [MY-010914] [Server] Aborted connection 84213 to db: 'appdb' user: 'app' host: '10.0.1.42' (Got timeout reading communication packets)
```

```text
[Warning] Aborted connection 90551 to db: 'appdb' user: 'app' host: '10.0.1.42' (Got an error reading communication packets)
```

On the client side this surfaces to the application as:

```text
ERROR 2013 (HY000): Lost connection to MySQL server during query
```

## Description

"Aborted connection" messages are written to the MySQL **error log** when a
client connection ends abnormally — the client did not send `COM_QUIT` before the
socket closed. The parenthetical reason is the diagnostic key:
*"Got timeout reading communication packets"* (idle past a timeout),
*"Got an error reading communication packets"* (network drop / client crash), or
*"interrupted while waiting"* . The application typically sees the matching
client-side `ERROR 2013`. A low rate is normal background noise; a rising rate
signals a real connectivity or pooling problem.

## Technologies

- mysql (connection handler / network layer)

## Severity

**medium** — individual queries fail and connections are recycled, which the app
can usually retry. It becomes high if a load balancer or firewall is silently
cutting healthy long-lived connections under load.

## Common Causes

1. A connection sat idle longer than `wait_timeout`/`interactive_timeout` and the
   server closed it; the pool then tried to reuse the dead connection.
2. A firewall, NAT, or load balancer idle-timeout silently dropped the TCP
   connection between client and server.
3. The client process crashed or was killed mid-query.
4. A single packet exceeded `max_allowed_packet` (large BLOB/row).
5. Network instability (packet loss, MTU/MSS issues) between app and database.

## Root Cause Analysis

The server expects a clean `COM_QUIT`. If a read on the connection fails or times
out first, it logs the abort with the reason it observed and increments
`Aborted_clients` (clean-loss) or `Aborted_connects` (failed during the
handshake/auth). The most common production pattern is the *idle-timeout
mismatch*: a connection pool keeps connections far longer than the server's
`wait_timeout` (default 28800s) or, more often, longer than an intermediate load
balancer's much shorter idle timeout. The connection is silently torn down, and
the next query on it fails with `ERROR 2013` while the server logs an aborted
connection.

## Diagnostic Commands

```bash
# Are aborts increasing, and which kind (during handshake vs after connect)?
mysql -u root -p -e "SHOW GLOBAL STATUS LIKE 'Aborted_%';"

# The timeouts that govern how long an idle connection survives
mysql -u root -p -e "SHOW VARIABLES LIKE 'wait_timeout'; SHOW VARIABLES LIKE 'interactive_timeout'; SHOW VARIABLES LIKE 'max_allowed_packet';"

# Read the actual abort reasons (timeout vs error vs packet) from the error log
sudo journalctl -u mysql --since "1 hour ago" | grep -i "aborted connection"

# Rule out a network-level idle reaper between app and DB
ss -tno state established '( dport = :3306 or sport = :3306 )'
```

## Expected Results

```text
| Aborted_clients  | 1842 |   <- connections closed without COM_QUIT
| Aborted_connects |   12 |   <- failed during handshake/auth
```

A fast-climbing `Aborted_clients` with *"Got timeout reading communication
packets"* in the log points to idle timeouts; *"Got an error reading…"* points
to network drops or client crashes; spikes correlated with large rows point to
`max_allowed_packet`.

## Resolution

1. Align timeouts: make the connection pool's max idle/lifetime *shorter* than
   both the server's `wait_timeout` and any load-balancer idle timeout, so the
   client retires connections before they are killed.
2. Enable pool connection validation/keepalive (e.g. test-on-borrow, or a periodic
   ping) so dead connections are detected before a query runs.
3. If large payloads cause aborts, raise `max_allowed_packet` on both server and
   client to fit the largest legitimate row:

   ```ini
   [mysqld]
   max_allowed_packet = 64M
   ```
4. Investigate the network path for an idle reaper or packet loss between app and
   database; increase the LB idle timeout or send TCP keepalives.
5. Ensure clients always close cleanly (`COM_QUIT`) rather than dropping sockets.

## Validation

```bash
mysql -u root -p -e "SHOW GLOBAL STATUS LIKE 'Aborted_clients';"
# Re-check after the change: the counter's growth rate should fall sharply.
```

## Prevention

- Keep pool idle/lifetime below the smallest timeout in the path (DB or LB).
- Turn on pool keepalive/validation queries.
- Monitor `Aborted_clients`/`Aborted_connects` rate, not just absolute value.
- Size `max_allowed_packet` for the largest row you actually store.

## Related Errors

- [MySQL Too Many Connections](./mysql-too-many-connections.md)
- [MySQL Can't Connect Through Socket](./mysql-cant-connect-through-socket.md)

## References

- [MySQL: Communication Errors and Aborted Connections](https://dev.mysql.com/doc/refman/8.0/en/communication-errors.html)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`mysql` · `connections` · `networking` · `timeouts` · `production`
