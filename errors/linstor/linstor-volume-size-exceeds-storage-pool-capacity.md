---
title: "LINSTOR Volume Size Exceeds Storage Pool Capacity"
slug: linstor-volume-size-exceeds-storage-pool-capacity
technologies: [linstor]
severity: medium
tags: [linstor, capacity, storage-pool, provisioning, production]
related: [linstor-storage-pool-not-found, linstor-not-enough-available-nodes]
last_reviewed: 2026-06-27
---

# LINSTOR Volume Size Exceeds Storage Pool Capacity

## Error Message

```text
$ linstor resource-definition create bigdata
$ linstor volume-definition create bigdata 500GiB
$ linstor resource create node-01 bigdata --storage-pool lvm-thick
ERROR:
Description:
    Not enough free space available for volume of size 500 GiB.
Details:
    Storage pool 'lvm-thick' on node 'node-01' has 180 GiB free,
    requested 500 GiB (incl. DRBD metadata).
```

## Description

When LINSTOR creates a resource it must allocate the requested volume size — plus a
small amount of **DRBD metadata** — from the chosen storage pool on each target
node. If the requested size exceeds the pool's free capacity on a node, the
controller rejects the create. For thick provisioning (`LVM`, thick ZFS) the full
size is reserved immediately; for thin pools (`LVM_THIN`) the *logical* size can be
overcommitted, but you can still hit the limit when the backing thin pool actually
fills.

## Technologies

- linstor (capacity accounting over LVM / LVM-thin / ZFS)

## Severity

**medium** — the new volume is not created and no existing data is harmed. If it
happens during a resize of a live volume, the resize fails but the current data
stays intact and accessible at its old size.

## Common Causes

1. Requested volume size simply larger than the free space in the pool on a target
   node (thick provisioning reserves it all up front).
2. The backing VG/zpool is smaller than assumed, or already consumed by other
   resources and snapshots.
3. A thin pool that has been overcommitted and is now physically full.
4. Forgetting the DRBD metadata overhead, so a size that "just fits" actually does
   not.
5. Asking for replicas on a node whose pool is the smallest in the cluster.

## Root Cause Analysis

The controller checks `requested_size + drbd_metadata` against each target node's
storage-pool free capacity before allocating. For thick drivers the reservation is
immediate, so the check is hard. For thin drivers LINSTOR permits logical
overcommit, but the physical thin pool can still exhaust — and a full thin pool
turns volumes read-only, which is more dangerous than an upfront rejection. The fix
is to free or add physical capacity, choose a pool that has room, or reduce the
requested size.

## Diagnostic Commands

```bash
# Free vs. total capacity for every pool, per node
linstor storage-pool list

# What is already consuming the pool (resources/volumes on each node)
linstor resource list-volumes
linstor volume list

# Backing storage reality check on the node
vgs ; lvs -a                  # LVM / LVM-thin: VG free + thin pool data%
zpool list ; zfs list         # ZFS pools

# Snapshots can pin space too
linstor snapshot list
```

## Expected Results

```text
# Faulty: free capacity below request
╭───────────────────────────────────────────────────────────────╮
┊ StoragePool ┊ Node    ┊ Driver ┊ TotalCapacity ┊ FreeCapacity ┊
╞═══════════════════════════════════════════════════════════════╡
┊ lvm-thick   ┊ node-01 ┊ LVM    ┊        200 GiB ┊       180 GiB ┊
╰───────────────────────────────────────────────────────────────╯
# Requested 500 GiB > 180 GiB free → create rejected.

# For thin pools, watch Data% in `lvs` approaching 100%.
```

## Resolution

1. Choose a pool/node with enough free space, or lower the requested size to fit
   the available capacity.
2. Free space by deleting unused resources or stale snapshots:

   ```bash
   linstor snapshot delete bigdata old-snap   # if no longer needed
   ```
3. Add physical capacity to the backing storage, then let LINSTOR see it:

   ```bash
   # Extend the underlying VG (LVM example), then LINSTOR re-reads capacity
   sudo vgextend drbdpool /dev/sdd
   ```
4. For thin pools that are physically full, extend the thin pool's data LV before
   it forces volumes read-only.
5. Retry the resource/volume create or resize once capacity is sufficient.

## Validation

```bash
linstor storage-pool list
# Expect: FreeCapacity on the target node exceeds requested size + metadata.
linstor resource create node-01 bigdata --storage-pool lvm-thick
linstor resource list-volumes
```

## Prevention

- Monitor per-pool free capacity and alert on a low-watermark (e.g., <15%).
- For thin pools, alert on physical `Data%` well before 100% to avoid read-only
  lockups.
- Size storage pools consistently across nodes so the smallest pool does not gate
  placement.
- Account for DRBD metadata overhead when planning volume sizes.

## Related Errors

- [LINSTOR Storage Pool Not Found](./linstor-storage-pool-not-found.md)
- [LINSTOR Not Enough Available Nodes](./linstor-not-enough-available-nodes.md)

## References

- [LINBIT: Storage Pools and Capacity](https://linbit.com/drbd-user-guide/linstor-guide-1_0-en/)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`linstor` · `capacity` · `storage-pool` · `provisioning` · `production`
