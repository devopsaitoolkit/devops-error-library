---
title: "MySQL Access Denied for User"
slug: mysql-access-denied-for-user
technologies: [mysql]
severity: high
tags: [mysql, authentication, privileges, access-denied, production]
related: [mysql-too-many-connections, mysql-cant-connect-through-socket]
last_reviewed: 2026-06-27
---

# MySQL Access Denied for User

## Error Message

```text
ERROR 1045 (28000): Access denied for user 'app'@'10.0.1.42' (using password: YES)
```

```text
ERROR 1045 (28000): Access denied for user 'root'@'localhost' (using password: NO)
```

## Description

`ERROR 1045 (28000)` is raised by the MySQL/MariaDB server during the
authentication handshake, before any SQL is executed. The server has matched the
incoming connection against the `mysql.user` table (or `mysql.global_priv` on
MariaDB 10.4+) and either found no account that matches the supplied
user/host/password combination, or the password failed verification. The
`(using password: YES|NO)` suffix tells you whether the client actually sent a
password.

The most subtle part is *host matching*: MySQL accounts are identified by the
pair `'user'@'host'`, so `'app'@'localhost'` and `'app'@'%'` are two distinct
accounts with potentially different passwords and privileges.

## Technologies

- mysql (authentication / privilege subsystem)

## Severity

**high** — the affected client cannot connect at all. For an application account
this is a full outage of every service using those credentials until the grant
or password is corrected.

## Common Causes

1. Wrong password, or a password that contains shell-special characters that got
   mangled before reaching the client.
2. The account exists for a different host pattern than the one the client
   connects from (`'app'@'localhost'` vs `'app'@'10.0.1.42'` vs `'app'@'%'`).
3. The account does not exist at all (typo in the username, or it was never
   created on this server).
4. An authentication-plugin mismatch — the account uses `caching_sha2_password`
   or `auth_socket` but the client/driver only speaks `mysql_native_password`.
5. `skip-networking` or `bind-address` restricts where connections may originate.

## Root Cause Analysis

When a client connects, the server resolves the client IP/hostname and scans the
user table for the most specific matching `host` entry, then verifies the
password against the stored authentication string using the account's plugin. A
mismatch at any stage — no matching host row, a different stored hash, or a
plugin the client cannot satisfy — produces `ERROR 1045`. Because `localhost`
connections go over a Unix socket and use the `'user'@'localhost'` row while TCP
connections to `127.0.0.1` use a different host row, the same credentials can
succeed one way and fail the other.

## Diagnostic Commands

```bash
# Which accounts and host patterns exist for this username (run as an admin user)
mysql -u root -p -e "SELECT user, host, plugin FROM mysql.user WHERE user='app';"

# What user the server thinks you are vs. who you authenticated as
mysql -u app -p -e "SELECT CURRENT_USER(), USER();"

# Confirm the server is listening where the client connects
ss -ltnp | grep 3306

# Server-side auth errors are logged here
sudo journalctl -u mysql --since "10 min ago" | grep -i "access denied"
```

## Expected Results

```text
+------+-----------+-----------------------+
| user | host      | plugin                |
+------+-----------+-----------------------+
| app  | localhost | auth_socket           |
| app  | %         | caching_sha2_password |
+------+-----------+-----------------------+
```

If `CURRENT_USER()` differs from `USER()`, the server fell back to a less
specific account (often an anonymous `''@'localhost'` row) than you intended.
A `plugin` of `auth_socket` means password auth will always fail for TCP clients.

## Resolution

1. Confirm the correct account exists for the client's host. If it does not,
   create or adjust it (replace the host pattern with the real client network):

   ```sql
   CREATE USER 'app'@'10.0.1.%' IDENTIFIED BY '<password>';
   GRANT SELECT, INSERT, UPDATE, DELETE ON appdb.* TO 'app'@'10.0.1.%';
   FLUSH PRIVILEGES;
   ```
2. If the password is wrong, reset it (this also fixes a plugin mismatch by
   keeping the same plugin):

   ```sql
   ALTER USER 'app'@'10.0.1.%' IDENTIFIED BY '<new-password>';
   ```
3. For a driver that cannot do `caching_sha2_password`, either upgrade the driver
   or switch the account to `mysql_native_password` (least-secure last resort):

   ```sql
   ALTER USER 'app'@'10.0.1.%'
     IDENTIFIED WITH mysql_native_password BY '<password>';
   ```
4. Remove anonymous accounts (`''@'localhost'`) that shadow real users.

## Validation

```bash
mysql -h <host> -u app -p -e "SELECT CURRENT_USER();"
# Expect: 'app@10.0.1.%' (or your intended host) and no ERROR 1045.
```

## Prevention

- Use a single, explicit host pattern per account and document it.
- Run `mysql_secure_installation` on every new server to drop anonymous users.
- Keep credentials in a secret manager so passwords are not edited by hand.
- Pin and test the authentication plugin against the driver version in CI.

## Related Errors

- [MySQL Too Many Connections](./mysql-too-many-connections.md)
- [MySQL Can't Connect Through Socket](./mysql-cant-connect-through-socket.md)

## References

- [MySQL: Access Denied Errors](https://dev.mysql.com/doc/refman/8.0/en/problems-connecting.html)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`mysql` · `authentication` · `privileges` · `access-denied` · `production`
