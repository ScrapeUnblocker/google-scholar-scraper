"""Shared fixtures: synthetic Google Scholar pages (no network, no API credit).

The builders produce compact HTML shaped like Scholar's real markup. The
ScrapeUnblocker API returns pages *prettified*, so tests also run the parsers on
``prettify(html)`` to make sure the text joining copes with the extra whitespace.
"""

from __future__ import annotations

from collections.abc import Sequence

from bs4 import BeautifulSoup


def prettify(html: str) -> str:
    """Re-indent ``html`` the way the getPageSource API returns it."""
    return BeautifulSoup(html, "html.parser").prettify()


SNIPPET = "&hellip; the development of <b>language models</b>, particularly &hellip;"


def result_block(
    cid: str = "o93zfHYlUTIJ",
    *,
    title: str = "A survey on evaluation of <b>large language models</b>",
    href: str | None = "https://dl.acm.org/doi/abs/10.1145/3641289",
    doc_type: str | None = None,
    authors: Sequence[tuple[str, str | None]] = (
        ("Y Chang", "Hw-lrpAAAAAJ"),
        ("X Wang", "Q7Ieos8AAAAJ"),
        ("J Wang", None),
    ),
    authors_more: bool = True,
    tail: str = "ACM transactions on&nbsp;&hellip;, 2024 - dl.acm.org",
    snippet: str | None = SNIPPET,
    cited_by: tuple[int, str] | None = (6818, "3625720365842685347"),
    versions: tuple[int, str] | None = (11, "3625720365842685347"),
    related: bool = True,
    full_text: tuple[str, str, str] | None = (
        "PDF",
        "acm.org",
        "https://dl.acm.org/doi/pdf/10.1145/3641289",
    ),
) -> str:
    """One ``div.gs_r.gs_or.gs_scl`` result, like Scholar renders it."""
    side = ""
    if full_text is not None:
        kind, source, url = full_text
        side = (
            '<div class="gs_ggs gs_fl"><div class="gs_ggsd"><div class="gs_or_ggsm">'
            f'<a href="{url}"><span class="gs_ctg2">[{kind}]</span> {source}</a>'
            '<a href="/scholar?output=instlink&amp;q=info:x">Full View</a>'
            "</div></div></div>"
        )
    label = ""
    if doc_type:
        short = doc_type[0]
        label = (
            f'<span class="gs_ctc"><span class="gs_ct1">[{doc_type}]</span>'
            f'<span class="gs_ct2">[{short}]</span></span> '
        )
    if href:
        heading = f'<h3 class="gs_rt">{label}<a href="{href}" id="{cid}">{title}</a></h3>'
    else:
        heading = f'<h3 class="gs_rt">{label}<span id="{cid}">{title}</span></h3>'
    names = []
    for name, author_id in authors:
        if author_id:
            names.append(f'<a href="/citations?user={author_id}&amp;hl=en&amp;oi=sra">{name}</a>')
        else:
            names.append(name)
    byline = ", ".join(names) + ("&hellip;" if authors_more else "")
    links = [
        '<a href="javascript:void(0)" class="gs_or_sav gs_or_btn">Save</a>',
        '<a href="javascript:void(0)" class="gs_or_cit gs_or_btn">Cite</a>',
    ]
    if cited_by:
        count, cites = cited_by
        links.append(
            f'<a href="/scholar?cites={cites}&amp;as_sdt=5,33&amp;hl=en">Cited by {count}</a>'
        )
    if related:
        links.append(
            f'<a href="/scholar?q=related:{cid}:scholar.google.com/&amp;hl=en">Related articles</a>'
        )
    if versions:
        count, cluster = versions
        links.append(f'<a href="/scholar?cluster={cluster}&amp;hl=en">All {count} versions</a>')
    body = f'<div class="gs_rs">{snippet}</div>' if snippet is not None else ""
    return (
        f'<div class="gs_r gs_or gs_scl" data-cid="{cid}" data-rp="0">{side}'
        f'<div class="gs_ri">{heading}<div class="gs_a">{byline}&nbsp;- {tail}</div>'
        f'{body}<div class="gs_fl gs_flb">{"".join(links)}</div></div></div>'
    )


def results_page(
    blocks: Sequence[str],
    *,
    header: str | None = "About 6,500,000 results (<b>0.10</b> sec)",
    next_start: int | None = 10,
    suggestion: str | None = None,
) -> str:
    """A full Scholar results page wrapping ``blocks``."""
    nav = ""
    if next_start is not None:
        nav = (
            '<div id="gs_n" role="navigation"><table><tr>'
            '<td><span class="gs_ico gs_ico_nav_current"></span><b>1</b></td>'
            f'<td align="left"><a href="/scholar?start={next_start}&amp;q=x&amp;hl=en">'
            '<span class="gs_ico gs_ico_nav_next"></span><b>Next</b></a></td>'
            "</tr></table></div>"
        )
    elif blocks:
        nav = (
            '<div id="gs_n" role="navigation"><table><tr><td align="left">'
            '<span class="gs_ico gs_ico_nav_last"></span></td></tr></table></div>'
        )
    ab = f'<div id="gs_ab_md"><div class="gs_ab_mdw">{header or ""}</div></div>'
    dym = ""
    if suggestion:
        dym = (
            '<div class="gs_r gs_pda"><span class="gs_red">Did you mean:</span> '
            f'<a href="/scholar?hl=en&amp;q={suggestion.replace(" ", "+")}"><b><i>{suggestion}'
            "</i></b></a></div>"
        )
    return (
        "<html><head><title>Google Scholar</title></head><body>"
        f'{ab}<div id="gs_res_ccl"><div id="gs_res_ccl_top">{dym}</div>'
        f'<div id="gs_res_ccl_mid">{"".join(blocks)}</div>{nav}</div>'
        "</body></html>"
    )


def author_row(
    title: str = "Deep learning",
    *,
    citation_id: str = "JicYPdAAAAAJ:C-SEpTPhZ1wC",
    authors: str = "Y LeCun, Y Bengio, G Hinton",
    publication: str = "Nature 521 (7553), 436-444",
    year: int | None = 2015,
    cited: int | None = 120642,
    cites: str | None = "5362332738201102290",
) -> str:
    user = citation_id.split(":")[0]
    cited_cell = ""
    if cited is not None:
        cited_cell = (
            '<a class="gsc_a_ac gs_ibl" href="https://scholar.google.com/scholar?oi=bibs'
            f'&amp;hl=en&amp;cites={cites}">{cited}</a>'
        )
    else:
        cited_cell = '<a class="gsc_a_ac gs_ibl gsc_a_acm" href="javascript:void(0)"></a>'
    year_html = f'<span class="gsc_a_h gsc_a_hc gs_ibl">{year}</span>' if year else ""
    return (
        '<tr class="gsc_a_tr"><td class="gsc_a_t">'
        '<a class="gsc_a_at" href="/citations?view_op=view_citation&amp;hl=en&amp;'
        f'user={user}&amp;citation_for_view={citation_id}">{title}</a>'
        f'<div class="gs_gray">{authors}</div>'
        f'<div class="gs_gray">{publication}<span class="gs_oph">, {year}</span></div></td>'
        f'<td class="gsc_a_c">{cited_cell}</td>'
        f'<td class="gsc_a_y">{year_html}</td></tr>'
    )


def author_page(
    rows: Sequence[str] | None = None,
    *,
    name: str = "Geoffrey Hinton",
    has_more: bool = False,
    histogram: Sequence[tuple[int, int | None]] = ((2023, 110325), (2024, None), (2025, 119114)),
) -> str:
    """A Scholar author profile page. ``None`` counts leave a year without a bar."""
    rows = [author_row()] if rows is None else rows
    labels, bars = [], []
    n = len(histogram)
    for i, (year, count) in enumerate(histogram):
        right = 3 + 32 * (n - 1 - i)
        labels.append(f'<span class="gsc_g_t" style="right:{right}px">{year}</span>')
        if count is not None:
            bars.append(
                f'<a href="javascript:void(0)" class="gsc_g_a" style="right:{right + 5}px;'
                f'top:10px;height:150px;z-index:{n - i}"><span class="gsc_g_al">{count}</span></a>'
            )
    more = "" if has_more else ' disabled=""'
    return (
        f"<html><head><title>{name} - Google Scholar</title></head><body>"
        '<div id="gsc_prf_i">'
        f'<div id="gsc_prf_inw"><div id="gsc_prf_in">{name}</div></div>'
        '<div class="gsc_prf_il">Emeritus Prof. Computer Science, <a class="gsc_prf_ila" '
        'href="/citations?view_op=view_org&amp;hl=en&amp;org=8515235176732148308">'
        "University of Toronto</a></div>"
        '<div class="gsc_prf_il" id="gsc_prf_ivh">Verified email at cs.toronto.edu - '
        '<a href="http://www.cs.toronto.edu/~hinton" rel="nofollow" class="gsc_prf_ila">'
        "Homepage</a></div>"
        '<div class="gsc_prf_il" id="gsc_prf_int">'
        '<a class="gsc_prf_inta gs_ibl" href="/citations?view_op=search_authors&amp;'
        'mauthors=label:machine_learning">machine learning</a>'
        '<a class="gsc_prf_inta gs_ibl" href="/citations?view_op=search_authors&amp;'
        'mauthors=label:psychology">psychology</a></div></div>'
        '<img id="gsc_prf_pup-img" src="https://scholar.googleusercontent.com/citations?'
        'view_op=view_photo&amp;user=JicYPdAAAAAJ&amp;citpid=2" alt="">'
        '<table id="gsc_rsb_st"><thead><tr><th class="gsc_rsb_sth"></th>'
        '<th class="gsc_rsb_sth">All</th><th class="gsc_rsb_sth">Since 2021</th></tr></thead>'
        "<tbody>"
        '<tr><td class="gsc_rsb_sc1"><a class="gsc_rsb_f">Citations</a></td>'
        '<td class="gsc_rsb_std">1091581</td><td class="gsc_rsb_std">626413</td></tr>'
        '<tr><td class="gsc_rsb_sc1"><a class="gsc_rsb_f">h-index</a></td>'
        '<td class="gsc_rsb_std">195</td><td class="gsc_rsb_std">134</td></tr>'
        '<tr><td class="gsc_rsb_sc1"><a class="gsc_rsb_f">i10-index</a></td>'
        '<td class="gsc_rsb_std">549</td><td class="gsc_rsb_std">403</td></tr>'
        "</tbody></table>"
        f'<div class="gsc_md_hist_b">{"".join(labels)}{"".join(bars)}</div>'
        '<div id="gsc_rsb_co"><ul class="gsc_rsb_a"><li><div class="gsc_rsb_aa">'
        '<span class="gsc_rsb_a_desc"><a href="/citations?user=m1qAiOUAAAAJ&amp;hl=en">'
        'Terrence Sejnowski</a><span class="gsc_rsb_a_ext">Salk Institute</span>'
        '<span class="gsc_rsb_a_ext gsc_rsb_a_ext2">Verified email at salk.edu</span>'
        "</span></div></li></ul></div>"
        f'<table id="gsc_a_t"><tbody id="gsc_a_b">{"".join(rows)}</tbody></table>'
        f'<div id="gsc_lwp"><button id="gsc_bpf_more" type="button"{more}>'
        "<span>Show more</span></button></div>"
        "</body></html>"
    )


BIBTEX_URL = "https://scholar.googleusercontent.com/scholar.bib?q=info:o93zfHYlUTIJ:x&ct=citation"

CITE_HTML = (
    '<div id="gs_citt"><table><tr><th class="gs_cith">MLA</th><td><div class="gs_citr">'
    'Chang, Yupeng, et al. "A survey on evaluation of large language models." '
    "<i>ACM transactions on intelligent systems and technology</i> 15.3 (2024): 1-45."
    '</div></td></tr><tr><th class="gs_cith">APA</th><td><div class="gs_citr">'
    "Chang, Y., Wang, X. (2024). A survey on evaluation of large language models. "
    "<i>ACM transactions on intelligent systems and technology</i>, <i>15</i>(3), 1-45."
    '</div></td></tr></table></div><div id="gs_citi">'
    f'<a class="gs_citi" href="{BIBTEX_URL.replace("&", "&amp;")}">BibTeX</a>'
    '<a class="gs_citi" href="https://scholar.googleusercontent.com/scholar.enw?q=x">'
    "EndNote</a></div>"
)

BIBTEX = (
    "@article{chang2024survey,\n  title={A survey on evaluation of large language models},\n"
    "  year={2024}\n}"
)

CAPTCHA_HTML = (
    "<html><head><title>https://scholar.google.com/scholar?q=x</title></head><body>"
    '<form id="captcha-form" action="index" method="post">'
    '<div class="g-recaptcha" data-sitekey="k"></div></form></body></html>'
)

SIGN_IN_HTML = (
    "<html><head><title>Google Scholar Citations</title></head><body>"
    "<h1>Sign in</h1><div>to continue to Google Scholar Citations</div></body></html>"
)
