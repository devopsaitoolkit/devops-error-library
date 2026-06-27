"""Search the error index by message, keyword, technology, tag and severity."""

from __future__ import annotations

from dataclasses import dataclass

from .model import ErrorDoc


@dataclass
class SearchResult:
    """A scored search hit."""

    doc: ErrorDoc
    score: float


def search(
    docs: list[ErrorDoc],
    query: str | None = None,
    *,
    technology: str | None = None,
    tag: str | None = None,
    severity: str | None = None,
    message: str | None = None,
    limit: int = 20,
) -> list[SearchResult]:
    """Filter and rank ``docs``.

    Filters (technology / tag / severity) are ANDed and applied first; the free
    text ``query`` (and ``message``) then rank the survivors. Ranking weights a
    title match highest, then the error-message section, then full-text.
    """
    candidates = [d for d in docs if _passes_filters(d, technology, tag, severity)]

    if not query and not message:
        # No text query: return the filtered set, severity-ordered for triage.
        order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
        candidates.sort(key=lambda d: (order.get(d.severity, 5), d.title.lower()))
        return [SearchResult(doc=d, score=1.0) for d in candidates[:limit]]

    results: list[SearchResult] = []
    for doc in candidates:
        score = 0.0
        if query:
            score += _score_text(doc, query.lower())
        if message:
            needle = message.lower()
            if needle in doc.message.lower():
                score += 5.0
        if score > 0:
            results.append(SearchResult(doc=doc, score=round(score, 3)))

    results.sort(key=lambda r: r.score, reverse=True)
    return results[:limit]


def _passes_filters(
    doc: ErrorDoc, technology: str | None, tag: str | None, severity: str | None
) -> bool:
    if technology and technology.lower() not in [t.lower() for t in doc.technologies]:
        return False
    if tag and tag.lower() not in doc.tags:
        return False
    return not (severity and severity.lower() != doc.severity.lower())


def _score_text(doc: ErrorDoc, needle: str) -> float:
    """Score a free-text needle against a document."""
    score = 0.0
    title = doc.title.lower()
    if needle == title:
        score += 12.0
    elif needle in title:
        score += 8.0
    if needle in doc.slug.lower():
        score += 4.0
    if needle in doc.message.lower():
        score += 5.0
    if needle in [t.lower() for t in doc.tags]:
        score += 3.0
    # Per-term coverage in the full text (handles multi-word queries).
    terms = [t for t in needle.split() if t]
    if terms:
        hits = sum(1 for term in terms if term in doc.text)
        score += 2.0 * (hits / len(terms))
    return score
