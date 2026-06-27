---
title: "LINSTOR DRBD Split-Brain Detected"
slug: linstor-drbd-split-brain-detected
technologies: [linstor]
severity: critical
tags: [linstor, drbd, split-brain, data-integrity, production]
related: [linstor-drbd-connection-standalone, linstor-resource-secondary-secondary-no-primary]
last_reviewed: 2026-06-27
---

# LINSTOR DRBD Split-Brain Detected

## Error Message

```text
kernel: drbd mydata node-02: Split-Brain detected but unresolved, dropping connection!
kernel: drbd mydata node-02: helper command: /sbin/drbdadm split-brain
kernel: drbd mydata node-02: conn( Connecting -> StandAlone )
```

```text
$ drbdadm status mydata
mydata role:Primary disk:UpToDate
  node-02 connection:StandAlone
```

## Description

A DRBD **split-brain** occurs when two nodes both modified a replica independently
while disconnected — each became Primary (or accepted writes) without the other,
so their data has *diverged*. When the link returns, DRBD detects two competing
sets of changes it cannot reconcile automatically, refuses to merge them, and drops
the connection to `StandAlone` to avoid silently destroying one side's writes.
Resolving it requires a human decision about which node's data is authoritative —
the other side's divergent writes will be discarded.

## Technologies

- linstor (DRBD replication, split-brain recovery)

## Severity

**critical** — the replicas have genuinely divergent data and replication is
stopped. Recovery is destructive: whichever side you designate as the "victim"
loses its divergent writes. Data loss is possible if the wrong side is chosen.

## Common Causes

1. A network partition during which both nodes served writes (each became Primary).
2. Failover that promoted a survivor while the original Primary was still writing,
   then both rejoined.
3. Manual promotion of a node that was not actually isolated.
4. Fencing/quorum disabled, so DRBD had no mechanism to prevent dual-Primary.
5. Power loss to one node mid-write followed by promotion of the other.

## Root Cause Analysis

DRBD tracks a data-generation UUID lineage. After a disconnect where *both* sides
advanced their own generation, the UUIDs no longer share a clean ancestor — DRBD
sees two divergent histories. Its `after-sb-*` policies decide whether to auto-pick
a winner; for safety these often resolve to "disconnect and require a human." The
operator picks the authoritative node; the other is told to discard its changes and
re-sync from the survivor. The root prevention is fencing/quorum so two writers can
never exist simultaneously in the first place.

## Diagnostic Commands

```bash
# Connection states — split-brained peers show StandAlone
drbdadm status mydata
drbdadm cstate mydata

# Kernel log: the split-brain detection line and helper invocation
journalctl -k | grep -i split-brain

# Disk/role of each node to help decide which copy is authoritative
drbdsetup status mydata --verbose

# LINSTOR view of the resource health
linstor resource list
linstor volume list mydata
```

## Expected Results

```text
# Faulty
kernel: "Split-Brain detected but unresolved, dropping connection!"
node-02 connection:StandAlone

# Decide authority: which node has the writes you must keep?
# The OTHER node becomes the split-brain victim and is re-synced.

# Healthy (after recovery)
node-02 connection:Connected peer-disk:UpToDate
```

## Resolution

> Recovery discards the victim node's divergent data. Confirm which node holds the
> writes you must keep before proceeding.

1. Pick the authoritative (survivor) node — the one whose data you keep.
2. On the **victim** node, discard its data and reconnect so it re-syncs from the
   survivor:

   ```bash
   # On the VICTIM node only:
   drbdadm disconnect mydata
   drbdadm secondary mydata
   drbdadm connect --discard-my-data mydata
   ```
3. On the **survivor** node, reconnect to accept the victim:

   ```bash
   drbdadm connect mydata
   ```
4. Watch the resync complete; both sides should reach `UpToDate`. Prefer driving
   reconnects through LINSTOR (`linstor resource connect`) where possible.

## Validation

```bash
drbdadm status mydata
# Expect: connection:Connected and peer-disk:UpToDate on every peer,
# exactly one Primary, no StandAlone.
journalctl -k | grep -i drbd | tail
```

## Prevention

- Enable DRBD **quorum** and resource **fencing** so two nodes can never both write.
- Use a cluster manager (DRBD Reactor / Pacemaker) for controlled, single-Primary
  failover.
- Configure deliberate `after-sb-0pri` / `after-sb-1pri` / `after-sb-2pri` policies
  for each resource's criticality.
- Alert immediately on any `split-brain` kernel message.

## Related Errors

- [LINSTOR DRBD Connection StandAlone](./linstor-drbd-connection-standalone.md)
- [LINSTOR Resource Secondary/Secondary No Primary](./linstor-resource-secondary-secondary-no-primary.md)

## References

- [LINBIT: Manual Split-Brain Recovery](https://linbit.com/drbd-user-guide/drbd-guide-9_0-en/)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`linstor` · `drbd` · `split-brain` · `data-integrity` · `production`
