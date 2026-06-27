"""Tests for the errlib toolkit and the integrity of the real error tree."""

from __future__ import annotations

from pathlib import Path

import pytest

from errlib import REQUIRED_SECTIONS
from errlib.frontmatter import split_frontmatter
from errlib.index import build_index, stats, write_index
from errlib.model import ErrorDoc
from errlib.new_error import create_error, slugify
from errlib.search import search
from errlib.validate import validate_file, validate_tree

# --------------------------------------------------------------------------- #
# frontmatter / model                                                         #
# --------------------------------------------------------------------------- #


def test_split_frontmatter_roundtrip() -> None:
    meta, body = split_frontmatter("---\ntitle: X\ntags: [a, b]\n---\n\n# X\n\nbody")
    assert meta["title"] == "X"
    assert meta["tags"] == ["a", "b"]
    assert body.startswith("# X")


def test_split_frontmatter_absent() -> None:
    meta, body = split_frontmatter("# No front matter\n")
    assert meta == {}
    assert body.startswith("# No front matter")


def test_errordoc_from_file(sample_tree: Path) -> None:
    doc = ErrorDoc.from_file(sample_tree / "sample" / "sample-tech-boom-error.md", root=sample_tree)
    assert doc.slug == "sample-tech-boom-error"
    assert doc.technologies == ["sample"]
    assert doc.severity == "high"
    assert "boom" in doc.tags
    assert "the thing exploded" in doc.message
    assert doc.path == "sample/sample-tech-boom-error.md"


# --------------------------------------------------------------------------- #
# index                                                                       #
# --------------------------------------------------------------------------- #


def test_build_index_and_stats(sample_tree: Path) -> None:
    docs = build_index(sample_tree)
    assert len(docs) == 1
    s = stats(docs)
    assert s["TOTAL"] == 1
    assert s["sample"] == 1


def test_write_index(sample_tree: Path, tmp_path: Path) -> None:
    docs = build_index(sample_tree)
    out = write_index(docs, tmp_path / "idx.json")
    assert out.exists()
    import json

    data = json.loads(out.read_text())
    assert data["count"] == 1
    assert data["documents"][0]["slug"] == "sample-tech-boom-error"
    assert "text" not in data["documents"][0]  # body text excluded from the JSON index


# --------------------------------------------------------------------------- #
# search                                                                       #
# --------------------------------------------------------------------------- #


def test_search_by_query(sample_tree: Path) -> None:
    docs = build_index(sample_tree)
    results = search(docs, "boom")
    assert results and results[0].doc.slug == "sample-tech-boom-error"


def test_search_filters(sample_tree: Path) -> None:
    docs = build_index(sample_tree)
    assert search(docs, technology="sample")
    assert search(docs, tag="boom")
    assert search(docs, severity="high")
    assert not search(docs, technology="kubernetes")
    assert not search(docs, severity="low")


def test_search_by_message(sample_tree: Path) -> None:
    docs = build_index(sample_tree)
    assert search(docs, message="thing exploded")
    assert not search(docs, message="nonexistent message")


def test_search_no_match(sample_tree: Path) -> None:
    docs = build_index(sample_tree)
    assert search(docs, "definitely-not-present-xyz") == []


# --------------------------------------------------------------------------- #
# validate                                                                     #
# --------------------------------------------------------------------------- #


def test_validate_good_doc(sample_tree: Path) -> None:
    issues = validate_file(sample_tree / "sample" / "sample-tech-boom-error.md")
    assert issues == []


def test_validate_catches_missing_section(tmp_path: Path) -> None:
    bad = tmp_path / "bad.md"
    bad.write_text(
        "---\ntitle: B\nslug: bad\ntechnologies: [x]\nseverity: low\ntags: [x]\n---\n\n# B\n",
        encoding="utf-8",
    )
    issues = validate_file(bad)
    assert any("missing required section" in i.message for i in issues)


def test_validate_catches_bad_severity_and_slug(tmp_path: Path) -> None:
    bad = tmp_path / "Bad_Slug.md"
    bad.write_text(
        "---\ntitle: B\nslug: Bad_Slug\ntechnologies: [x]\nseverity: nope\ntags: [x]\n---\n\n# B\n",
        encoding="utf-8",
    )
    issues = validate_file(bad)
    msgs = " ".join(i.message for i in issues)
    assert "severity" in msgs
    assert "kebab-case" in msgs


# --------------------------------------------------------------------------- #
# new_error scaffolding                                                        #
# --------------------------------------------------------------------------- #


def test_slugify() -> None:
    assert slugify("Kubernetes Evicted Pod!") == "kubernetes-evicted-pod"


def test_create_error_and_subdir(tmp_path: Path) -> None:
    path = create_error("Cinder Volume Stuck", "openstack", subdir="cinder", root=tmp_path)
    assert path.exists()
    assert path.parent.name == "cinder"
    meta, _ = split_frontmatter(path.read_text())
    assert meta["slug"] == "cinder-volume-stuck"


# --------------------------------------------------------------------------- #
# integrity of the REAL error tree                                            #
# --------------------------------------------------------------------------- #


def test_real_tree_is_valid(repo_errors: Path) -> None:
    if not repo_errors.exists():  # pragma: no cover
        pytest.skip("no errors/ tree")
    issues = validate_tree(repo_errors)
    assert issues == [], "\n".join(f"{i.path}: {i.message}" for i in issues[:25])


def test_real_tree_has_unique_slugs(repo_errors: Path) -> None:
    if not repo_errors.exists():  # pragma: no cover
        pytest.skip("no errors/ tree")
    docs = build_index(repo_errors)
    slugs = [d.slug for d in docs]
    dupes = {s for s in slugs if slugs.count(s) > 1}
    assert not dupes, f"duplicate slugs: {dupes}"


def test_required_sections_constant() -> None:
    assert "Error Message" in REQUIRED_SECTIONS
    assert "Tags" in REQUIRED_SECTIONS
    assert len(REQUIRED_SECTIONS) == 14
