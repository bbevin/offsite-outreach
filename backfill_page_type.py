"""Backfill page_type into an existing extraction CSV using URL pattern inference.

No API calls — purely URL-based classification.

Usage:
    python3 backfill_page_type.py test_results/author_extraction_all_<timestamp>.csv
"""

import csv
import sys
from urllib.parse import urlparse
from pathlib import Path


def infer_page_type(url: str) -> str:
    """Infer page type from URL path patterns."""
    parsed = urlparse(url)
    path = parsed.path.lower()
    domain = parsed.netloc.replace("www.", "").lower()

    social_domains = {"reddit.com", "youtube.com", "linkedin.com", "twitter.com",
                      "facebook.com", "instagram.com", "quora.com", "medium.com"}
    if any(s in domain for s in social_domains):
        return "social"

    if "wikipedia.org" in domain:
        return "reference"

    if "etsy.com" in domain:
        return "ecommerce"
    ecommerce_patterns = ["/products/", "/product/", "/shop/", "/listing/",
                          "/seller/", "/sales/", "/cart", "/checkout"]
    if any(p in path for p in ecommerce_patterns):
        return "ecommerce"

    article_patterns = ["/blog/", "/blogs/", "/article/", "/articles/",
                        "/post/", "/posts/", "/news/", "/magazine/",
                        "/resources/", "/guides/", "/guide/", "/reviews/",
                        "/review/", "/tips/", "/learn/"]
    if any(p in path for p in article_patterns):
        return "article"

    if "substack.com" in domain:
        return "article"

    landing_patterns = ["/features/", "/pricing/", "/plans/", "/solutions/",
                        "/use-case/", "/use-cases/", "/industries/",
                        "/comparisons/", "/compare/"]
    if any(p in path for p in landing_patterns):
        return "landing_page"

    if path in ("", "/"):
        return "homepage"

    return "unknown"


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 backfill_page_type.py <input_csv>")
        sys.exit(1)

    input_path = sys.argv[1]

    with open(input_path, newline="") as f:
        rows = list(csv.DictReader(f))
        fieldnames = list(rows[0].keys())

    if "page_type" not in fieldnames:
        fieldnames.append("page_type")

    counts = {}
    for row in rows:
        pt = infer_page_type(row["url"])
        row["page_type"] = pt
        counts[pt] = counts.get(pt, 0) + 1

    with open(input_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    print(f"Updated {len(rows)} rows in {input_path}")
    for pt, c in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"  {pt}: {c}")


if __name__ == "__main__":
    main()
