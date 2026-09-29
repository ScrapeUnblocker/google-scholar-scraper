from __future__ import annotations

from urllib.parse import parse_qs, urlsplit

import pytest
from conftest import (
    BIBTEX,
    BIBTEX_URL,
    CAPTCHA_HTML,
    CITE_HTML,
    SIGN_IN_HTML,
    author_page,
    author_row,
    prettify,
    result_block,
    results_page,
)

from google_scholar_scraper import (
    Article,
    ScholarBlockedError,
    ScholarNotFoundError,
    ScholarScraper,
)


class Transient(Exception):
    """Stand-in for a retryable ScrapeUnblocker error."""


class Fatal(Exception):
    """Stand-in for a non-retryable error (e.g. a bad API key)."""


class FakeClient:
    """Mimics ``scrapeunblocker.Client.get_page_source`` with scripted responses."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls: list[tuple[str, str | None]] = []

    def get_page_source(self, url, proxy_country=None):
        self.calls.append((url, proxy_country))
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response

    def params(self, n=-1):
        return {k: v[0] for k, v in parse_qs(urlsplit(self.calls[n][0]).query).items()}


def make_scraper(responses, **kwargs):
    client = FakeClient(responses)
    delays: list[float] = []
    scraper = ScholarScraper(
        client=client, transient_errors=(Transient,), sleep=delays.append, **kwargs
    )
    return scraper, client, delays


def page_of(*ids, next_start=10):
    blocks = [result_block(cid, title=f"Paper {cid}") for cid in ids]
    return prettify(results_page(blocks, next_start=next_start))


def ids(n, prefix="a"):
    return [f"{prefix}{i:011d}" for i in range(n)]


# --------------------------------------------------------------------------- #
# Search
# --------------------------------------------------------------------------- #


def test_search_paginates_until_limit():
    first, second = ids(10), ids(10, "b")
    scraper, client, _ = make_scraper([page_of(*first), page_of(*second, next_start=20)])
    articles = scraper.search("graph neural networks", limit=15, year_from=2020)
    assert [a.result_id for a in articles] == first + second[:5]
    assert [a.position for a in articles][-1] == 15
    assert all(a.query == "graph neural networks" for a in articles)
    assert "start" not in client.params(0)
    assert client.params(1)["start"] == "10"
    assert client.params(1)["as_ylo"] == "2020"
    assert client.calls[0][1] == "US"


def test_search_stops_on_last_page():
    scraper, client, _ = make_scraper([page_of(*ids(4), next_start=None)])
    assert len(scraper.search("rare topic", limit=50)) == 4
    assert len(client.calls) == 1


def test_search_stops_when_scholar_repeats_a_page():
    same = page_of(*ids(10))
    scraper, client, _ = make_scraper([same, same, same])
    assert len(scraper.search("x", limit=100)) == 10
    assert len(client.calls) == 2


def test_search_no_results():
    empty = prettify(results_page([], header=None, next_start=None, suggestion="deep learning"))
    scraper, _, _ = make_scraper([empty])
    assert scraper.search("deep lerning") == []


def test_search_validates_before_any_request():
    scraper, client, _ = make_scraper([])
    with pytest.raises(ValueError):
        scraper.search("x", sort="citations")
    with pytest.raises(ValueError):
        scraper.search("x", limit=0)
    assert client.calls == []


def test_search_many_dedupes_across_queries():
    scraper, _, _ = make_scraper(
        [
            page_of("aaaaaaaaaaaa", "bbbbbbbbbbbb", next_start=None),
            page_of("bbbbbbbbbbbb", "cccccccccccc", next_start=None),
        ]
    )
    articles = scraper.search_many(["query one", "query two"], sort="date")
    assert [(a.result_id, a.query) for a in articles] == [
        ("aaaaaaaaaaaa", "query one"),
        ("bbbbbbbbbbbb", "query one"),
        ("cccccccccccc", "query two"),
    ]


def test_proxy_country_and_language_are_passed():
    scraper, client, _ = make_scraper(
        [page_of("aaaaaaaaaaaa", next_start=None)], proxy_country="GB"
    )
    scraper.search("x", language="fr")
    assert client.calls[0][1] == "GB"
    assert client.params()["lr"] == "lang_fr"


# --------------------------------------------------------------------------- #
# Retries
# --------------------------------------------------------------------------- #


def test_retries_transient_errors_and_captcha_with_backoff():
    scraper, client, delays = make_scraper(
        [Transient("timeout"), CAPTCHA_HTML, page_of("aaaaaaaaaaaa", next_start=None)],
        backoff=2,
    )
    seen = []
    scraper.on_retry = lambda attempt, delay, exc: seen.append((attempt, delay, type(exc)))
    assert len(scraper.search("x")) == 1
    assert delays == [2.0, 4.0]
    assert seen == [(1, 2.0, Transient), (2, 4.0, ScholarBlockedError)]
    assert len(client.calls) == 3


def test_backoff_is_capped():
    scraper, _, delays = make_scraper(
        [Transient()] * 4 + [page_of("aaaaaaaaaaaa", next_start=None)],
        retries=4,
        backoff=10,
        max_backoff=25,
    )
    scraper.search("x")
    assert delays == [10.0, 20.0, 25.0, 25.0]


def test_gives_up_after_retries():
    scraper, client, _ = make_scraper([CAPTCHA_HTML] * 3, retries=2)
    with pytest.raises(ScholarBlockedError):
        scraper.search("x")
    assert len(client.calls) == 3


def test_non_transient_errors_are_not_retried():
    scraper, client, delays = make_scraper([Fatal("bad key")])
    with pytest.raises(Fatal):
        scraper.search("x")
    assert len(client.calls) == 1 and delays == []


# --------------------------------------------------------------------------- #
# Cited by
# --------------------------------------------------------------------------- #


def test_cited_by_accepts_article_id_or_url():
    scraper, client, _ = make_scraper([page_of("aaaaaaaaaaaa", next_start=None)] * 3)
    article = Article(result_id="o93zfHYlUTIJ", cites_id="3625720365842685347")
    citing = scraper.cited_by(article, year_from=2025, limit=5)
    assert [a.result_id for a in citing] == ["aaaaaaaaaaaa"]
    assert client.params(0) == {"cites": "3625720365842685347", "hl": "en", "as_ylo": "2025"}
    scraper.cited_by("123,456")
    assert client.params(1)["cites"] == "123,456"
    scraper.cited_by("https://scholar.google.com/scholar?cites=789&hl=en")
    assert client.params(2)["cites"] == "789"


def test_cited_by_uncited_article_makes_no_request():
    scraper, client, _ = make_scraper([])
    assert scraper.cited_by(Article(result_id="o93zfHYlUTIJ")) == []
    assert client.calls == []


# --------------------------------------------------------------------------- #
# Author profiles
# --------------------------------------------------------------------------- #


def rows(n, start=0):
    return [
        author_row(f"Paper {i}", citation_id=f"JicYPdAAAAAJ:{i:012d}")
        for i in range(start, start + n)
    ]


def test_author_paginates_with_cstart():
    scraper, client, _ = make_scraper(
        [
            prettify(author_page(rows(100), has_more=True)),
            prettify(author_page(rows(30, 100), has_more=False)),
        ]
    )
    profile = scraper.author(
        "https://scholar.google.com/citations?user=JicYPdAAAAAJ", max_articles=500
    )
    assert profile.name == "Geoffrey Hinton"
    assert len(profile.articles) == 130
    assert profile.articles[-1].title == "Paper 129"
    assert profile.has_more_articles is False
    assert client.params(0) == {"user": "JicYPdAAAAAJ", "hl": "en", "pagesize": "100"}
    assert client.params(1)["cstart"] == "100"


def test_author_trims_to_max_articles():
    scraper, client, _ = make_scraper([author_page(rows(100), has_more=True)])
    profile = scraper.author("JicYPdAAAAAJ", max_articles=25, sort="year")
    assert len(profile.articles) == 25
    assert profile.has_more_articles is True
    assert client.params()["sortby"] == "pubdate"
    assert len(client.calls) == 1


def test_author_profile_only():
    scraper, _, _ = make_scraper([author_page(rows(3), has_more=False)])
    profile = scraper.author("JicYPdAAAAAJ", max_articles=0)
    assert profile.articles == [] and profile.has_more_articles is True
    assert profile.h_index == 195


def test_author_not_found_is_not_retried():
    scraper, client, delays = make_scraper([SIGN_IN_HTML])
    with pytest.raises(ScholarNotFoundError):
        scraper.author("AAAAAAAAAAAA")
    assert len(client.calls) == 1 and delays == []


def test_author_rejects_bad_ids_without_request():
    scraper, client, _ = make_scraper([])
    with pytest.raises(ValueError):
        scraper.author("geoffrey hinton")
    assert client.calls == []


# --------------------------------------------------------------------------- #
# Citations
# --------------------------------------------------------------------------- #


def test_cite_with_bibtex():
    scraper, client, _ = make_scraper([prettify(CITE_HTML), BIBTEX])
    citation = scraper.cite(Article(result_id="o93zfHYlUTIJ"), bibtex=True)
    assert set(citation.formats) == {"MLA", "APA"}
    assert citation.bibtex == BIBTEX
    assert client.params(0)["q"] == "info:o93zfHYlUTIJ:scholar.google.com/"
    assert client.calls[1][0] == BIBTEX_URL


def test_cite_without_bibtex_is_one_request():
    scraper, client, _ = make_scraper([CITE_HTML])
    assert scraper.cite("o93zfHYlUTIJ").bibtex is None
    assert len(client.calls) == 1


def test_cite_retries_a_captcha_on_the_bibtex_download():
    scraper, client, delays = make_scraper([CITE_HTML, CAPTCHA_HTML, BIBTEX])
    assert scraper.cite("o93zfHYlUTIJ", bibtex=True).bibtex == BIBTEX
    assert len(delays) == 1 and len(client.calls) == 3
