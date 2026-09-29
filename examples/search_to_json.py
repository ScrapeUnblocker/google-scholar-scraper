"""Search Google Scholar and save the top results as JSON.

Run:  python examples/search_to_json.py
Needs SCRAPEUNBLOCKER_KEY in the environment (see .env.example).
"""

from google_scholar_scraper import ScholarScraper, to_json

scholar = ScholarScraper()  # reads SCRAPEUNBLOCKER_KEY

papers = scholar.search("large language models evaluation", limit=20)

with open("scholar_llm_evaluation.json", "w", encoding="utf-8") as fh:
    fh.write(to_json(papers, indent=2))

print(f"Saved {len(papers)} papers to scholar_llm_evaluation.json")
for paper in papers[:5]:
    cited = paper.cited_by_count or 0
    print(f"  [{paper.year}] {paper.title} - cited by {cited:,}")
