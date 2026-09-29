from __future__ import annotations

import pytest
from bs4 import BeautifulSoup
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
    ScholarBlockedError,
    ScholarNotFoundError,
    ScholarParseError,
    clean_text,
    parse_author_page,
    parse_cite_page,
    parse_results_page,
    split_publication_info,
)
from google_scholar_scraper.parsing import parse_bibtex, parse_int, parse_total

ELLIPSIS = "…"


def text_of(html: str) -> str | None:
    return clean_text(BeautifulSoup(prettify(f"<div>{html}</div>"), "html.parser").div)


# --------------------------------------------------------------------------- #
# Text helpers
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        (
            "A survey on <b>large language models</b>: a review",
            "A survey on large language models: a review",
        ),
        ("Omics-Nano-<b>CRISPR</b> Strategies", "Omics-Nano-CRISPR Strategies"),
        ("<b>Genome</b>-wide <b>CRISPR</b>-<b>Cas9</b> screens", "Genome-wide CRISPR-Cas9 screens"),
        ("the term “<b>large language model</b>” is", "the term “large language model” is"),
        ("<i>Journal</i>, <i>15</i>(3), 1-45.", "Journal, 15(3), 1-45."),
        (
            "<i>arXiv preprint arXiv:2310.19736</i> (2023).",
            "arXiv preprint arXiv:2310.19736 (2023).",
        ),
        ("J Smith&nbsp;- Nature, 2020 - nature.com", "J Smith - Nature, 2020 - nature.com"),
        ("line one<br/>line two", "line one line two"),
        ("<script>var x = 1;</script>visible", "visible"),
    ],
)
def test_clean_text_rejoins_prettified_html(html, expected):
    assert text_of(html) == expected


def test_clean_text_empty():
    assert clean_text(None) is None
    assert text_of("   ") is None


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Cited by 6818", 6818),
        ("Cited by 1,234", 1234),
        ("All 11 versions", 11),
        ("nothing here", None),
        (None, None),
    ],
)
def test_parse_int(text, expected):
    assert parse_int(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("About 6,500,000 results (0.10 sec)", 6_500_000),
        ("Page 2 of about 6,500,000 results (0.08 sec)", 6_500_000),
        ("1 result (0.01 sec)", 1),
        ("", None),
    ],
)
def test_parse_total(text, expected):
    assert parse_total(text) == expected


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        (
            f"Y Chang, X Wang {ELLIPSIS} - ACM transactions on {ELLIPSIS}, 2024 - dl.acm.org",
            (f"Y Chang, X Wang {ELLIPSIS}", f"ACM transactions on {ELLIPSIS}", 2024, "dl.acm.org"),
        ),
        ("DE Knuth - 2013 - books.google.com", ("DE Knuth", None, 2013, "books.google.com")),
        ("AL SEGATO - thesis.unipd.it", ("AL SEGATO", None, None, "thesis.unipd.it")),
        (
            "J Doe - Proceedings - Part II, 2019 - Springer",
            ("J Doe", "Proceedings - Part II", 2019, "Springer"),
        ),
        ("J Doe - Some Journal - example.org", ("J Doe", "Some Journal", None, "example.org")),
        ("J Doe - 2020", ("J Doe", None, 2020, None)),
        (None, (None, None, None, None)),
    ],
)
def test_split_publication_info(line, expected):
    assert split_publication_info(line) == expected


# --------------------------------------------------------------------------- #
# Results pages
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("pretty", [False, True])
def test_parse_results_page_full_result(pretty):
    html = results_page([result_block(), result_block("msVvatpT9iUJ", cited_by=None)])
    page = parse_results_page(prettify(html) if pretty else html, url="u", start=10)
    assert page.total_results == 6_500_000
    assert page.has_next is True
    assert page.start == 10 and page.url == "u"
    assert len(page.articles) == 2

    first = page.articles[0]
    assert first.position == 11
    assert first.result_id == "o93zfHYlUTIJ"
    assert first.title == "A survey on evaluation of large language models"
    assert first.url == "https://dl.acm.org/doi/abs/10.1145/3641289"
    assert first.doc_type is None
    assert [(a.name, a.author_id) for a in first.authors] == [
        ("Y Chang", "Hw-lrpAAAAAJ"),
        ("X Wang", "Q7Ieos8AAAAJ"),
        ("J Wang", None),
    ]
    assert first.authors[0].url == "https://scholar.google.com/citations?user=Hw-lrpAAAAAJ&hl=en"
    assert first.venue == f"ACM transactions on {ELLIPSIS}"
    assert first.year == 2024
    assert first.source == "dl.acm.org"
    assert (
        first.snippet == f"{ELLIPSIS} the development of language models, particularly {ELLIPSIS}"
    )
    assert first.added_ago is None
    assert first.cited_by_count == 6818
    assert first.cites_id == "3625720365842685347"
    assert first.cited_by_url.startswith("https://scholar.google.com/scholar?cites=")
    assert first.versions_count == 11
    assert first.cluster_id == "3625720365842685347"
    assert first.related_url.startswith("https://scholar.google.com/scholar?q=related:")
    assert first.full_text_type == "PDF"
    assert first.full_text_source == "acm.org"
    assert first.full_text_url == "https://dl.acm.org/doi/pdf/10.1145/3641289"

    second = page.articles[1]
    assert second.position == 12
    assert second.cited_by_count is None and second.cites_id is None


def test_parse_result_doc_types_and_citation_only_entries():
    html = results_page(
        [
            result_block("aaaaaaaaaaaa", doc_type="HTML", title="Open paper"),
            result_block("bbbbbbbbbbbb", doc_type="BOOK", title="A book", full_text=None),
            result_block(
                "cccccccccccc", doc_type="CITATION", title="Cited only", href=None, full_text=None
            ),
        ]
    )
    html_result, book, citation = parse_results_page(prettify(html)).articles
    assert (html_result.doc_type, html_result.title) == ("HTML", "Open paper")
    assert (book.doc_type, book.title, book.full_text_url) == ("BOOK", "A book", None)
    assert (citation.doc_type, citation.title, citation.url) == ("CITATION", "Cited only", None)
    assert citation.result_id == "cccccccccccc"


def test_parse_result_added_ago_from_sort_by_date():
    block = result_block(snippet="3 days ago - &hellip; we synthesize current strategies &hellip;")
    article = parse_results_page(results_page([block])).articles[0]
    assert article.added_ago == "3 days ago"
    assert article.snippet == f"{ELLIPSIS} we synthesize current strategies {ELLIPSIS}"


def test_parse_results_last_page_and_no_results():
    last = parse_results_page(results_page([result_block()], next_start=None))
    assert last.has_next is False

    empty = parse_results_page(
        results_page([], header=None, next_start=None, suggestion="large language models")
    )
    assert empty.articles == []
    assert empty.total_results is None
    assert empty.has_next is False
    assert empty.suggestion == "large language models"


def test_parse_results_page_detects_captcha_and_wrong_pages():
    with pytest.raises(ScholarBlockedError):
        parse_results_page(prettify(CAPTCHA_HTML))
    with pytest.raises(ScholarParseError):
        parse_results_page("<html><body><p>Something else</p></body></html>")
    assert issubclass(ScholarBlockedError, ScholarParseError)


# --------------------------------------------------------------------------- #
# Author profiles
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("pretty", [False, True])
def test_parse_author_page(pretty):
    html = author_page(
        [
            author_row(),
            author_row(
                "Imagenet classification with deep convolutional neural networks",
                citation_id="JicYPdAAAAAJ:VN7nJs4JPk0C",
                cites="2071317309766942398,1036029811429977192",
                cited=200585,
                year=2012,
            ),
            author_row("Unpublished note", citation_id="JicYPdAAAAAJ:zzz", cited=None, year=None),
        ],
        has_more=True,
    )
    profile = parse_author_page(prettify(html) if pretty else html, author_id="JicYPdAAAAAJ")
    assert profile.name == "Geoffrey Hinton"
    assert profile.affiliation == "Emeritus Prof. Computer Science, University of Toronto"
    assert profile.organization == "University of Toronto"
    assert profile.organization_id == "8515235176732148308"
    assert profile.email_domain == "cs.toronto.edu"
    assert profile.homepage == "http://www.cs.toronto.edu/~hinton"
    assert profile.interests == ["machine learning", "psychology"]
    assert profile.photo_url.startswith("https://scholar.googleusercontent.com/citations?")
    assert (profile.citations, profile.citations_recent) == (1091581, 626413)
    assert (profile.h_index, profile.h_index_recent) == (195, 134)
    assert (profile.i10_index, profile.i10_index_recent) == (549, 403)
    assert profile.recent_since == 2021
    # 2024 has no bar in the chart -> 0 citations that year.
    assert profile.citations_per_year == {2023: 110325, 2024: 0, 2025: 119114}
    assert [(c.name, c.author_id, c.affiliation) for c in profile.co_authors] == [
        ("Terrence Sejnowski", "m1qAiOUAAAAJ", "Salk Institute")
    ]
    assert profile.url == "https://scholar.google.com/citations?user=JicYPdAAAAAJ&hl=en"
    assert profile.has_more_articles is True

    deep, imagenet, note = profile.articles
    assert deep.title == "Deep learning"
    assert deep.citation_id == "JicYPdAAAAAJ:C-SEpTPhZ1wC"
    assert deep.authors == "Y LeCun, Y Bengio, G Hinton"
    assert deep.publication == "Nature 521 (7553), 436-444"
    assert (deep.year, deep.cited_by_count, deep.cites_id) == (2015, 120642, "5362332738201102290")
    assert deep.url.startswith("https://scholar.google.com/citations?view_op=view_citation")
    assert imagenet.cites_id == "2071317309766942398,1036029811429977192"
    assert (note.cited_by_count, note.cites_id, note.year) == (None, None, None)


def test_parse_author_page_last_page_and_default_avatar():
    html = author_page(has_more=False).replace(
        "https://scholar.googleusercontent.com/citations?view_op=view_photo&amp;user=JicYPdAAAAAJ"
        "&amp;citpid=2",
        "/citations/images/avatar_scholar_128.png",
    )
    profile = parse_author_page(html, author_id="JicYPdAAAAAJ")
    assert profile.has_more_articles is False
    assert profile.photo_url is None


def test_parse_author_page_errors():
    with pytest.raises(ScholarNotFoundError):
        parse_author_page(prettify(SIGN_IN_HTML), author_id="AAAAAAAAAAAA")
    with pytest.raises(ScholarBlockedError):
        parse_author_page(CAPTCHA_HTML, author_id="JicYPdAAAAAJ")
    with pytest.raises(ScholarParseError):
        parse_author_page(results_page([]), author_id="JicYPdAAAAAJ")


# --------------------------------------------------------------------------- #
# "Cite" dialog and BibTeX
# --------------------------------------------------------------------------- #


def test_parse_cite_page():
    citation = parse_cite_page(prettify(CITE_HTML), result_id="o93zfHYlUTIJ")
    assert citation.result_id == "o93zfHYlUTIJ"
    assert citation.formats == {
        "MLA": 'Chang, Yupeng, et al. "A survey on evaluation of large language models." '
        "ACM transactions on intelligent systems and technology 15.3 (2024): 1-45.",
        "APA": "Chang, Y., Wang, X. (2024). A survey on evaluation of large language models. "
        "ACM transactions on intelligent systems and technology, 15(3), 1-45.",
    }
    assert citation.bibtex_url == BIBTEX_URL
    assert citation.endnote_url == "https://scholar.googleusercontent.com/scholar.enw?q=x"
    assert citation.refman_url is None
    with pytest.raises(ScholarParseError):
        parse_cite_page("<html><body></body></html>", result_id="o93zfHYlUTIJ")


def test_parse_bibtex():
    assert parse_bibtex(BIBTEX) == BIBTEX
    assert parse_bibtex(f"<html><body><pre>{BIBTEX}</pre></body></html>") == BIBTEX
    assert parse_bibtex("<html><body>nope</body></html>") is None
    assert parse_bibtex("") is None
