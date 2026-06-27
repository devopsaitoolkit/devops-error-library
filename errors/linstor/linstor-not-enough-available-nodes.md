---
title: "LINSTOR Not Enough Available Nodes"
slug: linstor-not-enough-available-nodes
technologies: [linstor]
severity: medium
tags: [linstor, autoplace, scheduling, replication, production]
related: [linstor-storage-pool-not-found, linstor-volume-size-exceeds-storage-pool-capacity]
last_reviewed: 2026-06-27
---

# LINSTOR Not Enough Available Nodes

## Error Message

```text
$ linstor resource-definition auto-place 3 mydata
ERROR:
Description:
    Not enough available nodes
Details:
    Not enough nodes fulfilling the autoplace constraints to place 3 replicas
    of resource 'mydata'. Found 1 eligible node, requested 3.
    Storage pool 'lvm-thin' satisfied on: node-01
```

## Description

LINSTOR's auto-placement engine selects nodes for a resource's replicas based on
constraints: the requested replica count, the named storage pool, free capacity,
and any placement rules (replicas-on-same / replicas-on-different, do-not-place-with).
**Not enough available nodes** means the controller could not find enough nodes
that satisfy *all* of those constraints simultaneously. It is a scheduling
rejection, not a hardware failure — the resource is simply not created.

## Technologies

- linstor (controller auto-placement / scheduler)

## Severity

**medium** — no data is lost and existing resources are untouched, but the new
resource (or an attempted scale-up of replica count) cannot be provisioned until
the constraints can be met.

## Common Causes

1. Fewer nodes own the requested storage pool than the requested replica count
   (e.g., asking for 3 replicas when only 2 nodes have `lvm-thin`).
2. One or more candidate nodes are `OFFLINE`, so they are excluded.
3. Insufficient free space in the storage pool on otherwise eligible nodes.
4. Placement constraints (`--replicas-on-different`, `--do-not-place-with-regex`)
   narrow the candidate set below the requested count.
5. The storage pool name is misspelled or does not exist on the expected nodes.

## Root Cause Analysis

The scheduler builds a candidate list, then filters it: drop offline nodes, drop
nodes lacking the storage pool, drop nodes without enough free capacity, then apply
placement rules. If the surviving set is smaller than the requested replica count,
it returns this error rather than placing fewer replicas than asked. So the message
is really "your constraints are stricter than your fleet can satisfy." The fix is
either to relax constraints, free/add capacity, or bring more pool-owning nodes
online.

## Diagnostic Commands

```bash
# How many nodes are online and eligible
linstor node list

# Which nodes actually own the target storage pool, and free capacity
linstor storage-pool list

# Existing placement of the resource (if partially placed)
linstor resource list-volumes

# Any constraints/properties on the resource definition
linstor resource-definition list-properties mydata
```

## Expected Results

```text
# storage-pool list reveals the real candidate count
╭──────────────────────────────────────────────────────────────╮
┊ StoragePool ┊ Node    ┊ Driver   ┊ FreeCapacity ┊ State ┊
╞══════════════════════════════════════════════════════════════╡
┊ lvm-thin    ┊ node-01 ┊ LVM_THIN ┊       180 GiB ┊ Ok    ┊
╰──────────────────────────────────────────────────────────────╯
# Only ONE node owns lvm-thin → cannot place 3 replicas.
```

## Resolution

1. Confirm how many online nodes own the storage pool (`linstor storage-pool list`).
   If fewer than the replica count, create the pool on more nodes:

   ```bash
   linstor storage-pool create lvm node-02 lvm-thin drbdpool
   ```
2. Bring any `OFFLINE` candidate nodes back online.
3. If the limit is free space, extend the backing VG/zpool or delete unused
   resources, then retry the auto-place.
4. If placement constraints are too strict for the fleet, relax them or set a
   lower replica count that the cluster can satisfy.

## Validation

```bash
linstor resource-definition auto-place 3 mydata
linstor resource list
# Expect: the resource appears on the requested number of nodes, all InUse/UpToDate.
```

## Prevention

- Keep at least `replica_count` nodes owning each storage pool tier.
- Alert when a storage pool's eligible-node count drops below your standard
  replica count.
- Track free capacity per pool and reserve headroom before it forces rejections.

## Related Errors

- [LINSTOR Storage Pool Not Found](./linstor-storage-pool-not-found.md)
- [LINSTOR Volume Size Exceeds Storage Pool Capacity](./linstor-volume-size-exceeds-storage-pool-capacity.md)

## References

- [LINBIT: Placement and Auto-place](https://linbit.com/drbd-user-guide/linstor-guide-1_0-en/)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`linstor` · `autoplace` · `scheduling` · `replication` · `production`
