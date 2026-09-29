"""Command-line interface for google-scholar-scraper.

Examples:
    google-scholar-scraper search "large language models" --limit 20 --pretty
    google-scholar-scraper search "crispr off-target" "prime editing" --from 2022 \\
        --limit 30 --format csv --output crispr.csv
    google-scholar-scraper cited-by 3625720365842685347 --from 2025 --limit 20
    google-scholar-scraper author JicYPdAAAAAJ --max-articles 200 --output hinton.json
    google-scholar-scraper cite o93zfHYlUTIJ --bibtex
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from typing import Any

from . import __version__
from .export import author_to_csv, citations_to_csv, to_csv, to_json
from .models import AuthorProfile, ResultsPage
from .parsing import ScholarError, ScholarNotFoundError
from .scraper import DEFAULT_PROXY_COUNTRY, ScholarScraper
from .urls import (
    AUTHOR_SORTS,
    SORTS,
    build_search_url,
    parse_author_id,
    parse_cites_id,
    parse_result_id,
)

PROG = "google-scholar-scraper"


def _output_options() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    out = common.add_argument_group("output and requests")
    out.add_argument(
        "-f",
        "--format",
        choices=("json", "csv"),
        default="json",
        help="Output format (default: json).",
    )
    out.add_argument("-o", "--output", metavar="PATH", help="Write to this file, not stdout.")
    out.add_argument("--pretty", action="store_true", help="Pretty-print JSON (indented).")
    out.add_argument(
        "--proxy-country",
        default=DEFAULT_PROXY_COUNTRY,
        metavar="ISO",
        help=f"Country to route requests through (default: {DEFAULT_PROXY_COUNTRY}).",
    )
    out.add_argument(
        "--retries",
        type=int,
        default=3,
        metavar="N",
        help="Retries per page on CAPTCHAs and transient errors, with doubling backoff "
        "(default: 3).",
    )
    out.add_argument("-q", "--quiet", action="store_true", help="No progress output on stderr.")
    return common


def _result_filters(parser: argparse.ArgumentParser) -> None:
    filters = parser.add_argument_group("filters")
    filters.add_argument(
        "-n",
        "--limit",
        type=int,
        default=10,
        metavar="N",
        help="Maximum number of articles (default: 10; one request per 10).",
    )
    filters.add_argument(
        "--from", dest="year_from", type=int, metavar="YEAR", help="Published in or after YEAR."
    )
    filters.add_argument(
        "--to", dest="year_to", type=int, metavar="YEAR", help="Published in or before YEAR."
    )
    filters.add_argument(
        "-s",
        "--sort",
        choices=SORTS,
        default="relevance",
        help="relevance (default) or date (recently added articles first).",
    )
    filters.add_argument(
        "--no-citations",
        dest="include_citations",
        action="store_false",
        help="Drop citation-only [CITATION] entries.",
    )
    filters.add_argument(
        "--lang",
        dest="language",
        metavar="CODE",
        help="Only articles in this language, e.g. en, de, fr, zh-CN.",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROG,
        description="Scrape Google Scholar (search results, 'Cited by' lists, author "
        "profiles and citations) into clean JSON or CSV via the ScrapeUnblocker "
        "getPageSource API.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    common = _output_options()
    commands = parser.add_subparsers(dest="command", metavar="COMMAND")
    commands.required = True

    search = commands.add_parser(
        "search",
        parents=[common],
        help="Search Google Scholar.",
        description="Search Google Scholar. Several queries are merged and de-duplicated.",
    )
    search.add_argument(
        "queries",
        nargs="+",
        metavar="QUERY",
        help='Search terms. Scholar operators work: author:"lecun", source:nature, '
        'intitle:transformer, "exact phrase".',
    )
    _result_filters(search)

    cited = commands.add_parser(
        "cited-by",
        parents=[common],
        help="List the articles citing a paper.",
        description="List the articles citing a paper (its 'Cited by' list).",
    )
    cited.add_argument(
        "cites_id",
        metavar="CITES_ID",
        help="The paper's cites_id (from search or author output) or its 'Cited by' URL.",
    )
    _result_filters(cited)

    author = commands.add_parser(
        "author",
        parents=[common],
        help="Scrape an author profile.",
        description="Scrape a public author profile: affiliation, interests, citation "
        "metrics, citations per year, co-authors and publications. CSV output lists "
        "the publications.",
    )
    author.add_argument(
        "author_id",
        metavar="AUTHOR",
        help="Author ID (e.g. JicYPdAAAAAJ, from search output) or profile URL.",
    )
    author.add_argument(
        "-m",
        "--max-articles",
        type=int,
        default=100,
        metavar="N",
        help="Publications to collect (default: 100; one request per 100).",
    )
    author.add_argument(
        "-s",
        "--sort",
        choices=AUTHOR_SORTS,
        default="citations",
        help="citations (most cited first, default) or year (newest first).",
    )

    cite = commands.add_parser(
        "cite",
        parents=[common],
        help="Get MLA/APA/Chicago/Harvard/Vancouver citations.",
        description="Get ready-made citations (MLA, APA, Chicago, Harvard, Vancouver) "
        "and BibTeX / EndNote / RefMan / RefWorks links for search results.",
    )
    cite.add_argument(
        "result_ids",
        nargs="+",
        metavar="RESULT_ID",
        help="result_id values from search output, e.g. o93zfHYlUTIJ.",
    )
    cite.add_argument(
        "--bibtex",
        action="store_true",
        help="Also download each BibTeX entry (one extra request per result).",
    )
    return parser


def validate(args: argparse.Namespace) -> None:
    """Check argument combinations argparse cannot express.

    Raises:
        ValueError: with a message suitable for ``parser.error``.
    """
    if args.format == "csv" and not args.output:
        raise ValueError("--format csv requires --output PATH")
    if args.retries < 0:
        raise ValueError("--retries must not be negative")
    if args.command in ("search", "cited-by"):
        if args.limit < 1:
            raise ValueError("--limit must be at least 1")
        if args.year_from and args.year_to and args.year_from > args.year_to:
            raise ValueError("--from must not be after --to")
        # Same checks the scraper runs (year range, language code), before any request.
        build_search_url(
            "validate",
            year_from=args.year_from,
            year_to=args.year_to,
            sort=args.sort,
            language=args.language,
        )
    if args.command == "search" and not any(q.strip() for q in args.queries):
        raise ValueError("give at least one non-empty QUERY")
    if args.command == "cited-by":
        args.cites_id = parse_cites_id(args.cites_id)
    if args.command == "author":
        if args.max_articles < 0:
            raise ValueError("--max-articles must not be negative")
        args.author_id = parse_author_id(args.author_id)
    if args.command == "cite":
        args.result_ids = [parse_result_id(r) for r in args.result_ids]


def _say(line: str) -> None:
    try:
        print(line, file=sys.stderr)
    except UnicodeEncodeError:  # legacy console
        print(line.encode("ascii", "replace").decode("ascii"), file=sys.stderr)


def _page_progress(label: str):
    def report(page: ResultsPage) -> None:
        total = f" (about {page.total_results:,})" if page.total_results is not None else ""
        number = page.start // 10 + 1
        _say(f"[scholar] {label} page {number}: {len(page.articles)} results{total}")
        if not page.articles and page.suggestion:
            _say(f"[scholar] no results - did you mean: {page.suggestion}?")

    return report


def _author_progress(page: AuthorProfile) -> None:
    _say(f"[scholar] author {page.author_id} ({page.name}): {len(page.articles)} articles")


def _retrying(attempt: int, delay: float, error: BaseException) -> None:
    reason = str(error) or type(error).__name__
    _say(f"[scholar] {reason}; retry {attempt} in {delay:g}s")


def _write_output(text: str, output: str | None) -> None:
    if output:
        with open(output, "w", encoding="utf-8") as fh:
            fh.write(text)
    else:
        # Titles and author names carry non-ASCII glyphs; force UTF-8 so
        # printing on a legacy Windows console does not raise.
        try:
            sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            pass
        print(text)


def run(args: argparse.Namespace, scraper: ScholarScraper) -> tuple[Any, int]:
    """Execute a parsed command. Returns ``(records, count)``."""
    quiet = args.quiet
    filters: dict[str, Any] = {}
    if args.command in ("search", "cited-by"):
        filters = {
            "year_from": args.year_from,
            "year_to": args.year_to,
            "sort": args.sort,
            "include_citations": args.include_citations,
            "language": args.language,
        }
    if args.command == "search":
        seen: set[str] = set()
        articles = []
        for query in (q.strip() for q in args.queries if q.strip()):
            articles += scraper.search(
                query,
                limit=args.limit,
                seen=seen,
                on_page=None if quiet else _page_progress(f'"{query}"'),
                **filters,
            )
        if args.format == "csv":
            return to_csv(articles, args.output), len(articles)
        return articles, len(articles)
    if args.command == "cited-by":
        articles = scraper.cited_by(
            args.cites_id,
            limit=args.limit,
            on_page=None if quiet else _page_progress(f"cited by {args.cites_id}"),
            **filters,
        )
        if args.format == "csv":
            return to_csv(articles, args.output), len(articles)
        return articles, len(articles)
    if args.command == "author":
        profile = scraper.author(
            args.author_id,
            max_articles=args.max_articles,
            sort=args.sort,
            on_page=None if quiet else _author_progress,
        )
        if args.format == "csv":
            return author_to_csv(profile, args.output), len(profile.articles)
        return profile, len(profile.articles)
    citations = []
    for result_id in args.result_ids:
        citation = scraper.cite(result_id, bibtex=args.bibtex)
        if not quiet:
            extra = " + BibTeX" if citation.bibtex else ""
            _say(f"[scholar] cite {result_id}: {len(citation.formats)} styles{extra}")
        citations.append(citation)
    if args.format == "csv":
        return citations_to_csv(citations, args.output), len(citations)
    return citations, len(citations)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        validate(args)
    except ValueError as exc:
        parser.error(str(exc))

    scraper = ScholarScraper(
        proxy_country=args.proxy_country or None,
        retries=args.retries,
        on_retry=None if args.quiet else _retrying,
    )
    try:
        records, count = run(args, scraper)
    except ScholarNotFoundError as exc:
        print(f"error: {exc}.", file=sys.stderr)
        return 1
    except ScholarError as exc:
        print(f"error: {exc}. Try again in a few minutes or raise --retries.", file=sys.stderr)
        return 1

    what = {"author": "articles", "cite": "citations"}.get(args.command, "articles")
    if args.format == "json":
        _write_output(to_json(records, indent=2 if args.pretty else None), args.output)
    if args.output:
        print(f"Wrote {count} {what} to {args.output}", file=sys.stderr)
    elif count == 0 and args.command != "author":
        print("No results.", file=sys.stderr)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
