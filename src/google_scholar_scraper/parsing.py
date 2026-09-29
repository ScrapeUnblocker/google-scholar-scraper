"""Parse Google Scholar pages into typed records.

The parsers take the HTML returned by the ScrapeUnblocker ``getPageSource`` API
and read Scholar's stable result markup (``gs_r`` result blocks, ``gs_a``
publication lines, ``gsc_*`` profile tables). The API returns *prettified*
HTML, which puts every text node on its own line; :func:`clean_text` stitches
the pieces back together so "Omics-Nano-<b>CRISPR</b>" reads "Omics-Nano-CRISPR"
and not "Omics-Nano- CRISPR".
"""

from __future__ import annotations

import re
from typing import Any

from bs4 import BeautifulSoup, Comment, NavigableString, Tag

from .models import (
    Article,
    AuthorArticle,
    AuthorProfile,
    AuthorRef,
    Citation,
    CoAuthor,
    ResultsPage,
)
from .urls import BASE_URL, absolute_url, author_profile_url, query_param


class ScholarError(RuntimeError):
    """Base class for google-scholar-scraper errors."""


class ScholarParseError(ScholarError):
    """The page is not the Scholar page we asked for (e.g. an interstitial).

    Retried automatically. If it persists, Scholar may have changed its layout.
    """


class ScholarBlockedError(ScholarParseError):
    """Scholar answered with its "unusual traffic" CAPTCHA page.

    Retried automatically with backoff, like any other transient failure.
    """


class ScholarNotFoundError(ScholarError):
    """The author profile does not exist or is not public (not retried)."""


_CAPTCHA_RE = re.compile(
    r'id="captcha-form"|class="g-recaptcha"|id="gs_captcha|/sorry/index'
    r"|unusual traffic from your computer network",
    re.I,
)
_SIGN_IN_RE = re.compile(r"to continue to Google Scholar", re.I)

_NUMBER_RE = re.compile(r"\d[\d,.\u00a0\u202f ]*")
_TOTAL_RE = re.compile(r"(\d[\d,.\u00a0\u202f]*)\s*results?\b", re.I)
_YEAR_RE = re.compile(r"^(?:(?P<venue>.*?),\s*)?(?P<year>\d{4})$")
_ADDED_AGO_RE = re.compile(r"^(?P<ago>\d+\s+\w+\s+ago)\s+-\s+")
_EMAIL_RE = re.compile(r"Verified email at\s+(\S+?)(?:\s+-|$)")
_RIGHT_PX_RE = re.compile(r"right:\s*(-?\d+)px")
_ISSUE_RE = re.compile(r"\(\d{1,3}\)")
_SEPARATOR_RE = re.compile(r"\s+-\s+")

_SKIP_PARENTS = {"script", "style", "noscript", "template"}
_NO_SPACE_BEFORE = (*",.;:!?)]}%", "\u201d", "\u2019")
_NO_SPACE_AFTER = (*"([{", "\u201c", "\u2018")


# --------------------------------------------------------------------------- #
# Text helpers
# --------------------------------------------------------------------------- #


def _chunks(node: Any) -> list[str]:
    if isinstance(node, NavigableString):
        strings = [node]
    elif isinstance(node, Tag):
        strings = node.find_all(string=True)
    else:
        return []
    out = []
    for s in strings:
        if isinstance(s, Comment) or (s.parent is not None and s.parent.name in _SKIP_PARENTS):
            continue
        text = " ".join(str(s).replace("\xa0", " ").split())
        if text:
            out.append(text)
    return out


def _join(chunks: list[str]) -> str:
    out = ""
    for chunk in chunks:
        if not out:
            out = chunk
            continue
        glue = (
            chunk.startswith(_NO_SPACE_BEFORE)
            or out.endswith(_NO_SPACE_AFTER)
            # "Omics-Nano-" + "CRISPR" / "Genome" + "-wide": a hyphenated word
            # split by a <b> tag around the search terms
            or (out.endswith("-") and len(out) > 1 and out[-2].isalnum())
            or (
                chunk.startswith("-")
                and out[-1].isalnum()
                and (len(chunk) == 1 or chunk[1].isalnum())
            )
            # "15" + "(3), 1-45." (volume + issue in a formatted citation), but not
            # "arXiv:2310.19736" + "(2023)." (a year keeps its space)
            or (out[-1].isdigit() and _ISSUE_RE.match(chunk) is not None)
            or chunk.startswith(("'s ", "\u2019s "))
            or chunk in ("'s", "\u2019s")
        )
        out += chunk if glue else " " + chunk
    return out


def clean_text(node: Any) -> str | None:
    """Readable text of an element (or string); ``None`` when empty.

    Whitespace is collapsed and non-breaking spaces become plain spaces.
    """
    if node is None:
        return None
    text = _join(_chunks(node))
    return text or None


def parse_int(text: str | None) -> int | None:
    """First integer in ``text`` ("Cited by 1,234" -> 1234); ``None`` if none."""
    if not text:
        return None
    match = _NUMBER_RE.search(text)
    if not match:
        return None
    digits = re.sub(r"\D", "", match.group(0))
    return int(digits) if digits else None


def parse_total(text: str | None) -> int | None:
    """Result count from Scholar's header ("Page 2 of about 6,500,000 results")."""
    if not text:
        return None
    match = _TOTAL_RE.search(text)
    if match:
        return parse_int(match.group(1))
    numbers = [n for n in (parse_int(m.group(0)) for m in _NUMBER_RE.finditer(text)) if n]
    return max(numbers) if numbers else None


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html or "", "html.parser")


def check_page(html: str) -> None:
    """Raise :class:`ScholarBlockedError` when ``html`` is Scholar's CAPTCHA page."""
    if _CAPTCHA_RE.search(html or ""):
        raise ScholarBlockedError("Google Scholar answered with a CAPTCHA page")


# --------------------------------------------------------------------------- #
# Search results / "Cited by" lists
# --------------------------------------------------------------------------- #


def split_publication_info(
    text: str | None,
) -> tuple[str | None, str | None, int | None, str | None]:
    """Split Scholar's grey publication line into its parts.

    ``"Y Chang, X Wang … - ACM transactions on …, 2024 - dl.acm.org"`` becomes
    ``("Y Chang, X Wang …", "ACM transactions on …", 2024, "dl.acm.org")``.

    Returns:
        ``(authors, venue, year, source)``; missing parts are ``None``.
    """
    if not text:
        return None, None, None, None
    parts = [p.strip() for p in _SEPARATOR_RE.split(text.strip()) if p.strip()]
    if not parts:
        return None, None, None, None
    authors = parts[0]
    middle: str | None = None
    source: str | None = None
    if len(parts) >= 3:
        middle, source = " - ".join(parts[1:-1]), parts[-1]
    elif len(parts) == 2:
        if _YEAR_RE.match(parts[1]):
            middle = parts[1]
        else:
            source = parts[1]
    venue: str | None = None
    year: int | None = None
    if middle:
        match = _YEAR_RE.match(middle)
        if match and 1000 <= int(match.group("year")) <= 2100:
            venue = match.group("venue") or None
            year = int(match.group("year"))
        else:
            venue = middle
    return authors, venue, year, source


def _authors(gs_a: Tag | None, authors_text: str | None) -> list[AuthorRef]:
    if not authors_text:
        return []
    ids: dict[str, str] = {}
    if gs_a is not None:
        for link in gs_a.select('a[href*="user="]'):
            name = clean_text(link)
            author_id = query_param(absolute_url(link.get("href")), "user")
            if name and author_id:
                ids.setdefault(name, author_id)
    refs = []
    for raw in authors_text.split(","):
        name = raw.strip().strip("\u2026").strip()
        if not name:
            continue
        author_id = ids.get(name)
        refs.append(
            AuthorRef(
                name=name,
                author_id=author_id,
                url=author_profile_url(author_id) if author_id else None,
            )
        )
    return refs


def _doc_type(label: str | None) -> str | None:
    if not label:
        return None
    label = label.strip().strip("[]").strip()
    return label.upper() or None


def parse_result(block: Tag, *, position: int | None = None) -> Article:
    """Parse one ``div.gs_r`` search-result block."""
    article = Article(position=position, result_id=block.get("data-cid") or None)

    title_el = block.select_one(".gs_rt")
    if title_el is not None:
        label = title_el.select_one(".gs_ct1")
        article.doc_type = _doc_type(clean_text(label))
        for tag in title_el.select(".gs_ctc, .gs_ct1, .gs_ct2"):
            tag.decompose()
        link = title_el.find("a")
        article.url = absolute_url(link.get("href")) if link is not None else None
        article.title = clean_text(title_el)
        if article.result_id is None and link is not None:
            article.result_id = link.get("id") or None

    gs_a = block.select_one(".gs_a")
    info = clean_text(gs_a)
    article.publication_info = info
    authors_text, article.venue, article.year, article.source = split_publication_info(info)
    article.authors = _authors(gs_a, authors_text)

    snippet = clean_text(block.select_one(".gs_rs"))
    if snippet:
        match = _ADDED_AGO_RE.match(snippet)
        if match:
            article.added_ago = match.group("ago")
            snippet = snippet[match.end() :].strip() or None
    article.snippet = snippet

    for link in block.select(".gs_fl a"):
        href = absolute_url(link.get("href"))
        if not href:
            continue
        if "cites=" in href and article.cites_id is None:
            article.cites_id = query_param(href, "cites")
            article.cited_by_count = parse_int(clean_text(link))
            article.cited_by_url = href
        elif "cluster=" in href and article.cluster_id is None:
            article.cluster_id = query_param(href, "cluster")
            article.versions_count = parse_int(clean_text(link))
            article.versions_url = href
        elif "q=related:" in href and article.related_url is None:
            article.related_url = href

    for link in block.select(".gs_ggs .gs_or_ggsm a"):
        href = absolute_url(link.get("href"))
        if not href or href.startswith(f"{BASE_URL}/scholar"):
            continue
        kind = link.select_one(".gs_ctg2")
        article.full_text_type = _doc_type(clean_text(kind))
        if kind is not None:
            kind.decompose()
        article.full_text_url = href
        article.full_text_source = clean_text(link)
        break
    return article


def _has_next(soup: BeautifulSoup) -> bool:
    return any(icon.find_parent("a") is not None for icon in soup.select("#gs_n .gs_ico_nav_next"))


def parse_results_page(html: str, *, url: str | None = None, start: int = 0) -> ResultsPage:
    """Parse a Scholar search (or "Cited by") results page.

    Raises:
        ScholarBlockedError: the page is Scholar's CAPTCHA page.
        ScholarParseError: the page is not a Scholar results page.
    """
    check_page(html)
    soup = _soup(html)
    if soup.select_one("#gs_res_ccl, #gs_res_ccl_mid") is None:
        raise ScholarParseError("the page is not a Google Scholar results page")
    blocks = soup.select("#gs_res_ccl_mid div.gs_r.gs_or") or soup.select("div.gs_r.gs_or")
    articles = [parse_result(b, position=start + i + 1) for i, b in enumerate(blocks)]
    suggestion = clean_text(soup.select_one(".gs_r.gs_pda a"))
    return ResultsPage(
        articles=articles,
        total_results=parse_total(clean_text(soup.select_one("#gs_ab_md"))),
        start=start,
        has_next=_has_next(soup),
        suggestion=suggestion,
        url=url,
    )


# --------------------------------------------------------------------------- #
# Author profiles
# --------------------------------------------------------------------------- #


def _right_px(tag: Tag) -> int | None:
    match = _RIGHT_PX_RE.search(tag.get("style") or "")
    return int(match.group(1)) if match else None


def parse_citations_per_year(soup: BeautifulSoup) -> dict[int, int]:
    """Read the profile's citations-per-year bar chart into ``{year: count}``.

    Years and bars are positioned from the right edge; a bar sits 5px right of
    its year label, and years without citations have no bar (count 0).
    """
    chart = soup.select_one(".gsc_md_hist_b")
    if chart is None:
        return {}
    years: list[tuple[int, int]] = []
    for label in chart.select(".gsc_g_t"):
        year, right = parse_int(clean_text(label)), _right_px(label)
        if year is not None and right is not None:
            years.append((right, year))
    counts = {year: 0 for _, year in years}
    for bar in chart.select(".gsc_g_a"):
        right, value = _right_px(bar), parse_int(clean_text(bar.select_one(".gsc_g_al") or bar))
        if right is None or value is None or not years:
            continue
        distance, year = min((abs(right - 5 - r), y) for r, y in years)
        if distance <= 16:
            counts[year] = value
    return dict(sorted(counts.items()))


def _metrics(soup: BeautifulSoup, profile: AuthorProfile) -> None:
    table = soup.select_one("#gsc_rsb_st")
    if table is None:
        return
    headers = [clean_text(th) or "" for th in table.select("thead th")]
    if headers:
        profile.recent_since = parse_int(headers[-1])
    fields = {"citations": "citations", "h-index": "h_index", "i10-index": "i10_index"}
    for row in table.select("tbody tr"):
        cells = row.select("td")
        if len(cells) < 2:
            continue
        name = fields.get((clean_text(cells[0]) or "").lower())
        if name is None:
            continue
        setattr(profile, name, parse_int(clean_text(cells[1])))
        if len(cells) > 2:
            setattr(profile, f"{name}_recent", parse_int(clean_text(cells[2])))


def parse_author_article(row: Tag) -> AuthorArticle:
    """Parse one ``tr.gsc_a_tr`` row of a profile's article table."""
    article = AuthorArticle()
    link = row.select_one("a.gsc_a_at")
    if link is not None:
        article.title = clean_text(link)
        article.url = absolute_url(link.get("href"))
        article.citation_id = query_param(article.url, "citation_for_view")
    grey = row.select(".gsc_a_t .gs_gray")
    if grey:
        article.authors = clean_text(grey[0])
    if len(grey) > 1:
        for tag in grey[1].select(".gs_oph"):
            tag.decompose()
        article.publication = clean_text(grey[1])
    cited = row.select_one(".gsc_a_c a.gsc_a_ac")
    if cited is not None:
        article.cited_by_count = parse_int(clean_text(cited))
        href = absolute_url(cited.get("href"))
        if href and "cites=" in href:
            article.cites_id = query_param(href, "cites")
            article.cited_by_url = href
    article.year = parse_int(clean_text(row.select_one(".gsc_a_y")))
    return article


def parse_author_page(html: str, *, author_id: str, url: str | None = None) -> AuthorProfile:
    """Parse a Scholar author profile page (header, metrics and one article page).

    Raises:
        ScholarBlockedError: the page is Scholar's CAPTCHA page.
        ScholarNotFoundError: Scholar redirected to sign-in, which it does for
            profiles that do not exist or are not public.
        ScholarParseError: the page is not a Scholar profile.
    """
    check_page(html)
    soup = _soup(html)
    name_el = soup.select_one("#gsc_prf_in")
    if name_el is None:
        if _SIGN_IN_RE.search(html or ""):
            raise ScholarNotFoundError(
                f"no public Google Scholar profile for author ID {author_id}"
            )
        raise ScholarParseError("the page is not a Google Scholar profile")

    profile = AuthorProfile(author_id=author_id, name=clean_text(name_el))
    profile.url = author_profile_url(author_id)

    for line in soup.select("#gsc_prf_i .gsc_prf_il"):
        if line.get("id") in ("gsc_prf_ivh", "gsc_prf_int"):
            continue
        profile.affiliation = clean_text(line)
        org = line.select_one('a[href*="org="]')
        if org is not None:
            profile.organization = clean_text(org)
            profile.organization_id = query_param(absolute_url(org.get("href")), "org")
        break

    verified = soup.select_one("#gsc_prf_ivh")
    if verified is not None:
        homepage = verified.find("a", href=True)
        if homepage is not None and not homepage["href"].startswith("/"):
            profile.homepage = homepage["href"]
        match = _EMAIL_RE.search(clean_text(verified) or "")
        profile.email_domain = match.group(1) if match else None

    profile.interests = [
        text for a in soup.select("#gsc_prf_int a") if (text := clean_text(a)) is not None
    ]
    photo = soup.select_one("#gsc_prf_pup-img")
    src = absolute_url(photo.get("src")) if photo is not None else None
    profile.photo_url = src if src and "avatar_scholar" not in src else None

    _metrics(soup, profile)
    profile.citations_per_year = parse_citations_per_year(soup)

    for item in soup.select("#gsc_rsb_co li"):
        link = item.select_one('.gsc_rsb_a_desc a[href*="user="], a[href*="user="]')
        if link is None:
            continue
        co_id = query_param(absolute_url(link.get("href")), "user")
        profile.co_authors.append(
            CoAuthor(
                name=clean_text(link) or "",
                author_id=co_id,
                affiliation=clean_text(item.select_one(".gsc_rsb_a_ext")),
                url=author_profile_url(co_id) if co_id else None,
            )
        )

    profile.articles = [parse_author_article(r) for r in soup.select("#gsc_a_b tr.gsc_a_tr")]
    more = soup.select_one("#gsc_bpf_more")
    profile.has_more_articles = more is not None and not more.has_attr("disabled")
    return profile


# --------------------------------------------------------------------------- #
# "Cite" dialog
# --------------------------------------------------------------------------- #

_EXPORT_LINKS = {
    "bibtex": "bibtex_url",
    "endnote": "endnote_url",
    "refman": "refman_url",
    "refworks": "refworks_url",
}


def parse_cite_page(html: str, *, result_id: str) -> Citation:
    """Parse Scholar's "Cite" dialog: formatted references + export links.

    Raises:
        ScholarBlockedError: the page is Scholar's CAPTCHA page.
        ScholarParseError: the dialog has no citations.
    """
    check_page(html)
    soup = _soup(html)
    citation = Citation(result_id=result_id)
    for row in soup.select("#gs_citt tr"):
        style = clean_text(row.select_one("th"))
        text = clean_text(row.select_one(".gs_citr") or row.select_one("td"))
        if style and text:
            citation.formats[style] = text
    for link in soup.select("#gs_citi a"):
        attr = _EXPORT_LINKS.get((clean_text(link) or "").lower())
        if attr:
            setattr(citation, attr, link.get("href"))
    if not citation.formats and citation.bibtex_url is None:
        raise ScholarParseError(f"no citations in Scholar's cite dialog for {result_id}")
    return citation


def parse_bibtex(text: str) -> str | None:
    """Extract the BibTeX entry from a ``scholar.bib`` response.

    Plain-text responses are returned as-is; an HTML-wrapped one is unwrapped.
    """
    text = (text or "").strip()
    if not text:
        return None
    if text.startswith("@"):
        return text
    soup = _soup(text)
    pre = soup.find("pre")
    body = (pre or soup).get_text().strip()
    return body if body.startswith("@") else None
