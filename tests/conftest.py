"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

_SAMPLE = """---
title: "Sample Tech Boom Error"
slug: sample-tech-boom-error
technologies: [sample]
severity: high
tags: [sample, boom, production]
related: []
last_reviewed: 2026-06-27
---

# Sample Tech Boom Error

## Error Message

```text
boom: the thing exploded
```

## Description

It exploded.

## Technologies

- sample

## Severity

**high** — explosion.

## Common Causes

1. Too much pressure.

## Root Cause Analysis

Pressure built up.

## Diagnostic Commands

```bash
sample status
```

## Expected Results

```text
status: exploded
```

## Resolution

1. Release pressure.

## Validation

Run `sample status` again.

## Prevention

- Add a relief valve.

## Related Errors

- None

## References

- [docs](https://example.com)

## Tags

`sample` · `boom`
"""


@pytest.fixture
def sample_tree(tmp_path: Path) -> Path:
    """Create a tiny errors/ tree with one valid document."""
    root = tmp_path / "errors"
    (root / "sample").mkdir(parents=True)
    (root / "sample" / "sample-tech-boom-error.md").write_text(_SAMPLE, encoding="utf-8")
    return root


@pytest.fixture
def repo_errors() -> Path:
    """Path to the real errors/ tree in the repository."""
    return REPO_ROOT / "errors"
