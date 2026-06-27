"""The in-memory representation of one error document."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .frontmatter import split_frontmatter

_SECTION_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


@dataclass
class ErrorDoc:
    """A single parsed error document and its searchable fields."""

    path: str
    slug: str
    title: str
    technologies: list[str] = field(default_factory=list)
    severity: str = "medium"
    tags: list[str] = field(default_factory=list)
    related: list[str] = field(default_factory=list)
    message: str = ""
    text: str = ""

    @classmethod
    def from_file(cls, path: str | Path, root: str | Path | None = None) -> ErrorDoc:
        """Load and parse an error document from disk."""
        path = Path(path)
        content = path.read_text(encoding="utf-8")
        meta, body = split_frontmatter(content)
        sections = _split_sections(body)
        rel = str(path.relative_to(root)) if root else str(path)
        return cls(
            path=rel,
            slug=str(meta.get("slug") or path.stem),
            title=str(meta.get("title") or path.stem),
            technologies=[str(t) for t in meta.get("technologies", [])],
            severity=str(meta.get("severity", "medium")),
            tags=[str(t).lower() for t in meta.get("tags", [])],
            related=[str(r) for r in meta.get("related", [])],
            message=sections.get("error message", "").strip(),
            text=body.lower(),
        )

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable mapping (without the full body text)."""
        data = asdict(self)
        data.pop("text", None)
        return data


def _split_sections(body: str) -> dict[str, str]:
    """Return a mapping of lowercased H2 heading -> section text."""
    sections: dict[str, str] = {}
    matches = list(_SECTION_RE.finditer(body))
    for i, match in enumerate(matches):
        name = match.group(1).strip().lower()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        sections[name] = body[start:end].strip()
    return sections
