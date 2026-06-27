---
title: "Linux NIC Link is Down"
slug: linux-nic-link-is-down
technologies: [linux]
severity: high
tags: [linux, networking, nic, link, production]
related: [linux-systemd-failed-to-start-unit, linux-ssh-permission-denied-publickey]
last_reviewed: 2026-06-27
---

# Linux NIC Link is Down

## Error Message

```text
kernel: e1000e 0000:00:1f.6 eth0: NIC Link is Down
```

```text
kernel: igb 0000:03:00.0 eno1: Link is Down
NetworkManager: <warn>  [...] device (eth0): carrier: link disconnected
```

## Description

`NIC Link is Down` (also "Link is Down" / "carrier: link disconnected") is a
kernel/driver message reporting that the network interface has **lost physical
layer (L1) carrier** — the NIC no longer sees a link partner on the wire. This is
distinct from an IP/routing misconfiguration: at this level the cable, switch
port, or transceiver is the issue, and the interface's `LOWER_UP` flag is
cleared. No traffic can flow on that interface until carrier returns. When it
flaps (Down/Up repeatedly) you'll see paired messages and intermittent
connectivity.

## Technologies

- linux (network device drivers, link layer)

## Severity

**high** — the host loses connectivity on that interface. If it's the primary or
only NIC, the machine goes off the network entirely (you may lose SSH and depend
on console/OOB). For bonded/redundant setups a single link-down is degraded
rather than down, but a flapping link can be worse than a clean failure.

## Common Causes

1. Physical layer: unplugged/faulty cable, bad switch port, dead SFP/transceiver,
   or a powered-off switch.
2. The interface is administratively down (`ip link set ... down`) or never
   brought up by the network config.
3. Speed/duplex auto-negotiation mismatch with the switch (link won't establish
   or flaps).
4. Driver/firmware bug or a NIC power-management quirk (EEE/ASPM) dropping link.
5. Hardware failure of the NIC itself, or a recent kernel/driver upgrade
   regression.

## Root Cause Analysis

The NIC's PHY continuously negotiates a link with its partner (switch port). When
carrier is lost, the driver clears `IFF_RUNNING`/`LOWER_UP` and emits "Link is
Down"; the kernel then marks routes through that interface unusable and
NetworkManager/networkd report `carrier: down`. The driver also records
negotiated speed/duplex — a half/full-duplex or speed mismatch with the switch
prevents a stable link and shows up as flapping with rising error/CRC counters.
Because this is L1, no amount of IP reconfiguration helps until the driver
reports `Link is Up`; the fix is on the wire, the switch, or the driver, not in
the routing table.

## Diagnostic Commands

```bash
# Operational state and flags (look for state DOWN / NO-CARRIER)
ip -br link show
ip link show eth0

# Driver link events: up/down, negotiated speed/duplex, flapping
dmesg -T | grep -iE 'link is down|link is up|nic link|carrier'

# Carrier, negotiated speed/duplex, and whether link is detected
sudo ethtool eth0 | grep -iE 'speed|duplex|link detected|auto-negotiation'

# Interface error/drop/CRC counters (rising = bad cable/duplex mismatch)
ip -s link show eth0
cat /sys/class/net/eth0/carrier   # 1 = link up, 0 = link down
```

## Expected Results

```text
$ ip -br link show
eth0  DOWN  00:1b:21:aa:bb:cc <NO-CARRIER,BROADCAST,MULTICAST,UP>

$ ethtool eth0
        Speed: Unknown!
        Duplex: Unknown! (255)
        Link detected: no

$ cat /sys/class/net/eth0/carrier
0
```

`NO-CARRIER` with `Link detected: no` and `carrier 0` confirms L1 link loss. If
`ethtool` shows e.g. `Speed: 100Mb/s, Duplex: Half` on a gigabit link, suspect an
auto-negotiation/duplex mismatch; rising `errors`/`dropped` in `ip -s link`
points at a marginal cable.

## Resolution

1. Check and reseat/replace the **physical** path first: cable, switch port, and
   transceiver. Move to a known-good port to isolate.
2. If the interface is administratively down, bring it up:

   ```bash
   sudo ip link set eth0 up
   ```
   and ensure the persistent config (netplan / NetworkManager / systemd-networkd)
   actually enables it on boot.
3. For a duplex/speed mismatch, set both ends consistently; prefer
   auto-negotiation, but if the switch is fixed, match it:

   ```bash
   sudo ethtool -s eth0 autoneg off speed 1000 duplex full   # match the switch
   ```
   (persist via your network config). **Risk:** a mismatch here causes a hard
   link failure — change one variable at a time.
4. If a driver power feature flaps the link, disable EEE/ASPM for that NIC, or
   roll back a regressing kernel/driver.
5. If the NIC is dead, fail over to a redundant interface/bond and replace the
   hardware.

## Validation

```bash
ip -br link show eth0                 # expect state UP, no NO-CARRIER
ethtool eth0 | grep 'Link detected'   # expect: Link detected: yes
ping -c3 <gateway>                    # connectivity restored
dmesg -T | grep -i 'link is up' | tail -1
```

## Prevention

- Use bonded/redundant NICs (LACP) so one link-down is non-disruptive.
- Monitor `carrier`, interface error/CRC counters, and link flaps; alert on them.
- Standardize on auto-negotiation across hosts and switch ports.
- Keep OOB/console access so a primary-NIC failure isn't a lockout.
- Test NIC driver/firmware updates in staging before fleet rollout.

## Related Errors

- [systemd Failed to start unit](./linux-systemd-failed-to-start-unit.md)
- [SSH Permission denied (publickey)](./linux-ssh-permission-denied-publickey.md)

## References

- [ethtool man page](https://man7.org/linux/man-pages/man8/ethtool.8.html)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`linux` · `networking` · `nic` · `link` · `production`
