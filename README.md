# google-scholar-scraper

[![CI](https://github.com/ScrapeUnblocker/google-scholar-scraper/actions/workflows/ci.yml/badge.svg)](https://github.com/ScrapeUnblocker/google-scholar-scraper/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**Scrape Google Scholar into clean, typed JSON or CSV: search results, "Cited by" lists, author profiles with h-index and citation metrics, and ready-made MLA / APA / BibTeX citations.**

Search Google Scholar for any topic and get one clean record per paper: title,
result ID, document type, authors **with their Scholar profile IDs**, venue,
year, source, snippet, full-text PDF / HTML link, "Cited by" count and number of
versions. Follow any paper's "Cited by" list, pull a researcher's full profile
(affiliation, interests, citations / h-index / i10-index, citations per year,
co-authors and every publication), and turn any result into formatted MLA,
APA, Chicago, Harvard and Vancouver references or a BibTeX entry.

> **Powered by [ScrapeUnblocker](https://scrapeunblocker.com/?utm_source=github&utm_medium=integration&utm_campaign=example-repos).**
> Every Scholar page is loaded in a real browser through the
> [`getPageSource` API](https://docs.scrapeunblocker.com/?utm_source=github&utm_medium=integration&utm_campaign=example-repos)
> and parsed locally into typed records. Scholar's CAPTCHA pages are detected
> and retried automatically.

## Features

- 🔎 **Search with Scholar's own filters**: publication year range, sort by
  relevance or date (recently added first), include / exclude citation-only
  entries, restrict to one language. Scholar operators work in the query
  (`author:"hinton"`, `source:nature`, `intitle:transformer`, `"exact phrase"`).
- 📑 **Rich, typed results**: `year` and `cited_by_count` are integers, the grey
  publication line is split into `venue`, `year` and `source`, and every author
  that has a Scholar profile comes with an `author_id` you can feed straight
  into `author`.
- 📈 **Citation graph**: every result carries a `cites_id`; `cited-by` lists the
  papers citing it, with the same filters (for example "who cited this paper
  since 2025, newest first").
- 👩‍🔬 **Author profiles**: name, affiliation, organization, verified email
  domain, homepage, interests, photo, citations / h-index / i10-index (all time
  and recent), citations per year, co-authors and all publications (100 per
  request, with citation counts and years).
- 📚 **Citations and BibTeX**: MLA, APA, Chicago, Harvard and Vancouver
  references, BibTeX / EndNote / RefMan / RefWorks export links, and
  optionally the BibTeX entry itself.
- 📄 **Many pages, many queries**: collect hundreds of results per search (10 per
  request) and merge several searches, de-duplicated by Scholar result ID.
- 🔁 **Resilient**: CAPTCHA pages, timeouts and transient API errors are
  retried with doubling backoff.
- 🖥️ **CLI + library**: use `google-scholar-scraper` from the shell or import it
  in Python. JSON or CSV (UTF-8, Excel-friendly) output.

## Install

```bash
pip install .
# or, for development:
pip install -e ".[dev]"
```

Set your ScrapeUnblocker API key (grab one from your
[dashboard](https://scrapeunblocker.com/?utm_source=github&utm_medium=integration&utm_campaign=example-repos)):

```bash
cp .env.example .env          # then edit it, or just export the variable:
export SCRAPEUNBLOCKER_KEY=your_key_here
```

## CLI usage

The CLI has four commands: `search`, `cited-by`, `author` and `cite`.

```bash
# Top 20 results for a topic, pretty-printed JSON to stdout
google-scholar-scraper search "large language models evaluation" --limit 20 --pretty

# A literature review: two queries, papers from 2022 onwards, no citation-only
# entries, merged and de-duplicated into one CSV
google-scholar-scraper search "crispr off-target effects" "prime editing" \
  --from 2022 --no-citations --limit 50 --format csv --output crispr.csv

# Newest papers citing a paper (cites_id comes from search output)
google-scholar-scraper cited-by 3625720365842685347 --sort date --limit 30

# A researcher's profile, metrics and 200 most cited publications
google-scholar-scraper author JicYPdAAAAAJ --max-articles 200 --output hinton.json

# ... or their publications as a spreadsheet, newest first
google-scholar-scraper author "https://scholar.google.com/citations?user=JicYPdAAAAAJ" \
  --sort year --format csv --output hinton_papers.csv

# Formatted references + BibTeX for two results (result_id from search output)
google-scholar-scraper cite o93zfHYlUTIJ QBZmFEFVMhUJ --bibtex --pretty
```

`python -m google_scholar_scraper ...` works too. Progress goes to stderr:

```
[scholar] "large language models evaluation" page 1: 10 results (about 196,000)
[scholar] "large language models evaluation" page 2: 10 results (about 196,000)
Wrote 20 articles to llm_eval.json
```

### `search` and `cited-by` options

| Option | Meaning |
| --- | --- |
| `QUERY ...` (search) | Search terms; several queries are merged and de-duplicated. |
| `CITES_ID` (cited-by) | A paper's `cites_id` (from search or author output) or its "Cited by" URL. |
| `-n, --limit` | Maximum number of articles (default 10; one request per 10). |
| `--from YEAR` / `--to YEAR` | Only papers published in this year range. |
| `-s, --sort` | `relevance` (default) or `date` (recently added papers first; fills `added_ago`). |
| `--no-citations` | Drop citation-only `[CITATION]` entries. |
| `--lang CODE` | Only papers in this language: `en`, `de`, `fr`, `zh-CN`, ... |

### `author` options

| Option | Meaning |
| --- | --- |
| `AUTHOR` | Author ID (`JicYPdAAAAAJ`, the `user=` value of a profile URL, or any `author_id` from search output) or a profile URL. |
| `-m, --max-articles` | Publications to collect (default 100; one request per 100). `0` gives the profile only. |
| `-s, --sort` | `citations` (most cited first, default) or `year` (newest first). |

CSV output for `author` lists the publications (one row each, with the
author's name and ID); JSON output has the full profile.

### `cite` options

| Option | Meaning |
| --- | --- |
| `RESULT_ID ...` | One or more `result_id` values from search or cited-by output. |
| `--bibtex` | Also download each BibTeX entry (one extra request per result). |

### Options for every command

| Option | Meaning |
| --- | --- |
| `-f, --format` | `json` (default) or `csv` (needs `--output`). |
| `-o, --output` | Write to this file instead of stdout. |
| `--pretty` | Indented JSON. |
| `--proxy-country` | Country to route requests through (default `US`). |
| `--retries` | Retries per page on CAPTCHAs and transient errors (default 3, doubling backoff). |
| `-q, --quiet` | No progress output on stderr. |

## Library usage

```python
from google_scholar_scraper import ScholarScraper, to_csv

scholar = ScholarScraper()  # reads SCRAPEUNBLOCKER_KEY (or pass api_key="...")

# Search, with filters
papers = scholar.search("graph neural networks drug discovery", limit=30, year_from=2021)
for paper in papers[:3]:
    print(paper.year, paper.title, paper.cited_by_count, paper.full_text_url)

# Several searches, merged and de-duplicated by result ID
review = scholar.search_many(
    ["retrieval augmented generation", "RAG evaluation"],
    limit_per_query=20,
    year_from=2023,
    include_citations=False,
)
to_csv(review, "rag_papers.csv")

# Who cites the top paper? (accepts an Article, a cites_id or a "Cited by" URL)
citing = scholar.cited_by(papers[0], sort="date", limit=20)

# The first author's full profile
author_id = next(a.author_id for a in papers[0].authors if a.author_id)
profile = scholar.author(author_id, max_articles=100)
print(profile.name, profile.h_index, profile.citations_per_year)

# Formatted references
citation = scholar.cite(papers[0], bibtex=True)
print(citation.formats["APA"])
print(citation.bibtex)
```

The parsers are usable on their own too: `parse_results_page(html)`,
`parse_author_page(html, author_id=...)` and `parse_cite_page(html, result_id=...)`
turn Scholar HTML into the same records, and `build_search_url(...)`,
`build_cited_by_url(...)` and `build_author_url(...)` build the URLs.

## Example output

One search result (`google-scholar-scraper search "large language models evaluation"`,
author list shortened):

```json
{
  "position": 1,
  "result_id": "o93zfHYlUTIJ",
  "title": "A survey on evaluation of large language models",
  "url": "https://dl.acm.org/doi/abs/10.1145/3641289",
  "doc_type": null,
  "authors": [
    {"name": "Y Chang", "author_id": "Hw-lrpAAAAAJ", "url": "https://scholar.google.com/citations?user=Hw-lrpAAAAAJ&hl=en"},
    {"name": "X Wang", "author_id": "Q7Ieos8AAAAJ", "url": "https://scholar.google.com/citations?user=Q7Ieos8AAAAJ&hl=en"}
  ],
  "publication_info": "Y Chang, X Wang, J Wang, Y Wu, L Yang … - ACM transactions on …, 2024 - dl.acm.org",
  "venue": "ACM transactions on …",
  "year": 2024,
  "source": "dl.acm.org",
  "snippet": "Large language models (LLMs) are gaining increasing … and daily use, their evaluation becomes increasingly critical, not … comprehensive review of these evaluation methods for LLMs…",
  "added_ago": null,
  "cited_by_count": 6818,
  "cites_id": "3625720365842685347",
  "cited_by_url": "https://scholar.google.com/scholar?cites=3625720365842685347&as_sdt=2005&sciodt=0,5&hl=en",
  "versions_count": 11,
  "cluster_id": "3625720365842685347",
  "versions_url": "https://scholar.google.com/scholar?cluster=3625720365842685347&hl=en&as_sdt=0,5&as_ylo=2023",
  "related_url": "https://scholar.google.com/scholar?q=related:o93zfHYlUTIJ:scholar.google.com/&scioq=large+language+models+evaluation&hl=en&as_sdt=0,5&as_ylo=2023",
  "full_text_url": "https://dl.acm.org/doi/pdf/10.1145/3641289",
  "full_text_type": "PDF",
  "full_text_source": "acm.org",
  "query": "large language models evaluation"
}
```

An author profile (`google-scholar-scraper author JicYPdAAAAAJ`, lists shortened):

```json
{
  "author_id": "JicYPdAAAAAJ",
  "name": "Geoffrey Hinton",
  "affiliation": "Emeritus Prof. Computer Science, University of Toronto",
  "organization": "University of Toronto",
  "organization_id": "8515235176732148308",
  "email_domain": "cs.toronto.edu",
  "homepage": "http://www.cs.toronto.edu/~hinton",
  "interests": ["machine learning", "psychology", "artificial intelligence", "cognitive science", "computer science"],
  "photo_url": "https://scholar.googleusercontent.com/citations?view_op=view_photo&user=JicYPdAAAAAJ&citpid=2",
  "citations": 1091581,
  "citations_recent": 626413,
  "h_index": 195,
  "h_index_recent": 134,
  "i10_index": 549,
  "i10_index_recent": 403,
  "recent_since": 2021,
  "citations_per_year": {"2024": 110325, "2025": 119114, "2026": 84651},
  "co_authors": [
    {"name": "Terrence Sejnowski", "author_id": "m1qAiOUAAAAJ", "affiliation": "Francis Crick Professor, Salk Institute, Distingished Professor, UC San Diego", "url": "https://scholar.google.com/citations?user=m1qAiOUAAAAJ&hl=en"}
  ],
  "articles": [
    {
      "title": "Imagenet classification with deep convolutional neural networks",
      "citation_id": "JicYPdAAAAAJ:VN7nJs4JPk0C",
      "url": "https://scholar.google.com/citations?view_op=view_citation&hl=en&user=JicYPdAAAAAJ&pagesize=100&citation_for_view=JicYPdAAAAAJ:VN7nJs4JPk0C",
      "authors": "A Krizhevsky, I Sutskever, GE Hinton",
      "publication": "Advances in neural information processing systems 25",
      "year": 2012,
      "cited_by_count": 200585,
      "cites_id": "2071317309766942398,1036029811429977192,13351982974043817797",
      "cited_by_url": "https://scholar.google.com/scholar?oi=bibs&hl=en&cites=2071317309766942398,1036029811429977192,13351982974043817797"
    }
  ],
  "has_more_articles": true,
  "url": "https://scholar.google.com/citations?user=JicYPdAAAAAJ&hl=en"
}
```

Citations (`google-scholar-scraper cite QBZmFEFVMhUJ --bibtex`, export links omitted):

```json
{
  "result_id": "QBZmFEFVMhUJ",
  "formats": {
    "MLA": "Guo, Zishan, et al. \"Evaluating large language models: A comprehensive survey.\" arXiv preprint arXiv:2310.19736 (2023).",
    "APA": "Guo, Z., Jin, R., Liu, C., Huang, Y., Shi, D., Yu, L., ... & Xiong, D. (2023). Evaluating large language models: A comprehensive survey. arXiv preprint arXiv:2310.19736.",
    "Chicago": "Guo, Zishan, Renren Jin, Chuang Liu, Yufei Huang, Dan Shi, Linhao Yu, Yan Liu, Jiaxuan Li, Bojian Xiong, and Deyi Xiong. \"Evaluating large language models: A comprehensive survey.\" arXiv preprint arXiv:2310.19736 (2023).",
    "Harvard": "Guo, Z., Jin, R., Liu, C., Huang, Y., Shi, D., Yu, L., Liu, Y., Li, J., Xiong, B. and Xiong, D., 2023. Evaluating large language models: A comprehensive survey. arXiv preprint arXiv:2310.19736.",
    "Vancouver": "Guo Z, Jin R, Liu C, Huang Y, Shi D, Yu L, Liu Y, Li J, Xiong B, Xiong D. Evaluating large language models: A comprehensive survey. arXiv preprint arXiv:2310.19736. 2023 Oct 30."
  },
  "bibtex": "@article{guo2023evaluating,\n  title={Evaluating large language models: A comprehensive survey},\n  author={Guo, Zishan and Jin, Renren and Liu, Chuang and Huang, Yufei and Shi, Dan and Yu, Linhao and Liu, Yan and Li, Jiaxuan and Xiong, Bojian and Xiong, Deyi and others},\n  journal={arXiv preprint arXiv:2310.19736},\n  year={2023}\n}"
}
```

## Good to know

- **10 results per request.** Scholar lists 10 results per page and stops
  paging at 1,000 results per search. For more, split the topic into several
  queries or year ranges; `search_many` / several CLI queries merge them.
- **Author IDs, not names.** Scholar's author-name search requires a Google
  sign-in, so profiles are addressed by ID. Every linked author in search
  results carries its `author_id`, and profile URLs work too. A profile that
  does not exist (or is not public) raises `ScholarNotFoundError`.
- **Scholar truncates.** Long author lists and venue names end in "…" exactly
  as Scholar prints them; the author profile and `cite` give the full forms.
- **Estimates.** `total_results` / "about N results" is Scholar's own estimate.
- **English labels.** Keep `hl="en"` (the default): the result count,
  `added_ago` and the verified-email domain are read from English text.
- **CAPTCHAs.** Scholar sometimes answers automated traffic with a CAPTCHA
  page. It is detected and retried with doubling backoff; if a run still fails,
  wait a few minutes or raise `--retries`.

## Project layout

```
google-scholar-scraper/
├── src/google_scholar_scraper/
│   ├── __init__.py      # public API + __version__
│   ├── scraper.py       # ScholarScraper: fetching, retries, pagination, dedupe
│   ├── parsing.py       # Scholar HTML -> typed records, CAPTCHA detection
│   ├── urls.py          # URL builders + ID validation
│   ├── models.py        # Article, AuthorProfile, Citation, ... dataclasses
│   ├── export.py        # JSON / CSV export
│   ├── cli.py           # `google-scholar-scraper` command
│   └── __main__.py      # `python -m google_scholar_scraper`
├── examples/
│   ├── search_to_json.py
│   ├── literature_review_csv.py
│   └── author_report.py
├── tests/               # offline tests, SDK mocked (no API credit used)
├── pyproject.toml
├── requirements.txt
├── Makefile
└── .env.example
```

## Development

```bash
make install   # pip install -e ".[dev]"
make lint      # ruff check .
make format    # ruff format .
make test      # pytest -q (offline: the ScrapeUnblocker client is mocked)
make run       # python examples/search_to_json.py (needs SCRAPEUNBLOCKER_KEY)
```

The tests run the parsers on synthetic Scholar pages, both compact and
prettified the way the `getPageSource` API returns them, and cover retries,
pagination, de-duplication, the CLI and CSV export.

## Links

- [ScrapeUnblocker](https://scrapeunblocker.com/?utm_source=github&utm_medium=integration&utm_campaign=example-repos): web scraping API that loads pages in a real browser
- [ScrapeUnblocker documentation](https://docs.scrapeunblocker.com/?utm_source=github&utm_medium=integration&utm_campaign=example-repos): `getPageSource`, SDKs and more

This project is not affiliated with or endorsed by Google. Please use it
responsibly and in line with the terms of the sites you access.

## License

[MIT](LICENSE) © ScrapeUnblocker
