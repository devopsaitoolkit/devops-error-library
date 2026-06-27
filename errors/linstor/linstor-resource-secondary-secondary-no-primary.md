---
title: "LINSTOR Resource Secondary/Secondary No Primary"
slug: linstor-resource-secondary-secondary-no-primary
technologies: [linstor]
severity: high
tags: [linstor, drbd, promotion, primary, production]
related: [linstor-drbd-connection-standalone, linstor-drbd-split-brain-detected]
last_reviewed: 2026-06-27
---

# LINSTOR Resource Secondary/Secondary No Primary

## Error Message

```text
$ drbdadm status mydata
mydata role:Secondary
  disk:UpToDate
  node-02 role:Secondary peer-disk:UpToDate
  node-03 role:Secondary peer-disk:UpToDate
```

```text
$ mount /dev/drbd1000 /mnt/data
mount: /mnt/data: mount(2) system call failed: Wrong medium type.
# DRBD device is read-only/blocked because no node holds the Primary role.
```

## Description

A DRBD resource must have exactly one node in the **Primary** role to allow
read-write access to its device (`/dev/drbdXXXX`). When *every* node reports
`role:Secondary`, the device is effectively read-only/blocked everywhere — you
cannot mount it read-write, and any application or filesystem on top of it cannot
open it. The data is intact and fully replicated; what is missing is an active
Primary to serve I/O.

## Technologies

- linstor (DRBD promotion / role management)

## Severity

**high** — the volume is unusable for writes on every node. Any service backed by
this resource is down until a node is promoted to Primary.

## Common Causes

1. A failover where the old Primary went away but nothing promoted a survivor
   (e.g., manual setups without a cluster manager like Pacemaker/DRBD Reactor).
2. The application/orchestrator that normally promotes (auto-promote disabled,
   no consumer holding the device open) never ran.
3. A previous split-brain or StandAlone state left DRBD unwilling to auto-promote.
4. Promotion was attempted but blocked because a peer was not `UpToDate` and quorum
   rules prevented becoming Primary.
5. The resource was manually demoted (`drbdadm secondary`) and never re-promoted.

## Root Cause Analysis

DRBD only allows one Primary to guarantee a single writer. Promotion happens either
explicitly (`drbdadm primary`), automatically via `auto-promote` when a consumer
opens the device, or via a cluster resource manager. If none of those fire — for
example after the original Primary node died and no manager exists to promote a
survivor — the resource sits in Secondary/Secondary. With DRBD quorum enabled, a
node will also *refuse* to become Primary unless it can confirm it holds the most
recent data, which protects against promoting a stale copy.

## Diagnostic Commands

```bash
# Confirm every node is Secondary and check disk freshness
drbdadm status mydata

# Quorum and connection detail that may be blocking promotion
drbdadm cstate mydata
drbdsetup status mydata --verbose

# LINSTOR's view: which node it thinks is in-use / primary
linstor resource list
linstor resource list-volumes

# Did a previous primary die? Check node connectivity
linstor node list
```

## Expected Results

```text
# Faulty: all Secondary, but data is current → safe to promote
mydata role:Secondary disk:UpToDate
  node-02 role:Secondary peer-disk:UpToDate

# A node that is NOT UpToDate (Outdated/Inconsistent) should NOT be promoted:
  disk:Outdated      # promoting this risks serving stale data
```

## Resolution

1. Verify the candidate node is `disk:UpToDate` (not Outdated/Inconsistent) before
   promoting.
2. Promote the up-to-date node to Primary — prefer doing it through LINSTOR:

   ```bash
   # LINSTOR way (toggles the role for the resource on a node)
   linstor resource toggle-disk node-01 mydata --primary 2>/dev/null || \
   drbdadm primary mydata        # direct DRBD fallback on the chosen node
   ```
3. If a node refuses promotion due to quorum, restore the connection to enough
   peers so quorum is met, then retry.
4. Mount/use the device, and configure auto-promote or a cluster manager so this
   does not require manual intervention next time.

## Validation

```bash
drbdadm status mydata
# Expect: exactly ONE node shows role:Primary, peers role:Secondary, all UpToDate.
mount /dev/drbd1000 /mnt/data && echo "writable"
```

## Prevention

- Use a cluster resource manager (DRBD Reactor / Pacemaker) or rely on DRBD
  `auto-promote` so a Primary is always elected.
- Enable DRBD quorum to prevent promoting stale replicas.
- Alert when a resource has zero Primary across all nodes.

## Related Errors

- [LINSTOR DRBD Connection StandAlone](./linstor-drbd-connection-standalone.md)
- [LINSTOR DRBD Split-Brain Detected](./linstor-drbd-split-brain-detected.md)

## References

- [LINBIT: DRBD Roles and Promotion](https://linbit.com/drbd-user-guide/drbd-guide-9_0-en/)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`linstor` · `drbd` · `promotion` · `primary` · `production`
