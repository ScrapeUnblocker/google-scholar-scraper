"""Collect papers for a literature review into one CSV, most cited first.

Runs several related searches over a publication-year window, drops
citation-only entries, merges everything (de-duplicated by Scholar result ID)
and writes a spreadsheet with authors, venue, year, citation counts and a
full-text link where Scholar has one.

Run:  python examples/literature_review_csv.py
Needs SCRAPEUNBLOCKER_KEY in the environment (see .env.example).
"""

from google_scholar_scraper import ScholarScraper, to_csv

QUERIES = [
    "retrieval augmented generation",
    "retrieval augmented generation evaluation",
    '"RAG" hallucination large language models',
]

scholar = ScholarScraper()  # reads SCRAPEUNBLOCKER_KEY

papers = scholar.search_many(
    QUERIES,
    limit_per_query=20,
    year_from=2023,
    year_to=2025,
    include_citations=False,
)
papers.sort(key=lambda p: p.cited_by_count or 0, reverse=True)

to_csv(papers, "rag_literature_review.csv")
with_pdf = sum(1 for p in papers if p.full_text_url)
print(f"Wrote {len(papers)} papers to rag_literature_review.csv ({with_pdf} with a full-text link)")
