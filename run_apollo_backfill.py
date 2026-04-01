"""Apollo backfill — try Apollo on rows where Hunter found no email.

Usage:
    source .env && python3 run_apollo_backfill.py \
        test_results/enriched_<timestamp>.csv \
        test_results/enriched_final_<timestamp>.csv
"""

import csv
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import apollo


def extract_domain(url: str) -> str:
    try:
        host = url.split("/")[2]
        return re.sub(r"^www\.", "", host).lower()
    except IndexError:
        return ""


def split_name(full_name: str) -> tuple[str, str]:
    parts = full_name.strip().split()
    if len(parts) == 0:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 run_apollo_backfill.py <enriched_csv> [output_csv]")
        sys.exit(1)

    input_path = sys.argv[1]
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    output_path = sys.argv[2] if len(sys.argv) > 2 else f"test_results/enriched_final_{ts}.csv"

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    with open(input_path, newline="") as f:
        rows = list(csv.DictReader(f))

    skip_page_types = {"social", "ecommerce", "landing_page", "reference", "homepage"}
    to_backfill = [r for r in rows if r.get("author", "").strip() and not r.get("email", "").strip()
                   and r.get("page_type", "unknown") not in skip_page_types]
    print(f"Loaded {len(rows)} rows, {len(to_backfill)} missing emails to try Apollo on.")

    apollo_hits = 0
    still_none = 0

    for i, row in enumerate(to_backfill, 1):
        url = row.get("url", "").strip()
        author = row.get("author", "").strip()
        domain = extract_domain(url)
        first, last = split_name(author)

        if first and last and domain:
            a = apollo.find_email(domain, first, last)
            if a and a.get("email"):
                row["email"] = a["email"]
                row["email_source"] = "apollo"
                row["email_score"] = a.get("confidence", "")
                apollo_hits += 1
                print(f"[{i}/{len(to_backfill)}] APOLLO  {a['email']:40s}  {author} @ {domain}")
                continue

        still_none += 1
        print(f"[{i}/{len(to_backfill)}] NONE    {'':40s}  {author} @ {domain}")

    # Write full output (all rows, updated)
    fieldnames = list(rows[0].keys())
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n{'='*50}")
    print(f"Results saved to {output_path}")
    print(f"  Apollo hits:    {apollo_hits}")
    print(f"  Still no email: {still_none}")


if __name__ == "__main__":
    main()
