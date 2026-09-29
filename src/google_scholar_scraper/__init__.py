"""google-scholar-scraper - clean Google Scholar data via the ScrapeUnblocker API.

Search Google Scholar and get clean, typed JSON for every result: title, result
ID, document type, authors (with their Scholar profile IDs), venue, year,
source, snippet, full-text PDF/HTML link, "Cited by" count and versions count.
Follow a paper's "Cited by" list, pull complete author profiles (affiliation,
interests, citations / h-index / i10-index, citations per year, co-authors and
every publication) and get ready-made MLA / APA / Chicago / Harvard / Vancouver
citations or BibTeX. Pages are loaded in a real browser through the
ScrapeUnblocker ``getPageSource`` API, and Scholar's CAPTCHA pages are
detected and retried automatically.

Example:
    >>> from google_scholar_scraper import ScholarScraper
    >>> scholar = ScholarScraper()                     # reads SCRAPEUNBLOCKER_KEY
    >>> papers = scholar.search("large language models", limit=20)  # doctest: +SKIP
    >>> papers[0].title, papers[0].cited_by_count                  # doctest: +SKIP
    ('A survey on evaluation of large language models', 6818)
"""

from __future__ import annotations

from .export import (
    AUTHOR_ARTICLE_FIELDNAMES,
    CITATION_FIELDNAMES,
    CITATION_STYLES,
    FIELDNAMES,
    article_row,
    author_to_csv,
    citations_to_csv,
    to_csv,
    to_json,
)
from .models import (
    Article,
    AuthorArticle,
    AuthorProfile,
    AuthorRef,
    Citation,
    CoAuthor,
    ResultsPage,
)
from .parsing import (
    ScholarBlockedError,
    ScholarError,
    ScholarNotFoundError,
    ScholarParseError,
    clean_text,
    parse_author_page,
    parse_cite_page,
    parse_results_page,
    split_publication_info,
)
from .scraper import DEFAULT_PROXY_COUNTRY, ScholarScraper
from .urls import (
    AUTHOR_SORTS,
    SORTS,
    build_author_url,
    build_cite_url,
    build_cited_by_url,
    build_search_url,
    parse_author_id,
    parse_cites_id,
)

__all__ = [
    "ScholarScraper",
    "Article",
    "AuthorRef",
    "ResultsPage",
    "AuthorProfile",
    "AuthorArticle",
    "CoAuthor",
    "Citation",
    "ScholarError",
    "ScholarParseError",
    "ScholarBlockedError",
    "ScholarNotFoundError",
    "build_search_url",
    "build_cited_by_url",
    "build_author_url",
    "build_cite_url",
    "parse_author_id",
    "parse_cites_id",
    "parse_results_page",
    "parse_author_page",
    "parse_cite_page",
    "split_publication_info",
    "clean_text",
    "to_json",
    "to_csv",
    "author_to_csv",
    "citations_to_csv",
    "article_row",
    "FIELDNAMES",
    "AUTHOR_ARTICLE_FIELDNAMES",
    "CITATION_FIELDNAMES",
    "CITATION_STYLES",
    "SORTS",
    "AUTHOR_SORTS",
    "DEFAULT_PROXY_COUNTRY",
]

__version__ = "0.1.0"
