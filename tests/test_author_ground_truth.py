#!/usr/bin/env python3
"""
Open-loop author extraction test: fetches real pages, caches HTML locally,
and validates extract_author against author_ground_truth.json.

Usage:
    # First run fetches pages (needs DATAFORSEO creds or direct HTTP):
    python tests/test_author_ground_truth.py

    # Subsequent runs use cached HTML (no network needed):
    python tests/test_author_ground_truth.py
"""

import json
import os
import sys
import hashlib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bs4 import BeautifulSoup
from extractors import extract_author

GROUND_TRUTH = os.path.join(os.path.dirname(__file__), "author_ground_truth.json")
CACHE_DIR = os.path.join(os.path.dirname(__file__), "html_cache")


def url_to_filename(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest() + ".html"


def get_soup(url: str, scraper=None) -> BeautifulSoup | None:
    """Return cached soup, or fetch via scraper, cache, and return."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    fname = url_to_filename(url)
    path = os.path.join(CACHE_DIR, fname)

    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return BeautifulSoup(f.read(), "lxml")

    if scraper is None:
        return None

    soup = scraper.fetch_page(url)
    if soup:
        with open(path, "w", encoding="utf-8") as out:
            out.write(str(soup))
    return soup


def main():
    with open(GROUND_TRUTH) as f:
        entries = json.load(f)

    # Try to create scraper for uncached pages
    scraper = None
    try:
        from scraper import Scraper
        scraper = Scraper()
    except Exception as e:
        print(f"[info] No scraper available ({e}), using cached HTML only")

    passed = 0
    failed = 0
    skipped = 0
    failures = []

    for entry in entries:
        url = entry["url"]
        expected_name = entry.get("author_name", "")

        soup = get_soup(url, scraper)
        if not soup:
            print(f"SKIP    {url} (no cached HTML, no scraper)")
            skipped += 1
            continue

        result = extract_author(soup, url)
        actual = result.name

        if actual == expected_name:
            print(f"PASS    {url}")
            print(f"        expected={expected_name!r}  got={actual!r}")
            passed += 1
        else:
            print(f"FAIL    {url}")
            print(f"        expected={expected_name!r}  got={actual!r}")
            failed += 1
            failures.append((url, expected_name, actual))

    if scraper:
        scraper.stop()

    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed, {skipped} skipped")
    if failures:
        print(f"\nFailures:")
        for url, expected, actual in failures:
            print(f"  {url}")
            print(f"    expected={expected!r}  got={actual!r}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
