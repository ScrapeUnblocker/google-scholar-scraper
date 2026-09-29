"""JSON and CSV export for google-scholar-scraper records."""

from __future__ import annotations

import csv
import json
from collections.abc import Iterable, Sequence
from dataclasses import asdict, is_dataclass
from typing import Any

from .models import Article, AuthorProfile, Citation

# One CSV row per search result. Authors are flattened to "; "-joined lists.
FIELDNAMES: tuple[str, ...] = (
    "position",
    "result_id",
    "title",
    "url",
    "doc_type",
    "authors",
    "author_ids",
    "venue",
    "year",
    "source",
    "publication_info",
    "snippet",
    "added_ago",
    "cited_by_count",
    "cites_id",
    "cited_by_url",
    "versions_count",
    "cluster_id",
    "versions_url",
    "related_url",
    "full_text_url",
    "full_text_type",
    "full_text_source",
    "query",
)

# One CSV row per publication on an author profile.
AUTHOR_ARTICLE_FIELDNAMES: tuple[str, ...] = (
    "author_id",
    "author_name",
    "title",
    "citation_id",
    "url",
    "authors",
    "publication",
    "year",
    "cited_by_count",
    "cites_id",
    "cited_by_url",
)

CITATION_STYLES: tuple[str, ...] = ("MLA", "APA", "Chicago", "Harvard", "Vancouver")
CITATION_FIELDNAMES: tuple[str, ...] = (
    "result_id",
    *CITATION_STYLES,
    "bibtex",
    "bibtex_url",
    "endnote_url",
    "refman_url",
    "refworks_url",
)


def _plain(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    return value


def to_json(records: Any, *, indent: int | None = None) -> str:
    """Serialize a record, or a list of records, to a JSON string."""
    return json.dumps(_plain(records), ensure_ascii=False, indent=indent)


def article_row(article: Article) -> dict[str, Any]:
    """Flatten an :class:`Article` into a CSV row."""
    row = asdict(article)
    row["authors"] = "; ".join(a.name for a in article.authors)
    row["author_ids"] = "; ".join(a.author_id or "" for a in article.authors)
    return {name: row.get(name) for name in FIELDNAMES}


def author_article_rows(profile: AuthorProfile) -> list[dict[str, Any]]:
    """Flatten an author's publications into CSV rows."""
    rows = []
    for article in profile.articles:
        row: dict[str, Any] = asdict(article)
        row["author_id"] = profile.author_id
        row["author_name"] = profile.name
        rows.append({name: row.get(name) for name in AUTHOR_ARTICLE_FIELDNAMES})
    return rows


def citation_row(citation: Citation) -> dict[str, Any]:
    """Flatten a :class:`Citation` into a CSV row (one column per style)."""
    row: dict[str, Any] = {
        "result_id": citation.result_id,
        "bibtex": citation.bibtex,
        "bibtex_url": citation.bibtex_url,
        "endnote_url": citation.endnote_url,
        "refman_url": citation.refman_url,
        "refworks_url": citation.refworks_url,
    }
    for style in CITATION_STYLES:
        row[style] = citation.formats.get(style)
    return row


def _write_csv(rows: Iterable[dict[str, Any]], path: str, fieldnames: Sequence[str]) -> int:
    count = 0
    # utf-8-sig so Excel shows accented author names correctly.
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(fieldnames))
        writer.writeheader()
        for row in rows:
            writer.writerow({k: "" if row.get(k) is None else row.get(k) for k in fieldnames})
            count += 1
    return count


def to_csv(articles: Iterable[Article], path: str) -> int:
    """Write search results to ``path`` as CSV. Returns the number of rows."""
    return _write_csv((article_row(a) for a in articles), path, FIELDNAMES)


def author_to_csv(profile: AuthorProfile, path: str) -> int:
    """Write an author's publications to ``path`` as CSV. Returns the number of rows."""
    return _write_csv(author_article_rows(profile), path, AUTHOR_ARTICLE_FIELDNAMES)


def citations_to_csv(citations: Iterable[Citation], path: str) -> int:
    """Write citations to ``path`` as CSV (one row per result). Returns the row count."""
    return _write_csv((citation_row(c) for c in citations), path, CITATION_FIELDNAMES)


__all__ = [
    "FIELDNAMES",
    "AUTHOR_ARTICLE_FIELDNAMES",
    "CITATION_FIELDNAMES",
    "CITATION_STYLES",
    "to_json",
    "to_csv",
    "author_to_csv",
    "citations_to_csv",
    "article_row",
    "author_article_rows",
    "citation_row",
]
