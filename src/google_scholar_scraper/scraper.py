"""Scrape Google Scholar through the ScrapeUnblocker ``getPageSource`` API.

Every Scholar page (a results page, a "Cited by" list, an author profile, the
"Cite" dialog) is loaded in a real browser by ScrapeUnblocker and returned as
HTML, which :mod:`google_scholar_scraper.parsing` turns into typed records.

Google Scholar is quick to show a CAPTCHA to automated traffic. When one comes
back anyway, the request is retried with doubling backoff (as are timeouts and
other transient API errors), so a long collection run keeps going.
"""

from __future__ import annotations

import time
from collections.abc import Iterable, Sequence
from typing import Any, Callable

from .models import Article, AuthorProfile, Citation, ResultsPage
from .parsing import (
    ScholarParseError,
    check_page,
    parse_author_page,
    parse_bibtex,
    parse_cite_page,
    parse_results_page,
)
from .urls import (
    AUTHOR_PAGE_SIZE,
    MAX_RESULTS,
    PAGE_SIZE,
    build_author_url,
    build_cite_url,
    build_cited_by_url,
    build_search_url,
    parse_author_id,
    parse_cites_id,
    parse_result_id,
)

# Scholar serves the same results whatever the country; a fixed route keeps
# the interface language and result order consistent between runs.
DEFAULT_PROXY_COUNTRY = "US"


def _transient_errors() -> tuple[type[BaseException], ...]:
    """Best-effort tuple of ScrapeUnblocker exceptions worth retrying.

    Imported lazily so the package is usable (and unit-testable) even when the
    ``scrapeunblocker`` SDK is not installed.
    """
    try:
        from scrapeunblocker import (  # type: ignore
            BlockedError,
            BrowserTimeoutError,
            RateLimitError,
            ScrapeTimeoutError,
            ServerError,
            UpstreamOutageError,
        )
        from scrapeunblocker import (
            ConnectionError as SUConnectionError,
        )
    except Exception:  # pragma: no cover - depends on SDK availability
        return ()
    return (
        UpstreamOutageError,
        RateLimitError,
        ScrapeTimeoutError,
        BrowserTimeoutError,
        BlockedError,
        ServerError,
        SUConnectionError,
    )


def _article_key(article: Article) -> str | None:
    return article.result_id or article.url or article.title


class ScholarScraper:
    """Scrape Google Scholar search results, citations and author profiles.

    Args:
        api_key: ScrapeUnblocker key. If omitted, the SDK reads
            ``SCRAPEUNBLOCKER_KEY`` from the environment.
        client: A pre-built client (or any object exposing
            ``get_page_source(url, proxy_country=...)``). Mainly for testing.
        proxy_country: Country to route requests through (default ``"US"``).
        hl: Scholar interface language. Keep ``"en"``: a few fields (the result
            count, "N days ago", verified email) are read from English labels.
        retries: Extra attempts per page on transient failures, including a
            CAPTCHA page or an unexpected interstitial.
        backoff: Seconds before the first retry; doubles on every further retry.
        max_backoff: Upper bound for a single wait between retries.
        timeout: Per-request timeout passed to the SDK client.
        transient_errors: Exception classes treated as retryable. Defaults to
            the ScrapeUnblocker transient set.
        on_retry: Optional callback ``(attempt, delay_seconds, error)`` invoked
            before every retry (handy for progress output).
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        client: Any | None = None,
        proxy_country: str | None = DEFAULT_PROXY_COUNTRY,
        hl: str = "en",
        retries: int = 3,
        backoff: float = 5.0,
        max_backoff: float = 60.0,
        timeout: float = 180.0,
        transient_errors: Sequence[type[BaseException]] | None = None,
        sleep: Callable[[float], None] = time.sleep,
        on_retry: Callable[[int, float, BaseException], None] | None = None,
    ) -> None:
        if client is None:
            from scrapeunblocker import Client  # local import: optional dep

            client = Client(api_key=api_key, timeout=timeout)
        self._client = client
        self.proxy_country = proxy_country
        self.hl = hl
        self.retries = max(0, int(retries))
        self.backoff = float(backoff)
        self.max_backoff = float(max_backoff)
        self.on_retry = on_retry
        transient = tuple(transient_errors) if transient_errors is not None else _transient_errors()
        self._transient = (*transient, ScholarParseError)
        self._sleep = sleep

    # ------------------------------------------------------------------ #
    # Low-level fetching
    # ------------------------------------------------------------------ #

    def _fetch(self, url: str, parse: Callable[[str], Any]) -> Any:
        """Fetch ``url`` and parse it, retrying transient failures with backoff."""
        attempt = 0
        while True:
            try:
                html = self._client.get_page_source(url, proxy_country=self.proxy_country)
                return parse(html if isinstance(html, str) else "")
            except self._transient as exc:
                if attempt >= self.retries:
                    raise
                attempt += 1
                delay = min(self.backoff * 2 ** (attempt - 1), self.max_backoff)
                if self.on_retry is not None:
                    self.on_retry(attempt, delay, exc)
                self._sleep(delay)

    def fetch_results_page(self, url: str, *, start: int = 0) -> ResultsPage:
        """Fetch and parse one results page (search or "Cited by")."""
        return self._fetch(url, lambda html: parse_results_page(html, url=url, start=start))

    # ------------------------------------------------------------------ #
    # Search / "Cited by"
    # ------------------------------------------------------------------ #

    def _collect(
        self,
        url_for: Callable[[int], str],
        *,
        limit: int,
        query: str | None,
        seen: set[str] | None,
        on_page: Callable[[ResultsPage], None] | None,
    ) -> list[Article]:
        if limit < 1:
            raise ValueError("limit must be at least 1")
        seen = set() if seen is None else seen
        own: set[str] = set()  # keys met by this collection (guards against repeats)
        articles: list[Article] = []
        start = 0
        while len(articles) < limit and start < MAX_RESULTS:
            page = self.fetch_results_page(url_for(start), start=start)
            if on_page is not None:
                on_page(page)
            keys = [_article_key(article) for article in page.articles]
            fresh = any(key is not None and key not in own for key in keys)
            own.update(key for key in keys if key is not None)
            for article, key in zip(page.articles, keys):
                if key is None or key in seen:
                    continue
                seen.add(key)
                article.query = query
                articles.append(article)
                if len(articles) >= limit:
                    break
            if not page.has_next or not fresh:
                break
            start += PAGE_SIZE
        return articles

    def search(
        self,
        query: str,
        *,
        limit: int = 10,
        year_from: int | None = None,
        year_to: int | None = None,
        sort: str = "relevance",
        include_citations: bool = True,
        language: str | None = None,
        seen: set[str] | None = None,
        on_page: Callable[[ResultsPage], None] | None = None,
    ) -> list[Article]:
        """Search Google Scholar and return up to ``limit`` articles.

        Pages of 10 are fetched until ``limit`` is reached, Scholar runs out of
        results, or the 1,000-result ceiling Scholar imposes on every search.

        Args:
            query: Search terms; Scholar operators work (``author:"lecun"``,
                ``source:nature``, ``intitle:...``, ``"exact phrase"``).
            limit: Maximum number of articles (one request per 10).
            year_from / year_to: Only articles published in this year range.
            sort: ``"relevance"`` or ``"date"`` (recently added articles first).
            include_citations: ``False`` drops citation-only ([CITATION]) entries.
            language: Only articles in this language (``"en"``, ``"de"``, ...).
            seen: Shared de-duplication set (used by :meth:`search_many`).
            on_page: Optional callback invoked with every fetched page.

        Returns:
            A list of :class:`Article`, de-duplicated by result ID.
        """
        build_search_url(  # validate the arguments before spending a request
            query,
            year_from=year_from,
            year_to=year_to,
            sort=sort,
            include_citations=include_citations,
            language=language,
            hl=self.hl,
        )
        return self._collect(
            lambda start: build_search_url(
                query,
                start=start,
                year_from=year_from,
                year_to=year_to,
                sort=sort,
                include_citations=include_citations,
                language=language,
                hl=self.hl,
            ),
            limit=limit,
            query=query.strip(),
            seen=seen,
            on_page=on_page,
        )

    def search_many(
        self,
        queries: Iterable[str],
        *,
        limit_per_query: int = 10,
        on_page: Callable[[ResultsPage], None] | None = None,
        **filters: Any,
    ) -> list[Article]:
        """Run several searches and merge the results, de-duplicated by result ID.

        ``filters`` are passed to :meth:`search` (``year_from``, ``sort``, ...).
        Every article records the ``query`` that found it first.
        """
        seen: set[str] = set()
        articles: list[Article] = []
        for query in queries:
            if query and query.strip():
                articles += self.search(
                    query, limit=limit_per_query, seen=seen, on_page=on_page, **filters
                )
        return articles

    def cited_by(
        self,
        cites_id: str | Article,
        *,
        limit: int = 10,
        year_from: int | None = None,
        year_to: int | None = None,
        sort: str = "relevance",
        include_citations: bool = True,
        language: str | None = None,
        on_page: Callable[[ResultsPage], None] | None = None,
    ) -> list[Article]:
        """List the articles citing a paper (Scholar's "Cited by" list).

        Args:
            cites_id: An :class:`Article` (its ``cites_id`` is used), a cites
                ID such as ``"3625720365842685347"``, or a "Cited by" URL.
            limit, year_from, year_to, sort, include_citations, language,
            on_page: As in :meth:`search`.
        """
        if isinstance(cites_id, Article):
            if not cites_id.cites_id:
                return []  # nobody has cited it (yet)
            cites_id = cites_id.cites_id
        cid = parse_cites_id(cites_id)
        return self._collect(
            lambda start: build_cited_by_url(
                cid,
                start=start,
                year_from=year_from,
                year_to=year_to,
                sort=sort,
                include_citations=include_citations,
                language=language,
                hl=self.hl,
            ),
            limit=limit,
            query=None,
            seen=None,
            on_page=on_page,
        )

    # ------------------------------------------------------------------ #
    # Author profiles
    # ------------------------------------------------------------------ #

    def author(
        self,
        author_id: str,
        *,
        max_articles: int = AUTHOR_PAGE_SIZE,
        sort: str = "citations",
        on_page: Callable[[AuthorProfile], None] | None = None,
    ) -> AuthorProfile:
        """Fetch a public author profile with up to ``max_articles`` publications.

        Args:
            author_id: The ``user=`` ID (``"JicYPdAAAAAJ"``) or a profile URL.
            max_articles: Publications to collect (one request per 100). With 0
                you still get the profile, metrics and co-authors (one request).
            sort: ``"citations"`` (most cited first) or ``"year"`` (newest first).
            on_page: Optional callback invoked with every fetched page.

        Raises:
            ScholarNotFoundError: the profile does not exist or is not public.
        """
        author_id = parse_author_id(author_id)
        if max_articles < 0:
            raise ValueError("max_articles must not be negative")
        profile: AuthorProfile | None = None
        start = 0
        while True:
            url = build_author_url(
                author_id, start=start, page_size=AUTHOR_PAGE_SIZE, sort=sort, hl=self.hl
            )
            page = self._fetch(url, lambda html: parse_author_page(html, author_id=author_id))
            if on_page is not None:
                on_page(page)
            if profile is None:
                profile = page
            else:
                profile.articles += page.articles
                profile.has_more_articles = page.has_more_articles
            if (
                len(profile.articles) >= max_articles
                or not page.has_more_articles
                or not page.articles
            ):
                break
            start += AUTHOR_PAGE_SIZE
        if len(profile.articles) > max_articles:
            profile.articles = profile.articles[:max_articles]
            profile.has_more_articles = True
        return profile

    # ------------------------------------------------------------------ #
    # Citations
    # ------------------------------------------------------------------ #

    def cite(self, result_id: str | Article, *, bibtex: bool = False) -> Citation:
        """Get ready-made MLA / APA / Chicago / Harvard / Vancouver citations.

        Args:
            result_id: An :class:`Article` or its ``result_id``.
            bibtex: Also download the BibTeX entry (one extra request).
        """
        if isinstance(result_id, Article):
            result_id = result_id.result_id or ""
        rid = parse_result_id(result_id)
        citation: Citation = self._fetch(
            build_cite_url(rid, hl=self.hl), lambda html: parse_cite_page(html, result_id=rid)
        )
        if bibtex and citation.bibtex_url:
            citation.bibtex = self._fetch(citation.bibtex_url, _require_bibtex)
        return citation


def _require_bibtex(text: str) -> str:
    check_page(text)  # raises ScholarBlockedError on a CAPTCHA page
    entry = parse_bibtex(text)
    if entry is None:
        raise ScholarParseError("Scholar returned no BibTeX entry")
    return entry
