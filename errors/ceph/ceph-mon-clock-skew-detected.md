---
title: "Ceph Monitor Clock Skew Detected"
slug: ceph-mon-clock-skew-detected
technologies: [ceph]
severity: medium
tags: [ceph, mon, ntp, clock-skew, production]
related: [ceph-monitors-down-no-quorum, ceph-osd-down-and-out]
last_reviewed: 2026-06-27
---

# Ceph Monitor Clock Skew Detected

## Error Message

```text
cluster:
  id:     5b2a9c1e-7f3d-4a8b-9e6c-1d4f8a2b3c5e
  health: HEALTH_WARN
          clock skew detected on mon.ceph-node02, mon.ceph-node03
```

```text
$ ceph health detail
HEALTH_WARN clock skew detected on mon.ceph-node02
[WRN] MON_CLOCK_SKEW: clock skew detected on mon.ceph-node02
    mon.ceph-node02 clock skew 0.512s > max 0.05s (latency 0.001s)
```

## Description

Ceph monitors run a Paxos-based consensus and require their clocks to be closely
aligned. `MON_CLOCK_SKEW` fires when a monitor's clock differs from the leader's
by more than `mon_clock_drift_allowed` (default `0.05s`, 50ms). The health detail
reports the measured skew, the allowed maximum, and the round-trip latency (so you
can tell genuine drift from a noisy/slow link). While a small skew only raises a
warning, larger skews can disrupt monitor elections and lease handling, and Ceph
will refuse to let a badly-skewed monitor participate.

## Technologies

- ceph (mon, Paxos, NTP/chrony)

## Severity

**medium** — usually just a warning with no immediate data impact, but it is a
leading indicator of monitor instability. Severe skew can cause monitors to drop
out of quorum, escalate election churn, and ultimately threaten the control plane,
so it should be fixed promptly rather than ignored.

## Common Causes

1. NTP/chrony not running, misconfigured, or unable to reach its time sources on
   one or more monitor hosts.
2. Monitor hosts pointed at different/unsynchronized upstream NTP servers.
3. A VM monitor whose clock jumped after live-migration, pause/resume, or host
   suspend.
4. A flaky/high-latency network link inflating the apparent skew (check the
   reported `latency` value).
5. Hardware RTC battery failure or BIOS time wrong on a freshly-booted node.

## Root Cause Analysis

The leading monitor timestamps Paxos messages; followers compare the timestamps
in periodic time-check rounds against their own clocks, accounting for measured
round-trip latency. If a follower's clock differs by more than
`mon_clock_drift_allowed`, the monitor records the skew and surfaces the health
check. The latency figure matters: a large skew with near-zero latency is a real
clock difference (fix NTP); a large skew that tracks a high latency value can be a
measurement artifact of a slow link. Because the consensus protocol relies on
leases bounded in time, persistent skew undermines the assumption that all monitors
share a common timeline, which is why Ceph treats it as a health issue rather than
a tuning knob to widen.

## Diagnostic Commands

```bash
# Which monitors are skewed and by how much (note the latency column)
ceph status
ceph health detail

# Confirm quorum membership and the leader the skew is measured against
ceph quorum_status --format json-pretty | grep -E 'quorum|leader'

# On EACH monitor host: is time sync running and locked?
timedatectl status
chronyc tracking          # or: ntpq -p   (depending on the time daemon)

# Compare wall clocks across mon hosts quickly
journalctl -u chrony --no-pager -n 50
```

## Expected Results

```text
$ chronyc tracking
Reference ID    : 0A000001 (ntp.internal)
Stratum         : 3
System time     : 0.000012 seconds slow of NTP time
Leap status     : Normal

# Healthy: 'System time' offset is sub-millisecond and stratum is sane.
# Problem node: chrony not running, large offset, or 'Leap status: Not
# synchronised' — that node is the source of the skew.
```

## Resolution

1. On the skewed monitor host, ensure the time daemon is installed, enabled, and
   synchronized:

   ```bash
   systemctl enable --now chronyd
   chronyc makestep          # one-time large correction if far off
   chronyc tracking          # confirm sub-ms offset
   ```
2. Point all monitor hosts at the *same* reliable NTP source(s); inconsistent
   upstreams cause relative skew.
3. For VM monitors, disable guest clock features that pause/jump time and ensure
   the hypervisor passes a stable clocksource.
4. Fix BIOS/RTC time and replace a dead CMOS battery on bare-metal nodes.
5. If the skew is actually a slow/lossy link (high reported latency), fix the
   network rather than the clock.

## Validation

```bash
ceph health detail
# Expect: no MON_CLOCK_SKEW check; HEALTH_OK.

# On each mon host:
chronyc tracking
# Expect: 'Leap status: Normal' and a sub-millisecond System time offset.
```

## Prevention

- Run chrony/NTP on every monitor (and OSD) host, locked to common, redundant
  sources; monitor sync state, not just liveness.
- Alert on `MON_CLOCK_SKEW` early — it predicts quorum trouble.
- For virtualized mons, standardize hypervisor time settings and avoid suspend.
- Keep `mon_clock_drift_allowed` at its default; widening it hides the problem.

## Related Errors

- [Ceph Monitors Down — No Quorum](./ceph-monitors-down-no-quorum.md)
- [Ceph OSD Down and Out](./ceph-osd-down-and-out.md)

## References

- [Ceph: Monitor troubleshooting — clock skew](https://docs.ceph.com/en/latest/rados/troubleshooting/troubleshooting-mon/)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`ceph` · `mon` · `ntp` · `clock-skew` · `production`
