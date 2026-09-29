"""Typed records returned by google-scholar-scraper.

Every field that Google Scholar does not show for an item is ``None`` (or an
empty list / dict), never an empty string, so the records are safe to load into
a dataframe or a database as-is.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AuthorRef:
    """An author as listed under a search result.

    ``author_id`` (and ``url``) are only set when the author has a public
    Google Scholar profile that Scholar links to from the result.
    """

    name: str
    author_id: str | None = None
    url: str | None = None


@dataclass
class Article:
    """One Google Scholar search result (also used for "Cited by" lists).

    ``venue`` and ``authors`` are what Scholar prints under the title, so they
    may be truncated with "…" for long author lists or journal names.
    ``cites_id`` is the ID behind the "Cited by" link: pass it to
    :meth:`ScholarScraper.cited_by` to list the citing articles.
    """

    position: int | None = None
    result_id: str | None = None
    title: str | None = None
    url: str | None = None
    doc_type: str | None = None
    authors: list[AuthorRef] = field(default_factory=list)
    publication_info: str | None = None
    venue: str | None = None
    year: int | None = None
    source: str | None = None
    snippet: str | None = None
    added_ago: str | None = None
    cited_by_count: int | None = None
    cites_id: str | None = None
    cited_by_url: str | None = None
    versions_count: int | None = None
    cluster_id: str | None = None
    versions_url: str | None = None
    related_url: str | None = None
    full_text_url: str | None = None
    full_text_type: str | None = None
    full_text_source: str | None = None
    query: str | None = None


@dataclass
class ResultsPage:
    """One page of Scholar results (10 articles at most)."""

    articles: list[Article] = field(default_factory=list)
    total_results: int | None = None
    start: int = 0
    has_next: bool = False
    suggestion: str | None = None
    url: str | None = None


@dataclass
class CoAuthor:
    """A co-author listed on a Scholar profile."""

    name: str
    author_id: str | None = None
    affiliation: str | None = None
    url: str | None = None


@dataclass
class AuthorArticle:
    """One publication on a Scholar profile.

    ``cites_id`` can hold several comma-separated IDs when Scholar merged
    duplicate versions of the paper; :meth:`ScholarScraper.cited_by` accepts it
    as-is.
    """

    title: str | None = None
    citation_id: str | None = None
    url: str | None = None
    authors: str | None = None
    publication: str | None = None
    year: int | None = None
    cited_by_count: int | None = None
    cites_id: str | None = None
    cited_by_url: str | None = None


@dataclass
class AuthorProfile:
    """A public Google Scholar author profile.

    ``citations`` / ``h_index`` / ``i10_index`` are all-time figures; the
    ``*_recent`` ones cover the years since ``recent_since`` (Scholar's
    "Since <year>" column). ``citations_per_year`` maps year to citation count.
    """

    author_id: str
    name: str | None = None
    affiliation: str | None = None
    organization: str | None = None
    organization_id: str | None = None
    email_domain: str | None = None
    homepage: str | None = None
    interests: list[str] = field(default_factory=list)
    photo_url: str | None = None
    citations: int | None = None
    citations_recent: int | None = None
    h_index: int | None = None
    h_index_recent: int | None = None
    i10_index: int | None = None
    i10_index_recent: int | None = None
    recent_since: int | None = None
    citations_per_year: dict[int, int] = field(default_factory=dict)
    co_authors: list[CoAuthor] = field(default_factory=list)
    articles: list[AuthorArticle] = field(default_factory=list)
    has_more_articles: bool = False
    url: str | None = None


@dataclass
class Citation:
    """Ready-made citations for one search result (Scholar's "Cite" dialog).

    ``formats`` maps a style name (``"MLA"``, ``"APA"``, ``"Chicago"``,
    ``"Harvard"``, ``"Vancouver"``) to the formatted reference. ``bibtex`` is
    only filled in when you ask for it (one extra request).
    """

    result_id: str
    formats: dict[str, str] = field(default_factory=dict)
    bibtex_url: str | None = None
    endnote_url: str | None = None
    refman_url: str | None = None
    refworks_url: str | None = None
    bibtex: str | None = None
