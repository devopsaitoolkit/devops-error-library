---
title: "LINSTOR Controller Database Locked"
slug: linstor-controller-database-locked
technologies: [linstor]
severity: critical
tags: [linstor, controller, database, startup, production]
related: [linstor-satellite-offline, linstor-not-enough-available-nodes]
last_reviewed: 2026-06-27
---

# LINSTOR Controller Database Locked

## Error Message

```text
$ linstor node list
Error: Unable to connect to linstor://localhost:3370
Connection refused
```

```text
journalctl -u linstor-controller:
ERROR  Initialization of the controller failed.
       org.h2.jdbc.JdbcSQLException: Database may be already in use:
       "Locked by another process". Possible solutions: close all other
       connection(s); use the server mode [90020-200]
       Database file: /var/lib/linstor/linstordb.mv.db
```

## Description

The LINSTOR controller persists all cluster state — nodes, resource definitions,
storage pools, properties — in a single embedded database (H2 by default, or an
external DB / etcd / k8s backend). **"Database may be already in use / Locked by
another process"** means the controller cannot acquire the exclusive lock on its
database file at startup, so it aborts. With no controller, the entire API is down:
`linstor` commands fail to connect on port 3370 and no orchestration is possible.

## Technologies

- linstor (controller persistence layer, H2 / external DB, port 3370)

## Severity

**critical** — the controller will not start, so the whole LINSTOR control plane is
offline. Existing DRBD replication keeps running, but you cannot create, resize,
fail over, or repair any resource until the controller is back.

## Common Causes

1. A second `linstor-controller` process is already running and holding the lock
   (e.g., a stale process plus a fresh `systemctl start`).
2. The previous controller crashed/was killed without releasing the lock, leaving a
   stale `.lock` / open handle on the H2 file.
3. Two controllers configured to point at the **same** database file (active/active
   misconfiguration instead of proper HA).
4. The database file is on shared/NFS storage mounted by more than one host.
5. Filesystem permissions or a read-only mount preventing lock acquisition.

## Root Cause Analysis

H2 in embedded mode takes an exclusive file lock so exactly one JVM owns the
database — this prevents two controllers from corrupting shared state. If a prior
process did not exit cleanly, or a duplicate process exists, the new controller's
lock request is refused and it fails initialization. The safe sequence is: ensure
**only one** controller process targets the database, clear any stale lock left by a
crash, then start a single controller. Running two controllers against one DB is a
configuration error, not something to "force" past.

## Diagnostic Commands

```bash
# Is more than one controller process alive?
ps -ef | grep -i linstor-controller | grep -v grep

# Controller service state and the failure reason
systemctl status linstor-controller
journalctl -u linstor-controller -n 80 --no-pager

# Who holds the database file open?
sudo lsof /var/lib/linstor/linstordb.mv.db

# Is the API port actually listening?
ss -lntp | grep 3370
```

## Expected Results

```text
# Faulty: two PIDs, or a stale lock file present
$ ps -ef | grep linstor-controller
root  1411 ... LinstorController
root  2530 ... LinstorController        # <-- duplicate

journalctl: "Database may be already in use: Locked by another process"
```

## Resolution

1. Stop the controller service so you start from a clean slate:

   ```bash
   sudo systemctl stop linstor-controller
   ```
2. Confirm **no** `LinstorController` JVM is still running; kill any orphan:

   ```bash
   ps -ef | grep -i linstor-controller | grep -v grep
   ```
3. If a process crashed and left a stale lock, remove the lock file only after
   confirming no live process owns the DB (back it up first):

   ```bash
   sudo cp /var/lib/linstor/linstordb.mv.db /var/lib/linstor/linstordb.mv.db.bak
   sudo rm -f /var/lib/linstor/linstordb.*.lock.db   # only if no process holds it
   ```
4. Ensure exactly **one** controller is configured against this database (use proper
   HA with a leader election, not two controllers on the same file). Start one:

   ```bash
   sudo systemctl start linstor-controller
   ```

## Validation

```bash
systemctl status linstor-controller        # active (running)
linstor node list                           # API answers on 3370
ss -lntp | grep 3370                         # controller listening
```

## Prevention

- Run a single controller per database; for HA use LINSTOR's supported
  high-availability setup with leader election, never two on one file.
- Keep the database on local disk, not shared NFS that multiple hosts can mount.
- Use systemd so a crashed controller restarts cleanly and releases the lock.
- Back up `linstordb.mv.db` regularly.

## Related Errors

- [LINSTOR Satellite Offline](./linstor-satellite-offline.md)
- [LINSTOR Not Enough Available Nodes](./linstor-not-enough-available-nodes.md)

## References

- [LINBIT: LINSTOR Controller Database](https://linbit.com/drbd-user-guide/linstor-guide-1_0-en/)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`linstor` · `controller` · `database` · `startup` · `production`
