"""Email enrichment step.

Reads the author extraction CSV, looks up emails via Hunter.io (primary)
and Apollo.io (fallback), and writes an enriched output CSV.

Usage:
    source .env && python3 run_enrichment.py \
        test_results/author_extraction_all_<timestamp>.csv \
        test_results/enriched_<timestamp>.csv
"""

import csv
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import hunter
import apollo


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def extract_domain(url: str) -> str:
    """Pull bare domain from a URL (no www, no path)."""
    try:
        host = url.split("/")[2]
        return re.sub(r"^www\.", "", host).lower()
    except IndexError:
        return ""


def split_name(full_name: str) -> tuple[str, str]:
    """Split 'First Last' → ('First', 'Last').  Handles 2+ word names."""
    parts = full_name.strip().split()
    if len(parts) == 0:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 run_enrichment.py <extraction_csv> [output_csv]")
        sys.exit(1)

    input_path = sys.argv[1]
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    output_path = sys.argv[2] if len(sys.argv) > 2 else f"test_results/enriched_{ts}.csv"

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    with open(input_path, newline="") as f:
        rows = list(csv.DictReader(f))

    # Only enrich rows that have an author name and are article/unknown page types
    skip_page_types = {"social", "ecommerce", "landing_page", "reference", "homepage"}
    to_enrich = [r for r in rows if r.get("author", "").strip()
                 and r.get("page_type", "unknown") not in skip_page_types]
    print(f"Loaded {len(rows)} rows, {len(to_enrich)} have an author to enrich.")

    hunter_hits = 0
    apollo_hits = 0
    no_email = 0

    results = []
    for i, row in enumerate(to_enrich, 1):
        url    = row.get("url", "").strip()
        author = row.get("author", "").strip()
        domain = extract_domain(url)
        first, last = split_name(author)

        email = ""
        email_source = ""
        email_score = ""

        if first and last and domain:
            # Try Hunter first
            h = hunter.find_email(domain, first, last)
            if h and h.get("email"):
                email = h["email"]
                email_score = str(h.get("score", ""))
                email_source = "hunter"
                hunter_hits += 1
                print(f"[{i}/{len(to_enrich)}] HUNTER  {email:40s}  {author} @ {domain}")

            # Fall back to Apollo
            if not email:
                a = apollo.find_email(domain, first, last)
                if a and a.get("email"):
                    email = a["email"]
                    email_score = a.get("confidence", "")
                    email_source = "apollo"
                    apollo_hits += 1
                    print(f"[{i}/{len(to_enrich)}] APOLLO  {email:40s}  {author} @ {domain}")

        if not email:
            no_email += 1
            print(f"[{i}/{len(to_enrich)}] NONE    {'':40s}  {author} @ {domain}")

        results.append({
            **row,
            "email": email,
            "email_source": email_source,
            "email_score": email_score,
        })

    # Write output
    fieldnames = list(rows[0].keys()) + ["email", "email_source", "email_score"]
    # Avoid duplicate columns if re-running
    seen = set()
    fieldnames = [f for f in fieldnames if not (f in seen or seen.add(f))]

    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)

    print(f"\n{'='*50}")
    print(f"Results saved to {output_path}")
    print(f"  Authors enriched: {len(to_enrich)}")
    print(f"  Hunter hits:      {hunter_hits}")
    print(f"  Apollo hits:      {apollo_hits}")
    print(f"  No email found:   {no_email}")


if __name__ == "__main__":
    main()
