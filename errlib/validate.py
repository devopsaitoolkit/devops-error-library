"""Validate error documents against the library's structural rules."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from . import REQUIRED_FRONTMATTER, REQUIRED_SECTIONS, SEVERITIES
from .frontmatter import split_frontmatter

_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_H2_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


@dataclass
class Issue:
    """A single validation problem in a document."""

    path: str
    message: str


def validate_file(path: str | Path) -> list[Issue]:
    """Return a list of validation issues for one error document (empty if valid)."""
    path = Path(path)
    issues: list[Issue] = []
    rel = str(path)
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:  # pragma: no cover - filesystem edge case
        return [Issue(rel, f"cannot read file: {exc}")]

    try:
        meta, body = split_frontmatter(content)
    except yaml.YAMLError as exc:
        return [Issue(rel, f"invalid YAML front matter: {exc}")]

    if not meta:
        return [Issue(rel, "missing YAML front matter block")]

    for key in REQUIRED_FRONTMATTER:
        if key not in meta or meta[key] in (None, "", []):
            issues.append(Issue(rel, f"front matter missing required key: {key!r}"))

    slug = meta.get("slug")
    if isinstance(slug, str):
        if not _SLUG_RE.match(slug):
            issues.append(Issue(rel, f"slug is not kebab-case: {slug!r}"))
        if slug != path.stem:
            issues.append(Issue(rel, f"slug {slug!r} does not match filename {path.stem!r}"))

    severity = meta.get("severity")
    if severity is not None and severity not in SEVERITIES:
        issues.append(Issue(rel, f"severity {severity!r} not in {SEVERITIES}"))

    for key in ("technologies", "tags", "related"):
        if key in meta and meta[key] is not None and not isinstance(meta[key], list):
            issues.append(Issue(rel, f"front matter {key!r} must be a list"))

    present = {m.group(1).strip().lower() for m in _H2_RE.finditer(body)}
    for section in REQUIRED_SECTIONS:
        if section.lower() not in present:
            issues.append(Issue(rel, f"missing required section: '## {section}'"))

    if not body.lstrip().startswith("# "):
        issues.append(Issue(rel, "body must start with an H1 title ('# ...')"))

    return issues


def validate_tree(root: str | Path = "errors") -> list[Issue]:
    """Validate every error document under ``root``."""
    from .index import iter_error_files

    issues: list[Issue] = []
    for path in iter_error_files(root):
        issues.extend(validate_file(path))
    return issues
