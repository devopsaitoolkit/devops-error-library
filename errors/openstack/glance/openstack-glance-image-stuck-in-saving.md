---
title: "OpenStack Glance Image Stuck in Saving Status"
slug: openstack-glance-image-stuck-in-saving
technologies: [openstack, glance]
severity: medium
tags: [openstack, glance, image, saving, backend, production]
related: [openstack-glance-image-download-failed]
last_reviewed: 2026-06-27
---

# OpenStack Glance Image Stuck in Saving Status

## Error Message

```text
$ openstack image list
+--------------------------------------+-------------+--------+
| ID                                   | Name        | Status |
+--------------------------------------+-------------+--------+
| 7f0a3c1e-9b2d-4a11-8c3e-2f1a9d0b7e44 | ubuntu-2204 | saving |
+--------------------------------------+-------------+--------+
```

```text
glance-api[1842]: ERROR glance.api.v2.image_data [req-...] Failed to upload image data due to internal error: \
glance_store._drivers.rbd.StoreError: error connecting to the cluster
```

## Description

A Glance image stays in the `saving` state indefinitely instead of advancing to
`active`. `saving` means the image metadata record was created and the client is
streaming (or has finished streaming) the bits to the configured backing store,
but Glance never received confirmation that the data was fully written. The
glance-api worker that handles the `PUT /v2/images/{id}/file` request is
responsible for transitioning the status to `active`; if that worker dies, the
upload stalls, or the store driver errors, the record is orphaned in `saving`.

## Technologies

- openstack (glance-api, glance_store driver, backing store: Ceph RBD / file / Swift)

## Severity

**medium** — the affected image is unusable and consumes a metadata slot, but
existing `active` images and running instances are unaffected. Escalates to high
if uploads fail wholesale and no new images can be created.

## Common Causes

1. The client upload was interrupted (network drop, CLI timeout, `Ctrl-C`)
   before all bytes reached glance-api.
2. The backing store is unreachable or degraded — Ceph cluster in `HEALTH_ERR`,
   full OSDs, NFS/file mount gone read-only, or Swift returning 5xx.
3. The glance-api worker process was killed or restarted mid-upload.
4. Insufficient free space on the store, so the final write/commit fails.
5. A `glance_store` driver misconfiguration (wrong `rbd_store_pool`, bad Ceph
   keyring/auth) that surfaces only when data is written.

## Root Cause Analysis

Glance creates the image row in `queued`, flips it to `saving` when the data
upload begins, streams bytes through the `glance_store` driver, and only sets
`active` after the driver returns the image size and checksum. If the connection
to the store breaks or the worker dies before that return value is processed, the
state machine never advances. Because Glance does not run a janitor that reaps
stale `saving` records by default, the image is stuck until an operator clears it.

## Diagnostic Commands

```bash
# Confirm the stuck status and how long it has been saving
openstack image show <image-id> -c status -c updated_at -f value

# glance-api errors around the upload time
journalctl -u devstack@g-api --since "30 min ago" | grep -iE "error|store|saving"

# Backend health (Ceph example)
ceph -s
ceph df

# Is the image object actually present in the RBD pool?
rbd -p images ls | grep <image-id>

# File store: check the directory and free space
df -h /var/lib/glance/images
```

## Expected Results

```text
status      saving
updated_at  2026-06-27T10:14:02Z   # stale; no progress for many minutes

# Ceph unhealthy is the smoking gun:
  cluster:
    health: HEALTH_ERR
            1 full osd(s)

# Healthy comparison: image flips to active and an RBD object exists:
rbd -p images ls
7f0a3c1e-9b2d-4a11-8c3e-2f1a9d0b7e44
```

## Resolution

1. Fix the backing store first — restore Ceph health (`ceph osd df`, reweight or
   add OSDs), remount a read-only file store, or recover Swift before retrying.
2. Delete the orphaned `saving` record so the slot and name are freed:
   ```bash
   openstack image set --state queued <image-id>   # if reset is permitted
   openstack image delete <image-id>
   ```
   On older releases lacking `--state`, use `glance-manage` / DB cleanup with
   care, or the admin `PATCH` with the `modify_image` policy.
3. Re-upload from a stable host, preferring `--progress` and a reliable link:
   ```bash
   openstack image create --disk-format qcow2 --container-format bare \
     --file ubuntu-2204.qcow2 --progress ubuntu-2204
   ```
4. If the worker was OOM-killed, raise the glance-api memory limit or reduce
   concurrent uploads.

## Validation

```bash
openstack image show ubuntu-2204 -c status -c size -f value
# Expect: active  and a non-zero size
```

## Prevention

- Monitor backing-store health (Ceph `HEALTH_OK`, OSD fullness, NFS mount state)
  and alert before stores fill.
- Upload large images from a stable host or a staging node co-located with the API.
- Add an operational job/alert that flags images in `saving` older than N minutes.
- Set sensible `glance_store` timeouts and worker `graceful_timeout`.

## Related Errors

- [OpenStack Glance Image Download Failed](./openstack-glance-image-download-failed.md)

## References

- [Glance image statuses](https://docs.openstack.org/glance/latest/user/statuses.html)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`openstack` · `glance` · `image` · `saving` · `backend` · `production`
