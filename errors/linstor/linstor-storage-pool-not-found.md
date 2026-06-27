---
title: "LINSTOR Storage Pool Not Found"
slug: linstor-storage-pool-not-found
technologies: [linstor]
severity: medium
tags: [linstor, storage-pool, provisioning, lvm, production]
related: [linstor-not-enough-available-nodes, linstor-volume-size-exceeds-storage-pool-capacity]
last_reviewed: 2026-06-27
---

# LINSTOR Storage Pool Not Found

## Error Message

```text
$ linstor resource create node-02 mydata --storage-pool lvm-thin
ERROR:
Description:
    The storage pool 'lvm-thin' for resource 'mydata' is not deployed on
    node 'node-02'.
Details:
    Node: node-02, Resource: mydata
    Storage pool 'lvm-thin' is not known on this node.
```

## Description

A LINSTOR storage pool is a node-local mapping onto a backing volume group, thin
pool, or zpool (LVM, LVM-thin, ZFS, etc.). Storage pools are **per node** — a pool
named `lvm-thin` on `node-01` does not automatically exist on `node-02`. This error
means the controller was asked to place a resource using a storage pool that is not
defined on the target node (or is misspelled). Provisioning stops; nothing is
created on that node.

## Technologies

- linstor (storage pool layer over LVM / LVM-thin / ZFS)

## Severity

**medium** — no existing data is affected, but the resource cannot be created or
placed on the intended node until the storage pool is defined there.

## Common Causes

1. The storage pool was created on some nodes but never on the target node.
2. A typo or wrong case in the storage pool name (names are case-sensitive).
3. The backing VG/thin-pool/zpool does not exist on the node, so pool creation
   silently failed earlier.
4. A node was re-imaged/replaced and its storage pools were never recreated.
5. Auto-place defaulting to the `DfltStorPool` when the real pool was never set.

## Root Cause Analysis

LINSTOR stores storage-pool definitions in the controller database, scoped to a
specific node. Placement requires the named pool to exist on every target node.
When the lookup `(node, pool-name)` misses, the controller refuses the operation
rather than guessing an alternative pool — silently choosing a different pool could
land data on the wrong tier. So the message is precisely "this node has no pool by
that name." The fix is to create the pool on the node (which in turn requires the
backing storage to exist) or to point at a pool the node actually has.

## Diagnostic Commands

```bash
# Every storage pool, per node, with driver and capacity
linstor storage-pool list

# Pools defined specifically on the target node
linstor storage-pool list --nodes node-02

# Does the backing LVM/ZFS actually exist on the node?
vgs ; lvs                       # for LVM / LVM-thin pools
zpool list                      # for ZFS pools

# Confirm the node is online and known
linstor node list
```

## Expected Results

```text
# Faulty: target node has no row for the pool
$ linstor storage-pool list --nodes node-02
╭──────────────────────────────────────────────╮
┊ StoragePool ┊ Node ┊ Driver ┊ FreeCapacity ┊  ┊
╞══════════════════════════════════════════════╡
┊ (no entries)                                  ┊
╰──────────────────────────────────────────────╯

# Healthy: the pool exists on the node
┊ lvm-thin ┊ node-02 ┊ LVM_THIN ┊ 200 GiB ┊ Ok ┊
```

## Resolution

1. Confirm the backing storage exists on the node (the VG/thin-pool/zpool). Create
   it if missing — LINSTOR can do this for LVM-thin:

   ```bash
   # Create an LVM-thin storage pool on the node (assumes VG 'drbdpool' exists)
   linstor storage-pool create lvm-thin node-02 lvm-thin drbdpool/thinpool
   ```
2. If the name was simply mistyped, retry with the exact pool name from
   `linstor storage-pool list`.
3. Re-run the resource create / auto-place once the pool is present.

## Validation

```bash
linstor storage-pool list --nodes node-02
# Expect: a row for the pool with State Ok and non-zero FreeCapacity.
linstor resource create node-02 mydata --storage-pool lvm-thin
linstor resource list
```

## Prevention

- Provision storage pools as part of node bootstrap (Ansible/Terraform), not by
  hand, so every node has a consistent set.
- Standardize pool names across the fleet; avoid per-node naming drift.
- After replacing a node, recreate its storage pools before adding it to placement.

## Related Errors

- [LINSTOR Not Enough Available Nodes](./linstor-not-enough-available-nodes.md)
- [LINSTOR Volume Size Exceeds Storage Pool Capacity](./linstor-volume-size-exceeds-storage-pool-capacity.md)

## References

- [LINBIT: Storage Pools](https://linbit.com/drbd-user-guide/linstor-guide-1_0-en/)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`linstor` · `storage-pool` · `provisioning` · `lvm` · `production`
