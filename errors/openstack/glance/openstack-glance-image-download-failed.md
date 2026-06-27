---
title: "OpenStack Glance Image Download Failed"
slug: openstack-glance-image-download-failed
technologies: [openstack, glance]
severity: medium
tags: [openstack, glance, image, download, store, production]
related: [openstack-glance-image-stuck-in-saving]
last_reviewed: 2026-06-27
---

# OpenStack Glance Image Download Failed

## Error Message

```text
$ openstack image save --file ubuntu-2204.qcow2 7f0a3c1e-9b2d-4a11-8c3e-2f1a9d0b7e44
HTTP 404 Not Found: Image 7f0a3c1e-9b2d-4a11-8c3e-2f1a9d0b7e44 not found.
The image data is not available.
```

```text
glance-api[1842]: ERROR glance.api.v2.image_data [req-...] Image data not found for image \
7f0a3c1e-9b2d-4a11-8c3e-2f1a9d0b7e44: glance_store.exceptions.NotFound: Image not found in store
```

## Description

A request to retrieve image bits — `openstack image save`, a Nova compute pulling
the base image, or a `GET /v2/images/{id}/file` — fails even though the image
appears in the catalog. The image *metadata* exists in the Glance database, but
the *data* cannot be served: either the object is missing from the backing store,
the store is unreachable, or the image is in a state (`queued`, `saving`,
`deleted`) that has no downloadable data.

## Technologies

- openstack (glance-api, glance_store driver, Nova compute as a consumer)

## Severity

**medium** — instances depending on this image cannot boot and the image cannot
be exported. Other images and running instances are unaffected.

## Common Causes

1. The store object was deleted out-of-band (manual `rbd rm`, file removed,
   Swift object purged) while the Glance metadata row survived.
2. The backing store is unreachable — Ceph auth/connectivity failure, NFS mount
   missing, Swift endpoint down.
3. The image never finished uploading — it is `queued` or stuck in `saving`, so
   there is genuinely no data to download.
4. A multi-store migration left `stores`/`locations` metadata pointing at a store
   that no longer holds the object.
5. Corrupt or truncated data fails the checksum verification during transfer.

## Root Cause Analysis

On a download, glance-api looks up the image's `locations` (or default store),
asks the `glance_store` driver to open the object, and streams it back. If the
driver cannot find or read the object, it raises `NotFound`/`StoreError`, which
the API surfaces as a 404 or 500. The key distinction is metadata-vs-data: the
catalog row tells you the image *should* exist, while the store tells you whether
the bytes are actually present and reachable. Mismatch between the two is the
root cause.

## Diagnostic Commands

```bash
# Status must be 'active' to have downloadable data; check size and locations
openstack image show <image-id> -c status -c size -c stores -f value

# Locations as the admin sees them (needs show_multiple_locations / admin)
openstack image show <image-id> -f json | python3 -m json.tool | grep -i location

# Does the object physically exist? (Ceph RBD example)
rbd -p images ls | grep <image-id>

# File store presence and size
ls -lh /var/lib/glance/images/<image-id>

# glance-api errors at download time
journalctl -u devstack@g-api --since "15 min ago" | grep -iE "not found|store|error"
```

## Expected Results

```text
status   active
size     2361393152
stores   ceph

# But the object is missing from the store -> data unavailable:
$ rbd -p images ls | grep <image-id>
(no output)

# Healthy comparison: the object exists and size matches the metadata.
```

## Resolution

1. If the image is `queued`/`saving`, there is no data — re-upload it (see the
   "stuck in saving" runbook) rather than chasing the store.
2. If the store is unreachable, restore connectivity/auth (Ceph keyring,
   `rbd_store_pool`, NFS mount, Swift endpoint) and retry the download.
3. If the object was deleted but metadata remains, the data is unrecoverable —
   delete the dangling record and re-import the image:
   ```bash
   openstack image delete <image-id>
   openstack image create --disk-format qcow2 --container-format bare \
     --file ubuntu-2204.qcow2 ubuntu-2204
   ```
4. If `locations` point at the wrong store after a migration, fix the location
   metadata or copy the image into the active store:
   ```bash
   openstack image import --method copy-image --stores ceph <image-id>
   ```

## Validation

```bash
openstack image save --file /tmp/test.img <image-id>
ls -lh /tmp/test.img   # size should match 'openstack image show -c size'
```

## Prevention

- Never delete store objects directly — always go through the Glance API so
  metadata and data stay consistent.
- Enable and monitor a periodic consistency check between Glance metadata and
  store contents.
- Use checksums (`os_hash_value`) to detect truncation/corruption early.
- Monitor store reachability and auth (Ceph health, NFS mounts, Swift endpoints).

## Related Errors

- [OpenStack Glance Image Stuck in Saving Status](./openstack-glance-image-stuck-in-saving.md)

## References

- [Glance image data API](https://docs.openstack.org/api-ref/image/v2/)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`openstack` · `glance` · `image` · `download` · `store` · `production`
