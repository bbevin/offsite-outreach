#!/usr/bin/env python3
"""
Parses a Clarify citation pages CSV into the format expected by outreach_finder.py.

Usage:
    python parse_citations.py citations.csv [output.csv]

Input columns:  rank, page, category, mentioned, share, share delta
Output columns: url, priority, rank, category, mentioned, share, share_delta
"""

import csv
import sys


def share_to_priority(share: float) -> str:
    """Map traffic share to a priority level."""
    if share >= 2.0:
        return "high"
    elif share >= 1.0:
        return "medium"
    return "low"


def parse(input_path: str, output_path: str) -> None:
    with open(input_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "url", "priority", "rank", "category", "mentioned", "share", "share_delta",
        ])
        writer.writeheader()
        for row in rows:
            page = row["page"].strip()
            if not page.startswith("http"):
                page = "https://" + page
            share = float(row.get("share", 0))
            writer.writerow({
                "url": page,
                "priority": share_to_priority(share),
                "rank": row.get("rank", ""),
                "category": row.get("category", ""),
                "mentioned": row.get("mentioned", ""),
                "share": row.get("share", ""),
                "share_delta": row.get("share delta", ""),
            })

    print(f"Parsed {len(rows)} citation pages -> {output_path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <citations.csv> [output.csv]")
        sys.exit(1)
    input_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else "input.csv"
    parse(input_path, output_path)
