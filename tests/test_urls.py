from __future__ import annotations

from urllib.parse import parse_qs, urlsplit

import pytest

from google_scholar_scraper import (
    build_author_url,
    build_cite_url,
    build_cited_by_url,
    build_search_url,
    parse_author_id,
    parse_cites_id,
)
from google_scholar_scraper.urls import absolute_url, parse_result_id, query_param


def params(url: str) -> dict[str, str]:
    return {k: v[0] for k, v in parse_qs(urlsplit(url).query).items()}


def test_search_url_defaults():
    url = build_search_url("large language models")
    assert url.startswith("https://scholar.google.com/scholar?")
    assert params(url) == {"q": "large language models", "hl": "en"}


def test_search_url_all_filters():
    url = build_search_url(
        'author:"hinton" dropout',
        start=20,
        year_from=2019,
        year_to=2021,
        sort="date",
        include_citations=False,
        language="de",
    )
    assert params(url) == {
        "q": 'author:"hinton" dropout',
        "hl": "en",
        "start": "20",
        "as_ylo": "2019",
        "as_yhi": "2021",
        "scisbd": "1",
        "as_vis": "1",
        "lr": "lang_de",
    }


@pytest.mark.parametrize(
    "kwargs",
    [
        {"query": "  "},
        {"query": "x", "sort": "citations"},
        {"query": "x", "year_from": 2022, "year_to": 2020},
        {"query": "x", "year_from": 99},
        {"query": "x", "start": 1000},
        {"query": "x", "start": -10},
        {"query": "x", "language": "english"},
    ],
)
def test_search_url_rejects_bad_arguments(kwargs):
    with pytest.raises(ValueError):
        build_search_url(**kwargs)


def test_cited_by_url_accepts_id_or_url():
    url = build_cited_by_url("3625720365842685347", start=10, year_from=2025)
    assert params(url) == {
        "cites": "3625720365842685347",
        "hl": "en",
        "start": "10",
        "as_ylo": "2025",
    }
    from_url = build_cited_by_url(
        "https://scholar.google.com/scholar?cites=3625720365842685347&as_sdt=5,33&hl=en"
    )
    assert params(from_url)["cites"] == "3625720365842685347"


def test_cited_by_url_keeps_merged_ids():
    url = build_cited_by_url("2071317309766942398,1036029811429977192")
    assert params(url)["cites"] == "2071317309766942398,1036029811429977192"


def test_author_url():
    url = build_author_url("JicYPdAAAAAJ", start=100, sort="year")
    assert url.startswith("https://scholar.google.com/citations?")
    assert params(url) == {
        "user": "JicYPdAAAAAJ",
        "hl": "en",
        "cstart": "100",
        "pagesize": "100",
        "sortby": "pubdate",
    }
    assert "cstart" not in params(build_author_url("JicYPdAAAAAJ"))
    with pytest.raises(ValueError):
        build_author_url("JicYPdAAAAAJ", sort="title")
    with pytest.raises(ValueError):
        build_author_url("JicYPdAAAAAJ", page_size=500)


def test_cite_url():
    assert params(build_cite_url("o93zfHYlUTIJ")) == {
        "q": "info:o93zfHYlUTIJ:scholar.google.com/",
        "output": "cite",
        "scirp": "0",
        "hl": "en",
    }


@pytest.mark.parametrize(
    "value",
    [
        "JicYPdAAAAAJ",
        " JicYPdAAAAAJ ",
        "https://scholar.google.com/citations?user=JicYPdAAAAAJ&hl=en",
        "https://scholar.google.com/citations?hl=en&user=JicYPdAAAAAJ&view_op=list_works",
    ],
)
def test_parse_author_id(value):
    assert parse_author_id(value) == "JicYPdAAAAAJ"


@pytest.mark.parametrize("value", ["", "hinton", "https://scholar.google.com/citations?hl=en"])
def test_parse_author_id_rejects(value):
    with pytest.raises(ValueError):
        parse_author_id(value)


def test_parse_cites_and_result_ids():
    assert parse_cites_id(" 123, 456 ") == "123,456"
    with pytest.raises(ValueError):
        parse_cites_id("o93zfHYlUTIJ")
    assert parse_result_id("_QKtdPuIcqkJ") == "_QKtdPuIcqkJ"
    with pytest.raises(ValueError):
        parse_result_id("3625720365842685347")


def test_absolute_url_and_query_param():
    assert absolute_url("/scholar?cites=1") == "https://scholar.google.com/scholar?cites=1"
    assert absolute_url("https://arxiv.org/pdf/1") == "https://arxiv.org/pdf/1"
    assert absolute_url("javascript:void(0)") is None
    assert absolute_url(None) is None
    assert query_param("https://x.org/?a=1&b=2", "b") == "2"
    assert query_param("https://x.org/?a=1", "b") is None
