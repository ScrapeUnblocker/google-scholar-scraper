from __future__ import annotations

import csv
import json

import pytest

from google_scholar_scraper import (
    Article,
    AuthorArticle,
    AuthorProfile,
    AuthorRef,
    Citation,
    ScholarBlockedError,
    ScholarNotFoundError,
    cli,
)
from google_scholar_scraper.models import ResultsPage


def parse(*argv):
    args = cli.build_parser().parse_args(list(argv))
    cli.validate(args)
    return args


def test_search_defaults():
    args = parse("search", "large language models")
    assert args.command == "search"
    assert args.queries == ["large language models"]
    assert args.limit == 10
    assert args.sort == "relevance"
    assert args.include_citations is True
    assert args.year_from is None and args.year_to is None
    assert args.format == "json" and args.output is None
    assert args.proxy_country == "US" and args.retries == 3


def test_search_all_flags():
    args = parse(
        "search", "crispr", "prime editing",
        "-n", "30", "--from", "2020", "--to", "2024", "--sort", "date",
        "--no-citations", "--lang", "en", "-f", "csv", "-o", "out.csv",
        "--proxy-country", "GB", "--retries", "5", "-q", "--pretty",
    )  # fmt: skip
    assert args.queries == ["crispr", "prime editing"]
    assert (args.limit, args.year_from, args.year_to) == (30, 2020, 2024)
    assert args.sort == "date" and args.include_citations is False and args.language == "en"
    assert (args.format, args.output, args.proxy_country) == ("csv", "out.csv", "GB")
    assert args.retries == 5 and args.quiet and args.pretty


def test_other_commands_normalize_ids():
    assert parse("cited-by", "https://scholar.google.com/scholar?cites=42&hl=en").cites_id == "42"
    author = parse("author", "https://scholar.google.com/citations?user=JicYPdAAAAAJ&hl=en")
    assert author.author_id == "JicYPdAAAAAJ"
    assert (author.max_articles, author.sort) == (100, "citations")
    cite = parse("cite", "o93zfHYlUTIJ", "msVvatpT9iUJ", "--bibtex")
    assert cite.result_ids == ["o93zfHYlUTIJ", "msVvatpT9iUJ"] and cite.bibtex


@pytest.mark.parametrize(
    "argv",
    [
        [],
        ["search"],
        ["search", "x", "--format", "csv"],
        ["search", "x", "--limit", "0"],
        ["search", "x", "--from", "2024", "--to", "2020"],
        ["search", "x", "--lang", "english"],
        ["search", "x", "--sort", "citations"],
        ["search", "x", "--retries", "-1"],
        ["cited-by", "not-an-id"],
        ["author", "geoffrey hinton"],
        ["author", "JicYPdAAAAAJ", "--max-articles", "-5"],
        ["cite", "3625720365842685347"],
    ],
)
def test_invalid_arguments_exit_2(argv, capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(argv)
    assert exc.value.code == 2


class FakeScraper:
    """Stands in for ScholarScraper inside cli.main (no network)."""

    instances: list[FakeScraper] = []
    error: BaseException | None = None

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.calls: list[tuple] = []
        FakeScraper.instances.append(self)

    def _maybe_fail(self):
        if FakeScraper.error is not None:
            raise FakeScraper.error

    def search(self, query, *, limit, seen, on_page, **filters):
        self._maybe_fail()
        self.calls.append(("search", query, limit, filters))
        if on_page:
            on_page(ResultsPage(articles=[], total_results=1200, start=0))
        article = Article(
            position=1,
            result_id=query.replace(" ", "_")[:12].ljust(12, "x"),
            title=f"About {query}",
            authors=[AuthorRef("Y Chang", "Hw-lrpAAAAAJ"), AuthorRef("J Wang")],
            year=2024,
            cited_by_count=7,
            query=query,
        )
        if article.result_id in seen:
            return []
        seen.add(article.result_id)
        return [article]

    def cited_by(self, cites_id, *, limit, on_page, **filters):
        self._maybe_fail()
        self.calls.append(("cited_by", cites_id, limit, filters))
        return [Article(position=1, result_id="citingaaaaaa", title="Citing paper")]

    def author(self, author_id, *, max_articles, sort, on_page):
        self._maybe_fail()
        self.calls.append(("author", author_id, max_articles, sort))
        profile = AuthorProfile(
            author_id=author_id,
            name="Geoffrey Hinton",
            h_index=195,
            citations_per_year={2024: 10, 2025: 12},
            articles=[AuthorArticle(title="Deep learning", year=2015, cited_by_count=120642)],
        )
        if on_page:
            on_page(profile)
        return profile

    def cite(self, result_id, *, bibtex):
        self._maybe_fail()
        self.calls.append(("cite", result_id, bibtex))
        return Citation(
            result_id=result_id,
            formats={"MLA": "Chang, Yupeng, et al.", "APA": "Chang, Y. (2024)."},
            bibtex="@article{x}" if bibtex else None,
        )


@pytest.fixture
def fake(monkeypatch):
    FakeScraper.instances = []
    FakeScraper.error = None
    monkeypatch.setattr(cli, "ScholarScraper", FakeScraper)
    return FakeScraper


def test_main_search_json_to_stdout(fake, capsys):
    code = cli.main(["search", "llm evaluation", "llm agents", "--from", "2023", "--pretty"])
    assert code == 0
    out, err = capsys.readouterr()
    data = json.loads(out)
    assert [d["title"] for d in data] == ["About llm evaluation", "About llm agents"]
    assert data[0]["authors"][0] == {
        "name": "Y Chang",
        "author_id": "Hw-lrpAAAAAJ",
        "url": None,
    }
    scraper = fake.instances[0]
    assert scraper.kwargs["proxy_country"] == "US" and scraper.kwargs["retries"] == 3
    assert scraper.calls[0][3]["year_from"] == 2023
    assert '[scholar] "llm evaluation" page 1: 0 results (about 1,200)' in err


def test_main_search_csv(fake, tmp_path, capsys):
    path = tmp_path / "papers.csv"
    assert cli.main(["search", "llm", "-f", "csv", "-o", str(path), "-q"]) == 0
    with open(path, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert rows[0]["title"] == "About llm"
    assert rows[0]["authors"] == "Y Chang; J Wang"
    assert rows[0]["author_ids"] == "Hw-lrpAAAAAJ; "
    assert "Wrote 1 articles" in capsys.readouterr().err


def test_main_cited_by_and_cite(fake, tmp_path, capsys):
    assert cli.main(["cited-by", "3625720365842685347", "-n", "25", "-q"]) == 0
    assert json.loads(capsys.readouterr().out)[0]["title"] == "Citing paper"
    assert fake.instances[0].calls[0][:3] == ("cited_by", "3625720365842685347", 25)

    path = tmp_path / "cite.csv"
    assert cli.main(["cite", "o93zfHYlUTIJ", "--bibtex", "-f", "csv", "-o", str(path)]) == 0
    with open(path, encoding="utf-8-sig", newline="") as fh:
        row = next(csv.DictReader(fh))
    assert row["MLA"] == "Chang, Yupeng, et al." and row["bibtex"] == "@article{x}"
    assert "cite o93zfHYlUTIJ: 2 styles + BibTeX" in capsys.readouterr().err


def test_main_author_json_and_csv(fake, tmp_path, capsys):
    assert cli.main(["author", "JicYPdAAAAAJ", "-m", "0", "-s", "year"]) == 0
    out, err = capsys.readouterr()
    profile = json.loads(out)
    assert profile["name"] == "Geoffrey Hinton" and profile["h_index"] == 195
    assert profile["citations_per_year"] == {"2024": 10, "2025": 12}
    assert fake.instances[0].calls[0] == ("author", "JicYPdAAAAAJ", 0, "year")
    assert "author JicYPdAAAAAJ (Geoffrey Hinton)" in err

    path = tmp_path / "hinton.csv"
    assert cli.main(["author", "JicYPdAAAAAJ", "-f", "csv", "-o", str(path), "-q"]) == 0
    with open(path, encoding="utf-8-sig", newline="") as fh:
        row = next(csv.DictReader(fh))
    assert row["author_name"] == "Geoffrey Hinton" and row["title"] == "Deep learning"


def test_main_reports_errors(fake, capsys):
    fake.error = ScholarNotFoundError("no public Google Scholar profile for author ID AAAAAAAAAAAA")
    assert cli.main(["author", "AAAAAAAAAAAA"]) == 1
    assert "no public Google Scholar profile" in capsys.readouterr().err

    fake.error = ScholarBlockedError("Google Scholar answered with a CAPTCHA page")
    assert cli.main(["search", "x"]) == 1
    assert "raise --retries" in capsys.readouterr().err
