"""Build and persist the search index over the ``errors/`` tree."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

from .model import ErrorDoc

DEFAULT_ROOT = "errors"
INDEX_FILE = "search-index.json"


def iter_error_files(root: str | Path = DEFAULT_ROOT) -> Iterator[Path]:
    """Yield every error Markdown file under ``root`` (excluding README indexes)."""
    root_path = Path(root)
    for path in sorted(root_path.rglob("*.md")):
        if path.name.upper() == "README.MD":
            continue
        yield path


def build_index(root: str | Path = DEFAULT_ROOT) -> list[ErrorDoc]:
    """Parse every error document under ``root`` into a list of :class:`ErrorDoc`."""
    root_path = Path(root)
    return [ErrorDoc.from_file(path, root=root_path) for path in iter_error_files(root_path)]


def write_index(docs: list[ErrorDoc], out: str | Path = INDEX_FILE) -> Path:
    """Write a compact JSON index (metadata only) for fast loading or web use."""
    payload = {
        "version": 1,
        "count": len(docs),
        "documents": [doc.to_dict() for doc in docs],
    }
    out_path = Path(out)
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return out_path


def stats(docs: list[ErrorDoc]) -> dict[str, int]:
    """Return per-technology document counts, plus a total."""
    counts: dict[str, int] = {}
    for doc in docs:
        for tech in doc.technologies or ["unknown"]:
            counts[tech] = counts.get(tech, 0) + 1
    counts["TOTAL"] = len(docs)
    return dict(sorted(counts.items(), key=lambda kv: (kv[0] == "TOTAL", -kv[1], kv[0])))
