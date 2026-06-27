"""Parse YAML front matter from a Markdown document."""

from __future__ import annotations

from typing import Any

import yaml

_DELIM = "---"


def split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Split a document into ``(frontmatter_dict, body)``.

    Returns an empty dict if the document has no front matter. Never raises on a
    missing block; raises ``yaml.YAMLError`` only when a present block is invalid.
    """
    if not text.startswith(_DELIM):
        return {}, text
    lines = text.splitlines()
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == _DELIM:
            end = i
            break
    if end is None:
        return {}, text
    raw = "\n".join(lines[1:end])
    data = yaml.safe_load(raw) or {}
    body = "\n".join(lines[end + 1 :]).lstrip("\n")
    if not isinstance(data, dict):
        return {}, text
    return data, body
