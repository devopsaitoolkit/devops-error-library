"""Scaffold a new error document from the canonical template."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

_TEMPLATE = """---
title: "{title}"
slug: {slug}
technologies: [{technology}]
severity: {severity}
tags: [{tags}]
related: []
last_reviewed: {today}
---

# {title}

## Error Message

```text
TODO: paste the exact error string here.
```

## Description

TODO: explain what this error means and when it appears.

## Technologies

- {technology}

## Severity

**{severity}** — TODO: describe the operational impact.

## Common Causes

1. TODO

## Root Cause Analysis

TODO: explain the failure mechanism.

## Diagnostic Commands

```bash
# TODO: a real, READ-ONLY diagnostic command.
```

## Expected Results

```text
TODO: what the diagnostic output reveals.
```

## Resolution

1. TODO

## Validation

TODO: how to confirm the fix worked.

## Prevention

- TODO

## Related Errors

- TODO

## References

- [Advanced troubleshooting guides](https://devopsaitoolkit.com/blog)

## Tags

`{tag_inline}`
"""


def slugify(text: str) -> str:
    """Turn a title into a kebab-case slug."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "error"


def create_error(
    title: str,
    technology: str,
    *,
    severity: str = "medium",
    tags: list[str] | None = None,
    root: str | Path = "errors",
    subdir: str | None = None,
) -> Path:
    """Write a new error document and return its path.

    The file is placed under ``errors/<technology>/`` (or a nested ``subdir`` such
    as an OpenStack service) and named after the slug.
    """
    slug = slugify(title)
    tag_list = tags or [technology]
    base = Path(root) / technology
    if subdir:
        base = base / subdir
    base.mkdir(parents=True, exist_ok=True)
    target = base / f"{slug}.md"
    content = _TEMPLATE.format(
        title=title,
        slug=slug,
        technology=technology,
        severity=severity,
        tags=", ".join(tag_list),
        tag_inline=" · ".join(tag_list),
        today=date.today().isoformat(),
    )
    target.write_text(content, encoding="utf-8")
    return target
