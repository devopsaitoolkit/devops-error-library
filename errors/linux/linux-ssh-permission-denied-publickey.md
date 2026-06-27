---
title: "SSH Permission denied (publickey)"
slug: linux-ssh-permission-denied-publickey
technologies: [linux]
severity: medium
tags: [linux, ssh, authentication, permissions, production]
related: [linux-systemd-failed-to-start-unit, linux-read-only-file-system]
last_reviewed: 2026-06-27
---

# SSH Permission denied (publickey)

## Error Message

```text
git@github.com: Permission denied (publickey).
user@host: Permission denied (publickey).
```

```text
sshd[2210]: Authentication refused: bad ownership or modes for directory /home/deploy/.ssh
sshd[2210]: Connection closed by authenticating user deploy 10.0.0.5 port 51022 [preauth]
```

## Description

`Permission denied (publickey)` means the SSH server offered public-key
authentication, the client presented one or more keys, and **none were accepted**
— so the connection is refused. It is an *authentication* failure, not a network
or connectivity problem (you reached `sshd` fine). The most common and most
surprising cause is not a missing key at all but **wrong file permissions/
ownership** on `~/.ssh`, `authorized_keys`, or the private key: `sshd` silently
rejects keys when the surrounding files are group/world-accessible, and the
client refuses to use a private key with loose permissions.

## Technologies

- linux (OpenSSH client/server, file permissions)

## Severity

**medium** — for an interactive user it is an access nuisance, but for automation
(CI deploys, `git` over SSH, Ansible, backups) it breaks pipelines and scheduled
jobs. A permissions regression after a restore or a bad `chmod -R` can lock out
every key-based login at once.

## Common Causes

1. Wrong permissions/ownership on `~/.ssh` (must be 700) or
   `authorized_keys` (600) — `sshd` rejects keys if these are too open.
2. The public key isn't in the target user's `authorized_keys` (or the wrong
   user/host).
3. The client isn't offering the right key (no matching `IdentityFile`, agent not
   loaded, or too many keys offered and the server hits `MaxAuthTries`).
4. `sshd_config` disallows it: `PubkeyAuthentication no`, restrictive
   `AllowUsers`/`AllowGroups`, or `PermitRootLogin prohibit-password` for root.
5. SELinux/AppArmor context wrong on `authorized_keys` after a manual copy.

## Root Cause Analysis

On each connection `sshd` checks the target user's `~/.ssh/authorized_keys`, but
first it enforces *strict modes*: if `~`, `~/.ssh`, or `authorized_keys` is
writable by group/other (or owned by the wrong user), it refuses the key and logs
`bad ownership or modes` — without telling the client *why*, which is why the
client only sees the generic "Permission denied (publickey)". On the client side,
`ssh` likewise refuses to load a private key whose file is group/world-readable
("UNPROTECTED PRIVATE KEY FILE"). So the same terse message can originate on
either end; the server's `sshd` logs and the client's `ssh -v` trace disambiguate
which key was tried and why it was rejected.

## Diagnostic Commands

```bash
# CLIENT: verbose handshake — which keys are offered and the server's responses
ssh -vvv user@host 2>&1 | grep -iE 'offering|authentications|publickey|denied'

# CLIENT: permissions on key files (private must NOT be group/world readable)
ls -ld ~/.ssh ; ls -l ~/.ssh/id_* ~/.ssh/config

# CLIENT: keys currently loaded in the agent
ssh-add -l

# SERVER: the real rejection reason in the sshd journal
sudo journalctl -u ssh -u sshd --no-pager | grep -iE 'authentication refused|bad ownership|invalid|accepted|denied' | tail -20

# SERVER: target user's ssh dir permissions and the effective sshd config
sudo ls -ld /home/deploy/.ssh ; sudo ls -l /home/deploy/.ssh/authorized_keys
sudo sshd -T 2>/dev/null | grep -iE 'pubkeyauthentication|authorizedkeysfile|allowusers|permitrootlogin'
```

## Expected Results

```text
# SERVER journal — the smoking gun
sshd[2210]: Authentication refused: bad ownership or modes for directory /home/deploy/.ssh

# Healthy permissions look like:
drwx------ 2 deploy deploy 4096 .ssh
-rw------- 1 deploy deploy  563 .ssh/authorized_keys
```

If `~/.ssh` is `drwxrwxr-x` or `authorized_keys` is `-rw-rw-r--`, that loose mode
is the cause. On the client, `ssh -vvv` showing `Offering public key ...` then
`Authentications that can continue: publickey` (and looping) means the offered
key wasn't in `authorized_keys`.

## Resolution

1. Fix permissions/ownership on the **server** for the target user (most common
   fix):

   ```bash
   sudo chown -R deploy:deploy /home/deploy/.ssh
   sudo chmod 700 /home/deploy/.ssh
   sudo chmod 600 /home/deploy/.ssh/authorized_keys
   ```
2. Ensure the correct public key is present:
   `cat ~/.ssh/id_ed25519.pub` (client) appears in the server's
   `authorized_keys`. Use `ssh-copy-id user@host` to add it safely.
3. On the client, fix private-key perms (`chmod 600 ~/.ssh/id_ed25519`) and load
   it: `ssh-add ~/.ssh/id_ed25519`, or point at it with `-i`/`IdentityFile`.
4. If `sshd_config` blocks it, enable `PubkeyAuthentication yes` and adjust
   `AllowUsers`/`PermitRootLogin`, then `sudo systemctl reload ssh`. **Risk:**
   keep an open session while editing `sshd_config` so a mistake doesn't lock you
   out.
5. If SELinux is enforcing, restore context:
   `sudo restorecon -Rv /home/deploy/.ssh`.

## Validation

```bash
ssh -o BatchMode=yes user@host 'echo SSH_OK'   # expect: SSH_OK, no password prompt
# Server side, confirm a clean accept:
sudo journalctl -u ssh | grep -i 'Accepted publickey' | tail -1
```

## Prevention

- Never `chmod -R 777` a home directory; manage `.ssh` perms explicitly.
- Provision keys via configuration management with correct ownership/modes.
- Edit `sshd_config` only with a second open session and `sshd -t` validation.
- Use `ssh-copy-id` rather than hand-editing `authorized_keys`.
- Run `restorecon` after restoring/copying `.ssh` on SELinux systems.

## Related Errors

- [systemd Failed to start unit](./linux-systemd-failed-to-start-unit.md)
- [Linux Read-only file system](./linux-read-only-file-system.md)

## References

- [OpenSSH sshd authorized_keys / strict modes](https://man.openbsd.org/sshd)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`linux` · `ssh` · `authentication` · `permissions` · `production`
