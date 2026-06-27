---
title: "OpenStack Cinder Volume in Error State"
slug: openstack-cinder-volume-in-error-state
technologies: [openstack, cinder]
severity: high
tags: [openstack, cinder, volume, error-state, backend, production]
related: [openstack-cinder-no-weighed-backends-available, openstack-cinder-volume-attachment-failed]
last_reviewed: 2026-06-27
---

# OpenStack Cinder Volume in Error State

## Error Message

```text
cinder-volume[3271]: ERROR cinder.volume.manager [req-7d2a...] Unable to create volume \
2f9c4e1b-...: Failed to create volume on backend lvm-1: \
ProcessExecutionError: Unexpected error while running command: lvcreate ... \
  Volume group "cinder-volumes" has insufficient free space (0 extents): 256 required.
```

```text
$ openstack volume show 2f9c4e1b-...
| status | error                                  |
| error  | Failed to create volume on backend ... |
```

## Description

A Cinder volume lands in the `error` (or `error_deleting`, `error_extending`)
state when `cinder-volume` could not complete the requested operation on the
storage backend. The volume row stays in the database but is unusable. The cause
is almost always backend-side: the driver returned an error from the array, LVM,
Ceph, or transport layer. The scheduler already chose a backend — this failure
happens when that backend actually tries to provision.

## Technologies

- openstack (cinder-volume, cinder-scheduler, storage driver/backend)

## Severity

**high** — the affected volume is unusable, and if the backend itself is full or
unreachable, every new volume request to it will fail the same way.

## Common Causes

1. Backend capacity exhausted — LVM volume group full, Ceph pool near full, or
   array thin-pool out of space.
2. Backend/driver unreachable — `cinder-volume` cannot talk to the array
   (network, credentials, or the driver service is down).
3. Image-to-volume conversion failed (corrupt image, qemu-img error, no temp
   space) when creating a bootable volume.
4. Snapshot or clone source is itself in `error`, or a parent was deleted.
5. Quota/feature mismatch the driver rejects (unsupported size, type extra-specs).

## Root Cause Analysis

`cinder-scheduler` picks a backend, then `cinder-volume` on that host calls the
driver's `create_volume()`. The driver shells out (LVM `lvcreate`, Ceph RBD,
vendor API). Any non-zero result raises an exception that the manager catches,
sets the volume `status = error`, and writes the reason into the volume's
`error`/message field. The DB row persists so an operator can inspect it. Because
the failure is at provisioning time, the backend log + the volume message
together reveal whether it is capacity, connectivity, or a bad source.

## Diagnostic Commands

```bash
# Status and the recorded error reason
openstack volume show <volume-id> -c status -c name

# Recent user-visible messages explaining the failure
openstack volume message list --resource-uuid <volume-id>

# Which backend/host owns it and is the service up?
openstack volume service list

# cinder-volume backend log around the failure
journalctl -u devstack@c-vol --since "15 min ago" | grep -i <volume-id>

# Backend free capacity (example: LVM)
sudo vgs cinder-volumes
```

## Expected Results

```text
# volume message list
| User Message                                              |
| create volume: Failed with: insufficient free space ...  |

# vgs
VG             #PV #LV #SN Attr   VSize    VFree
cinder-volumes   1   8   0 wz--n- 100.00g    0     <- backend is full
```

`VFree 0`, an unreachable array, or a referenced source volume in `error` each
pinpoint the cause.

## Resolution

1. **Capacity:** free or expand backend storage (extend the VG / add OSDs /
   grow the thin-pool). Verify `cinder-scheduler` capacity reporting afterward.
2. **Connectivity:** restore the array/network and restart the affected
   `cinder-volume` backend; confirm it appears `up` in `volume service list`.
3. **Bad source/image:** use a known-good image/snapshot; ensure temp space for
   `qemu-img` conversion (`image_conversion_dir`).
4. The errored volume cannot be recovered in place — delete and recreate:
   ```bash
   openstack volume delete <volume-id>
   ```
   If it is stuck `error_deleting`, an admin may need `cinder-manage volume delete`.

## Validation

```bash
openstack volume create --size 1 cinder-health-test
openstack volume show cinder-health-test -c status -f value   # Expect: available
openstack volume delete cinder-health-test
```

## Prevention

- Alert on backend free capacity well before it fills.
- Monitor `cinder-volume` service `up`/`down` per backend.
- Health-check array/network connectivity and credentials.
- Validate images used for bootable volumes; keep `image_conversion_dir` sized.

## Related Errors

- [OpenStack Cinder No Weighed Backends Available](./openstack-cinder-no-weighed-backends-available.md)
- [OpenStack Cinder Volume Attachment Failed](./openstack-cinder-volume-attachment-failed.md)

## References

- [Cinder troubleshooting](https://docs.openstack.org/cinder/latest/admin/troubleshooting.html)
- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`openstack` · `cinder` · `volume` · `error-state` · `backend` · `production`
