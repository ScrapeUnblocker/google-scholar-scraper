"""Print a researcher's citation metrics and most cited papers.

Pass a Google Scholar author ID (the `user=` value in a profile URL, or the
`author_id` of any author in search output) or a full profile URL.

Run:  python examples/author_report.py JicYPdAAAAAJ
Needs SCRAPEUNBLOCKER_KEY in the environment (see .env.example).
"""

import sys

from google_scholar_scraper import ScholarScraper

author_id = sys.argv[1] if len(sys.argv) > 1 else "JicYPdAAAAAJ"

scholar = ScholarScraper()  # reads SCRAPEUNBLOCKER_KEY
profile = scholar.author(author_id, max_articles=100)

print(f"{profile.name} - {profile.affiliation}")
print(f"Interests: {', '.join(profile.interests) or '-'}")
since = profile.recent_since or "recent years"
print(f"Citations: {profile.citations or 0:,} (since {since}: {profile.citations_recent or 0:,})")
print(f"h-index:   {profile.h_index} (since {since}: {profile.h_index_recent})")
print(f"i10-index: {profile.i10_index} (since {since}: {profile.i10_index_recent})")

last_years = list(profile.citations_per_year.items())[-5:]
print("Citations per year: " + ", ".join(f"{year}: {count:,}" for year, count in last_years))

print("\nMost cited papers:")
for paper in profile.articles[:10]:
    print(f"  {paper.cited_by_count or 0:>8,}  {paper.title} ({paper.year})")
