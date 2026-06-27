#!/usr/bin/env python3
"""Generate per-category README indexes and the top-level errors/README.md.

Run from the repo root: ``python scripts/gen_indexes.py``. The generated indexes
are navigation aids only — they are excluded from validation and the search
index. Re-run after adding errors (CI can do this).
"""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from errlib.index import build_index
from errlib.model import ErrorDoc

ERRORS = Path("errors")
_SEV_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


def _category(doc: ErrorDoc) -> str:
    return doc.path.split("/", 1)[0]


def _row(doc: ErrorDoc, category: str) -> str:
    # doc.path is relative to errors/, e.g. "ceph/x.md" or "openstack/nova/x.md".
    # The category README lives at errors/<category>/README.md, so strip the prefix.
    rel = doc.path[len(category) + 1 :] if doc.path.startswith(category + "/") else doc.path
    link = f"[{doc.title}]({rel})"
    tags = ", ".join(f"`{t}`" for t in doc.tags[:5])
    return f"| {link} | {doc.severity} | {tags} |"


def write_category_index(category: str, docs: list[ErrorDoc]) -> None:
    """Write ``errors/<category>/README.md`` listing its errors."""
    base = ERRORS / category
    docs = sorted(docs, key=lambda d: (_SEV_ORDER.get(d.severity, 9), d.title.lower()))
    lines = [
        f"# {category.title()} Errors",
        "",
        f"{len(docs)} documented error(s). Search the whole library with "
        '`errlib search "<query>" --tech ' + category + "`.",
        "",
        "| Error | Severity | Tags |",
        "| --- | --- | --- |",
    ]
    lines.extend(_row(d, category) for d in docs)
    lines.append("")
    lines.append("More DevOps troubleshooting guides: https://devopsaitoolkit.com/blog")
    (base / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_root_index(by_cat: dict[str, list[ErrorDoc]], total: int) -> None:
    """Write ``errors/README.md`` summarizing every category."""
    lines = [
        "# Error Library Index",
        "",
        f"**{total} documented errors** across {len(by_cat)} categories.",
        "",
        "| Category | Errors |",
        "| --- | --- |",
    ]
    for cat in sorted(by_cat, key=lambda c: (-len(by_cat[c]), c)):
        lines.append(f"| [{cat}](./{cat}/) | {len(by_cat[cat])} |")
    lines.append("")
    (ERRORS / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    """Build all index README files."""
    docs = build_index(ERRORS)
    by_cat: dict[str, list[ErrorDoc]] = defaultdict(list)
    for doc in docs:
        by_cat[_category(doc)].append(doc)
    for category, cat_docs in by_cat.items():
        write_category_index(category, cat_docs)
    write_root_index(by_cat, len(docs))
    print(f"Generated indexes for {len(by_cat)} categories ({len(docs)} errors).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
