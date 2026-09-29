"""Google Scholar URL builders and ID helpers.

Scholar is driven entirely by query-string parameters, so every search, "Cited
by" list, author profile and citation dialog is a plain GET URL that can be
fetched through ScrapeUnblocker. These helpers build those URLs and validate
the IDs Scholar uses (result IDs, "cites" IDs and author IDs).
"""

from __future__ import annotations

import re
from datetime import date
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit

BASE_URL = "https://scholar.google.com"

SORTS: tuple[str, ...] = ("relevance", "date")
AUTHOR_SORTS: tuple[str, ...] = ("citations", "year")

# Scholar lists 10 results per page and never pages past the 1,000th result.
PAGE_SIZE = 10
MAX_RESULTS = 1000
# Author profiles list up to 100 articles per request.
AUTHOR_PAGE_SIZE = 100

_AUTHOR_ID_RE = re.compile(r"^[\w-]{12}$")
_RESULT_ID_RE = re.compile(r"^[\w-]{12}$")
_CITES_ID_RE = re.compile(r"^\d+(?:,\d+)*$")
_LANG_RE = re.compile(r"^[a-z]{2}(?:-[A-Za-z]{2})?$")


def absolute_url(href: str | None) -> str | None:
    """Resolve a Scholar-relative link; ``None`` for empty or ``javascript:`` links."""
    if not href or href.startswith("javascript:"):
        return None
    return urljoin(BASE_URL + "/", href)


def query_param(url: str | None, name: str) -> str | None:
    """First value of query parameter ``name`` in ``url`` (``None`` if absent)."""
    if not url:
        return None
    values = parse_qs(urlsplit(url).query).get(name)
    return values[0] if values else None


def parse_author_id(value: str) -> str:
    """Accept an author ID (``JicYPdAAAAAJ``) or a profile URL and return the ID.

    Raises:
        ValueError: when no valid author ID can be found.
    """
    value = (value or "").strip()
    if "user=" in value:
        value = query_param(value, "user") or ""
    if not _AUTHOR_ID_RE.match(value):
        raise ValueError(
            "expected a Google Scholar author ID like JicYPdAAAAAJ or a profile URL "
            "(https://scholar.google.com/citations?user=...)"
        )
    return value


def parse_cites_id(value: str) -> str:
    """Accept a "cites" ID (or a "Cited by" URL) and return the ID.

    Author-profile articles can carry several comma-separated IDs; those are
    kept as-is (Scholar accepts the list).

    Raises:
        ValueError: when no valid cites ID can be found.
    """
    value = (value or "").strip()
    if "cites=" in value:
        value = query_param(value, "cites") or ""
    value = value.replace(" ", "")
    if not _CITES_ID_RE.match(value):
        raise ValueError(
            "expected a Scholar cites ID like 3625720365842685347 or a 'Cited by' URL "
            "(https://scholar.google.com/scholar?cites=...)"
        )
    return value


def parse_result_id(value: str) -> str:
    """Validate a search-result ID (``o93zfHYlUTIJ``, the ``result_id`` field).

    Raises:
        ValueError: when ``value`` is not a result ID.
    """
    value = (value or "").strip()
    if not _RESULT_ID_RE.match(value):
        raise ValueError(f"expected a Scholar result ID like o93zfHYlUTIJ, not {value!r}")
    return value


def _check_year(value: int | None, name: str) -> int | None:
    if value is None:
        return None
    year = int(value)
    if not 1000 <= year <= date.today().year + 1:
        raise ValueError(f"{name} must be a 4-digit year, not {value!r}")
    return year


def _filters(
    *,
    start: int,
    year_from: int | None,
    year_to: int | None,
    sort: str,
    include_citations: bool,
    language: str | None,
) -> list[tuple[str, str]]:
    """Scholar's result filters as query-string pairs (validated)."""
    if start < 0 or start >= MAX_RESULTS:
        raise ValueError(f"start must be between 0 and {MAX_RESULTS - 1}")
    if sort not in SORTS:
        raise ValueError(f"sort must be one of {', '.join(SORTS)}")
    year_from = _check_year(year_from, "year_from")
    year_to = _check_year(year_to, "year_to")
    if year_from is not None and year_to is not None and year_from > year_to:
        raise ValueError("year_from must not be after year_to")
    params: list[tuple[str, str]] = []
    if start:
        params.append(("start", str(start)))
    if year_from is not None:
        params.append(("as_ylo", str(year_from)))
    if year_to is not None:
        params.append(("as_yhi", str(year_to)))
    if sort == "date":
        # "Sort by date": recently added articles, newest first.
        params.append(("scisbd", "1"))
    if not include_citations:
        params.append(("as_vis", "1"))
    if language:
        if not _LANG_RE.match(language):
            raise ValueError(f"language must be a code like en, de or zh-CN, not {language!r}")
        params.append(("lr", f"lang_{language}"))
    return params


def build_search_url(
    query: str,
    *,
    start: int = 0,
    year_from: int | None = None,
    year_to: int | None = None,
    sort: str = "relevance",
    include_citations: bool = True,
    language: str | None = None,
    hl: str = "en",
) -> str:
    """URL of one Scholar results page for ``query``.

    Args:
        query: Search terms. Scholar operators work too (``author:"hinton"``,
            ``source:nature``, ``intitle:transformer``, ``"exact phrase"``).
        start: Offset of the first result (0, 10, 20, ...).
        year_from / year_to: Only articles published in this year range.
        sort: ``"relevance"`` (default) or ``"date"`` (recently added first).
        include_citations: ``False`` drops citation-only entries ([CITATION]).
        language: Only articles in this language (``"en"``, ``"de"``, ...).
        hl: Scholar interface language (keep ``"en"`` for English labels).
    """
    query = (query or "").strip()
    if not query:
        raise ValueError("give a search query")
    params = [("q", query), ("hl", hl)]
    params += _filters(
        start=start,
        year_from=year_from,
        year_to=year_to,
        sort=sort,
        include_citations=include_citations,
        language=language,
    )
    return f"{BASE_URL}/scholar?{urlencode(params)}"


def build_cited_by_url(
    cites_id: str,
    *,
    start: int = 0,
    year_from: int | None = None,
    year_to: int | None = None,
    sort: str = "relevance",
    include_citations: bool = True,
    language: str | None = None,
    hl: str = "en",
) -> str:
    """URL of one page of the articles citing a result (its "Cited by" list)."""
    params = [("cites", parse_cites_id(cites_id)), ("hl", hl)]
    params += _filters(
        start=start,
        year_from=year_from,
        year_to=year_to,
        sort=sort,
        include_citations=include_citations,
        language=language,
    )
    return f"{BASE_URL}/scholar?{urlencode(params)}"


def build_author_url(
    author_id: str,
    *,
    start: int = 0,
    page_size: int = AUTHOR_PAGE_SIZE,
    sort: str = "citations",
    hl: str = "en",
) -> str:
    """URL of an author profile, listing ``page_size`` articles from ``start``.

    ``sort`` is ``"citations"`` (Scholar's default, most cited first) or
    ``"year"`` (newest first).
    """
    if sort not in AUTHOR_SORTS:
        raise ValueError(f"sort must be one of {', '.join(AUTHOR_SORTS)}")
    if start < 0:
        raise ValueError("start must not be negative")
    if not 1 <= page_size <= AUTHOR_PAGE_SIZE:
        raise ValueError(f"page_size must be between 1 and {AUTHOR_PAGE_SIZE}")
    params = [("user", parse_author_id(author_id)), ("hl", hl)]
    if start:
        params.append(("cstart", str(start)))
    params.append(("pagesize", str(page_size)))
    if sort == "year":
        params.append(("sortby", "pubdate"))
    return f"{BASE_URL}/citations?{urlencode(params)}"


def author_profile_url(author_id: str, hl: str = "en") -> str:
    """Canonical, shareable profile URL for an author ID."""
    return f"{BASE_URL}/citations?{urlencode([('user', author_id), ('hl', hl)])}"


def build_cite_url(result_id: str, *, hl: str = "en") -> str:
    """URL of the "Cite" dialog (MLA, APA, ... and BibTeX links) for a result."""
    result_id = parse_result_id(result_id)
    params = [
        ("q", f"info:{result_id}:scholar.google.com/"),
        ("output", "cite"),
        ("scirp", "0"),
        ("hl", hl),
    ]
    return f"{BASE_URL}/scholar?{urlencode(params)}"
