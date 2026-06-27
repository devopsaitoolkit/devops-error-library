---
title: "Ceph Monitors Down — No Quorum"
slug: ceph-monitors-down-no-quorum
technologies: [ceph]
severity: critical
tags: [ceph, mon, quorum, availability, production]
related: [ceph-mon-clock-skew-detected, ceph-osd-down-and-out]
last_reviewed: 2026-06-27
---

# Ceph Monitors Down — No Quorum

## Error Message

```text
$ ceph status
2026-06-27T09:14:02.118+0000 7f3a mon.ceph-node01@0(probing) e7 handle_auth_request ...
[errno 110] RADOS timed out (error connecting to the cluster)
```

```text
$ ceph health detail
HEALTH_WARN 1/3 mons down, quorum ceph-node01,ceph-node02
[WRN] MON_DOWN: 1/3 mons down, quorum ceph-node01,ceph-node02
    mon.ceph-node03 (rank 2) addr [v2:10.0.0.13:3300/0] is down (out of quorum)
```

```text
# When a MAJORITY is lost, the whole control plane stalls and commands hang:
$ ceph -s
2026-06-27T09:20:11.642+0000 monclient(hunting): authenticate timed out after 300
```

## Description

Ceph monitors maintain the cluster maps via a Paxos quorum and require a strict
**majority** to operate (2 of 3, 3 of 5). `MON_DOWN` warns when some — but not a
majority — of monitors are down: the cluster still functions on the surviving
quorum. But if you lose the majority (e.g. 2 of 3 mons), there is **no quorum**:
the monitors cannot agree on map updates, `ceph` commands hang or time out
(`monclient(hunting)`, RADOS timeouts), and the cluster's control plane is frozen.
Existing client I/O may continue briefly on cached maps, but no recovery,
peering, or administrative change can proceed.

## Technologies

- ceph (mon, Paxos, RocksDB mon store)

## Severity

**critical** when quorum is lost — the entire cluster control plane is down: no
map updates, no recovery, administrative commands time out, and clients will
eventually fail as they cannot refresh maps. `MON_DOWN` with quorum still held is
high (reduced fault tolerance) but not yet an outage. Losing the mon majority is
one of the most serious states a Ceph cluster can be in.

## Common Causes

1. Multiple monitor hosts down at once — power/rack failure, simultaneous reboots,
   or a bad rolling change taking out the majority.
2. The mon store (RocksDB under `/var/lib/ceph/mon/`) is full, corrupt, or out of
   disk on the mon host.
3. Network partition isolating monitors from each other so no majority can form.
4. Severe clock skew preventing elections (see related clock-skew error).
5. A misconfigured `monmap` after adding/removing mons left an even count or wrong
   addresses.

## Root Cause Analysis

Monitors elect a leader and commit map changes through Paxos, which by design
requires a majority to guarantee consistency and prevent split-brain. With three
monitors, one can fail and the remaining two still form a majority (`MON_DOWN`,
warning). Lose a second and only one remains — a single mon is a minority and
*refuses* to act alone, because doing so could diverge from the other copies and
corrupt cluster state. So it sits in `probing`/`electing`, hunting for peers it
cannot reach, and every client/admin request that needs a fresh map blocks until
it times out. This fail-stop behavior is intentional: Ceph chooses unavailability
over inconsistency. Recovery means restoring enough monitors (or, in a disaster,
rebuilding the monmap) to re-establish a majority.

## Diagnostic Commands

```bash
# These may hang if quorum is lost — that itself is the diagnosis
ceph status
ceph health detail

# Ask a specific live mon directly via its admin socket (works without quorum)
ceph daemon mon.ceph-node01 mon_status

# Quorum membership and ranks as the surviving mons see it
ceph daemon mon.ceph-node01 quorum_status

# On each mon host: is the daemon running, and why did it stop?
systemctl status ceph-mon@ceph-node03
journalctl -u ceph-mon@ceph-node03 --no-pager -n 200

# Check the mon store disk isn't full
df -h /var/lib/ceph/mon/
```

## Expected Results

```text
$ ceph daemon mon.ceph-node01 mon_status
{
    "name": "ceph-node01",
    "rank": 0,
    "state": "probing",
    "quorum": [],
    "outside_quorum": [ "ceph-node01" ],
    "monmap": { "mons": [ "ceph-node01", "ceph-node02", "ceph-node03" ] }
}

# state "probing"/"electing" with an empty "quorum" array = no quorum.
# A healthy mon shows state "leader" or "peon" and a populated quorum list.
# A full /var/lib/ceph/mon disk in df output is a common, fixable cause.
```

## Resolution

1. Determine which mons are down and *why* from `systemctl`/`journalctl` on each
   host. The fastest fix is almost always restoring the down daemons.
2. If a mon stopped because its store disk is full, free space on
   `/var/lib/ceph/mon/` and restart it:

   ```bash
   systemctl restart ceph-mon@ceph-node03
   ceph daemon mon.ceph-node01 mon_status   # confirm quorum reforms
   ```
3. If a host is dead, recover the host or the mon will rejoin on boot; bringing
   back any one mon to reach a majority restores the control plane.
4. Fix any network partition between mon hosts — without connectivity a majority
   cannot form even if all daemons run.
5. **Last resort / disaster only:** if the mon store on a survivor is intact but
   peers are permanently lost, you can rebuild the monmap to a single survivor and
   re-add mons. This is high-risk and should follow the official disaster-recovery
   procedure exactly.

## Validation

```bash
ceph status
# Expect: command returns instantly (no hunting/timeout), "mon: N daemons,
# quorum <all-mons>", and HEALTH_OK once OSDs re-peer.

ceph daemon mon.ceph-node01 mon_status
# Expect: state "leader"/"peon" with all mons listed in "quorum".
```

## Prevention

- Run an **odd** number of monitors (3 or 5) across distinct failure domains so a
  single rack/host loss never breaks the majority.
- Monitor mon store disk usage and free space; a full mon store is a silent
  cluster-killer.
- Keep NTP healthy to prevent skew-blocked elections.
- During maintenance, never reboot/upgrade more than `(N-1)/2` monitors at once;
  drain and verify quorum between steps.

## Related Errors

- [Ceph Monitor Clock Skew Detected](./ceph-mon-clock-skew-detected.md)
- [Ceph OSD Down and Out](./ceph-osd-down-and-out.md)

## References

- [Ceph: Troubleshooting Monitors](https://docs.ceph.com/en/latest/rados/troubleshooting/troubleshooting-mon/)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`ceph` · `mon` · `quorum` · `availability` · `production`
