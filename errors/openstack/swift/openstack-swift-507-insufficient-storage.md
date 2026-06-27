---
title: "OpenStack Swift 507 Insufficient Storage"
slug: openstack-swift-507-insufficient-storage
technologies: [openstack, swift]
severity: high
tags: [openstack, swift, object-storage, 507, disk, production]
related: [openstack-glance-image-stuck-in-saving]
last_reviewed: 2026-06-27
---

# OpenStack Swift 507 Insufficient Storage

## Error Message

```text
HTTP/1.1 507 Insufficient Storage
< X-Trans-Id: tx0a1b2c3d...
```

```text
object-server: ERROR __call__ error with PUT /d3/12345/AUTH_acct/cont/obj : \
DiskFileNoSpace: No space left on device
proxy-server: ERROR 507 Insufficient Storage From Object Server \
re: PUT 10.0.0.21:6200/d3/12345/...
```

## Description

A Swift object server returned `507 Insufficient Storage`, which the proxy surfaces
to the client when it cannot place the required number of replicas. The object
server refuses a write when the target drive's free space falls below the
configured `fallocate_reserve`, or when the drive is unmounted/failed. If too many
of the replica drives for a partition are unavailable, the proxy cannot satisfy
write quorum and the whole PUT fails with 507.

## Technologies

- openstack (swift proxy-server, object-server, account/container servers, the ring)

## Severity

**high** — uploads (and potentially container/account writes) fail. Reads of
existing objects may still work, so it is typically a write outage on the
affected partitions or a cluster-wide ingest stop when many drives are full.

## Common Causes

1. One or more storage drives are full past `fallocate_reserve` so the object
   server rejects writes.
2. A drive failed or was unmounted; Swift treats the mount point as unavailable
   and skips it, reducing available replicas.
3. The ring is unbalanced — data concentrated on a few devices while others sit
   nearly empty (bad weights or a partial rebalance).
4. Cluster capacity is genuinely exhausted; total ingest outran provisioning.
5. Inodes exhausted on a filesystem even though raw bytes remain.

## Root Cause Analysis

For a PUT, the proxy hashes the path to a partition and writes replicas to the
devices the ring assigns. Each object server checks free space against
`fallocate_reserve` before accepting the data; if the drive is below the reserve
(or not mounted), it returns 507. The proxy needs a write quorum of successful
replica writes; if enough replica drives return 507/unavailable, the proxy returns
507 to the client. So the root cause is per-drive fullness/availability multiplied
by how the ring distributes that partition's replicas.

## Diagnostic Commands

```bash
# Per-drive usage across the cluster — find the full/failed devices
swift-recon -d                      # disk usage report
swift-recon --unmounted             # drives Swift considers unmounted

# Raw OS view on a storage node
df -h /srv/node/*                   # bytes
df -i /srv/node/*                   # inodes

# Object-server 507s in the logs
journalctl -u swift-object --since "20 min ago" | grep -iE "507|No space|DiskFileNoSpace"

# Inspect ring balance and device weights
swift-ring-builder /etc/swift/object.builder

# Client-side reproduction with the transaction id
curl -i -X PUT -H "X-Auth-Token: $TOKEN" \
  https://<proxy>/v1/AUTH_acct/cont/probe -d "test"
```

## Expected Results

```text
$ df -h /srv/node/d3
Filesystem  Size  Used Avail Use% Mounted on
/dev/sdd1   1.8T  1.8T   18G  99% /srv/node/d3     # below fallocate_reserve

$ swift-recon --unmounted
Checking unmounted drives
-> 10.0.0.21:6200: d7 is unmounted

# Healthy: all devices well under 90-95% and none unmounted; PUT returns 201.
```

## Resolution

1. Free or add capacity on the full drives — expire/delete stale data, or add new
   devices and rebalance the ring:
   ```bash
   swift-ring-builder /etc/swift/object.builder add r1z1-10.0.0.30:6200/d1 1000
   swift-ring-builder /etc/swift/object.builder rebalance
   # distribute the new *.ring.gz to all nodes, then let replication settle
   ```
2. Remount or replace failed drives so Swift counts them again:
   ```bash
   mount /srv/node/d7 && systemctl restart swift-object
   ```
3. If a single device is hot, fix weights and rebalance to spread the partitions
   evenly.
4. If inodes are exhausted, reclaim small files or reformat with more inodes; raw
   space alone will not clear the 507.

## Validation

```bash
curl -i -X PUT -H "X-Auth-Token: $TOKEN" \
  https://<proxy>/v1/AUTH_acct/cont/probe -d "ok"   # Expect: 201 Created
swift-recon -d | tail                                # no drive at/over reserve
```

## Prevention

- Alert on per-drive usage at 80/90% via `swift-recon -d`, not just node totals.
- Monitor `swift-recon --unmounted` and replace failed drives promptly.
- Keep ring weights balanced and rebalance incrementally after capacity changes.
- Track inode usage as well as bytes for many-small-object workloads.

## Related Errors

- [OpenStack Glance Image Stuck in Saving Status](../glance/openstack-glance-image-stuck-in-saving.md)

## References

- [Swift cluster health & swift-recon](https://docs.openstack.org/swift/latest/admin_guide.html)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`openstack` · `swift` · `object-storage` · `507` · `disk` · `production`
