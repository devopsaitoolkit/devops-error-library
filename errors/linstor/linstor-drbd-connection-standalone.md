---
title: "LINSTOR DRBD Connection StandAlone"
slug: linstor-drbd-connection-standalone
technologies: [linstor]
severity: high
tags: [linstor, drbd, replication, standalone, production]
related: [linstor-drbd-split-brain-detected, linstor-satellite-offline]
last_reviewed: 2026-06-27
---

# LINSTOR DRBD Connection StandAlone

## Error Message

```text
$ drbdadm status mydata
mydata role:Primary
  disk:UpToDate
  node-02 connection:StandAlone
  node-03 connection:Connecting
```

```text
kernel: drbd mydata node-02: conn( NetworkFailure -> StandAlone )
kernel: drbd mydata node-02: Discarding network configuration.
```

## Description

DRBD (the replication layer LINSTOR drives) maintains a connection between each
pair of nodes that hold a replica. **`connection:StandAlone`** means DRBD has
*intentionally torn down* the replication link to a peer and will **not** attempt
to reconnect on its own. Unlike `Connecting` (actively retrying) or
`NetworkFailure` (transient), `StandAlone` is a latched state — the node keeps
serving I/O locally but no longer replicates to that peer. Writes accepted while
StandAlone are not protected by the missing replica.

## Technologies

- linstor (DRBD replication transport, data ports 7000-7999)

## Severity

**high** — replication to the affected peer has stopped. The data is now under-
replicated; a failure of the surviving Primary risks data loss, and the cluster is
one step away from split-brain if the peer was independently promoted.

## Common Causes

1. DRBD detected a configuration mismatch or protocol error and dropped the link to
   protect data integrity.
2. A **split-brain** was detected and DRBD set the connection StandAlone rather than
   silently choosing a winner (see related error).
3. The peer's DRBD data port (7000-7999) is blocked or the peer was offline long
   enough for DRBD to give up.
4. Mismatched DRBD versions or shared-secret/auth mismatch between peers.
5. A manual `drbdadm disconnect` that was never reconnected.

## Root Cause Analysis

DRBD transitions to `StandAlone` whenever continuing to replicate would be unsafe
or impossible: an unresolved split-brain, an authentication/protocol mismatch, or
an explicit disconnect. Crucially, it stays there — it will not auto-reconnect —
because reconnecting blindly could overwrite good data with stale data. The peer
side typically shows `Connecting` (waiting) or also `StandAlone`. Resolution means
fixing the underlying cause (network/auth/split-brain) and then explicitly telling
DRBD to reconnect, choosing which side's data survives if they diverged.

## Diagnostic Commands

```bash
# Per-peer connection state for every resource
drbdadm status

# Detailed connection + disk state, including split-brain flags
drbdadm cstate mydata
drbdadm dstate mydata

# Kernel ring buffer — the reason DRBD went StandAlone
journalctl -k | grep -i drbd | tail -n 40

# LINSTOR's view of the same resource
linstor resource list
linstor volume list mydata
```

## Expected Results

```text
# Faulty
node-02 connection:StandAlone
# kernel: "Split-Brain detected but unresolved, dropping connection!"
#   or:   "incompatible after-sb-0pri settings"

# Healthy (after fix)
node-02 connection:Connected
  peer-disk:UpToDate
```

## Resolution

1. Read the kernel log to learn *why* it went StandAlone. If it is split-brain,
   follow the split-brain procedure (see related error) before reconnecting.
2. Verify the DRBD data ports are open and the peer satellite is online.
3. On a simple link drop with no data divergence, reconnect via LINSTOR or
   `drbdadm`:

   ```bash
   # Preferred: let LINSTOR re-establish the connection
   linstor resource connect node-01 node-02 mydata

   # Or directly on the node
   drbdadm connect mydata
   ```
4. If data diverged, decide the surviving side first; do **not** reconnect blindly.

## Validation

```bash
drbdadm status mydata
# Expect: every peer shows connection:Connected and peer-disk:UpToDate.
linstor resource list
# Expect: no nodes in a Bad/StandAlone condition.
```

## Prevention

- Open and keep stable the DRBD data ports (7000-7999) between all replica peers.
- Keep DRBD module/utils versions identical across the cluster.
- Alert on any `drbdadm status` connection that is not `Connected`.
- Configure sensible `after-sb-*` auto-recovery policies for non-critical volumes.

## Related Errors

- [LINSTOR DRBD Split-Brain Detected](./linstor-drbd-split-brain-detected.md)
- [LINSTOR Satellite Offline](./linstor-satellite-offline.md)

## References

- [LINBIT: DRBD Connection States](https://linbit.com/drbd-user-guide/drbd-guide-9_0-en/)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`linstor` · `drbd` · `replication` · `standalone` · `production`
