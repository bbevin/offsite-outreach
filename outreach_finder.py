#!/usr/bin/env python3
"""
Outreach Target Contact Finder

Reads a CSV of URLs, scrapes each to identify the best contact method,
and outputs an enriched CSV with contact details for outreach.

Usage:
    python outreach_finder.py input.csv output.csv
"""

import csv
import sys

from models import OutreachResult
from scraper import Scraper, get_domain, rate_limit
from extractors import (
    build_linkedin_search_url,
    build_linkedin_profile_url,
    detect_affiliate_networks,
    detect_contact_method,
    extract_affiliate_instructions,
    extract_author,
    extract_company_name,
    find_team_contacts,
    generate_email_candidates,
)
from known_sites import get_known_site_result
from classifier import (
    classify_site,
    classify_site_with_content,
    get_site_name,
    KNOWN_OUTREACH_SITES,
    KNOWN_NON_AFFILIATE_SITES,
)


def classify_send(result: OutreachResult, send_override: str = "") -> None:
    """Set send_classification and authority_score on result.

    Logic:
    - If send_override is provided in the input CSV, use it directly.
    - Affiliate/Review sites → not_applicable.
    - Known brand domains (in KNOWN_OUTREACH_SITES or KNOWN_NON_AFFILIATE_SITES) → manual_send.
    - Unknown domains that defaulted to Outreach → auto_send.
    """
    # Manual override from input CSV takes priority
    if send_override:
        result.send_classification = send_override
        result.authority_score = "manual_override"
        return

    # Affiliate sites — outreach is via form, not email
    if result.site_type == "Affiliate/Review":
        result.send_classification = "not_applicable"
        result.authority_score = "affiliate_site"
        return

    # Check if domain is a known brand (vendor or non-affiliate org)
    clean_domain = result.domain.replace("www.", "")
    is_known_brand = (
        clean_domain in KNOWN_OUTREACH_SITES
        or clean_domain in KNOWN_NON_AFFILIATE_SITES
        or any(clean_domain.endswith("." + d) for d in KNOWN_OUTREACH_SITES)
        or any(clean_domain.endswith("." + d) for d in KNOWN_NON_AFFILIATE_SITES)
    )

    if is_known_brand:
        result.send_classification = "manual_send"
        result.authority_score = "known_brand"
        return

    # Known-list classification (e.g. domain_pattern for blog.company.com)
    if result.classification_reason == "domain_pattern":
        result.send_classification = "manual_send"
        result.authority_score = "heuristic:vendor_blog_pattern"
        return

    # Default: unknown/low-authority publisher → auto_send
    result.send_classification = "auto_send"
    result.authority_score = "heuristic:unknown_publisher"


def process_url(url: str, priority: str, scraper: Scraper, send_override: str = "") -> OutreachResult:
    """Process a single URL and return an OutreachResult."""
    result = OutreachResult(url=url, priority=priority)
    domain = get_domain(url)
    result.domain = domain

    print(f"\n{'='*60}")
    print(f"Processing: {url}")
    print(f"  Priority: {priority}")

    # 1. Fetch the page
    soup = scraper.fetch_page(url)
    if not soup:
        # Classify with domain only (no page content)
        result.site_type, result.classification_reason = classify_site_with_content(domain)
        print(f"  Site type: {result.site_type} ({result.classification_reason})")
        # Check known sites directory as fallback
        known = get_known_site_result(domain)
        if known:
            print(f"  Using known site data for {domain}")
            for field, value in known.items():
                setattr(result, field, value)
            result.linkedin_search_url = build_linkedin_search_url(result.company_name, result.author_name)
            classify_send(result, send_override)
            return result
        result.notes = "Failed to fetch page"
        classify_send(result, send_override)
        return result

    # 2. Classify using known lists + page content signals
    result.site_type, result.classification_reason = classify_site_with_content(domain, soup)
    print(f"  Site type: {result.site_type} ({result.classification_reason})")
    if "needs_review" in result.classification_reason:
        result.notes = "Classification uncertain — flagged for human review"

    # 3. Extract company name
    result.company_name = extract_company_name(soup, domain)
    print(f"  Company: {result.company_name}")

    # 4. Extract author
    author = extract_author(soup, url)
    result.author_name = author.name
    result.author_url = author.url
    if author.name:
        print(f"  Author: {author.name}")

    # 5. Detect contact method
    rate_limit()
    contact = detect_contact_method(soup, url, scraper)
    result.contact_type = contact.contact_type
    result.contact_form_url = contact.contact_form_url
    print(f"  Contact type: {contact.contact_type}")
    if contact.contact_form_url:
        print(f"  Contact URL: {contact.contact_form_url}")

    # 5b. Extract affiliate instructions for affiliate sites
    if result.site_type == "Affiliate/Review" and contact.contact_form_url:
        rate_limit()
        result.affiliate_instructions = extract_affiliate_instructions(
            contact.contact_form_url, scraper
        )
        if result.affiliate_instructions:
            print(f"  Affiliate instructions: {result.affiliate_instructions[:100]}...")

    # 5c. Detect affiliate networks from article page content
    if result.site_type == "Affiliate/Review":
        result.affiliate_network = detect_affiliate_networks(soup)
        if result.affiliate_network:
            print(f"  Affiliate network(s): {result.affiliate_network}")

    # 6. Find team contacts
    rate_limit()
    about_url, team = find_team_contacts(url, scraper)
    result.company_about_url = about_url
    if team:
        result.team_contacts = "; ".join(f"{t.name} ({t.role})" for t in team)
        print(f"  Team contacts: {result.team_contacts}")

    # 7. Generate email candidates for outreach targets with a known author
    if result.site_type != "Affiliate/Review" and author.name:
        result.author_email_candidates = generate_email_candidates(author.name, domain)
        if result.author_email_candidates:
            print(f"  Email candidates: {result.author_email_candidates}")

    # 8. LinkedIn search — use author name for targeted search when available
    result.linkedin_search_url = build_linkedin_search_url(result.company_name, result.author_name)
    if result.author_name:
        profile_url = build_linkedin_profile_url(result.author_name)
        if profile_url:
            result.linkedin_search_url = f"{profile_url} | {result.linkedin_search_url}"

    # Combine notes
    notes_parts = []
    if scraper.last_fetch_method == "direct_http":
        notes_parts.append("Fetched via direct HTTP fallback")
    if contact.notes:
        notes_parts.append(contact.notes)
    result.notes = "; ".join(notes_parts)

    # 9. Send classification
    classify_send(result, send_override)
    print(f"  Send classification: {result.send_classification} ({result.authority_score})")

    return result


def read_input(filepath: str) -> list[tuple[str, str, dict]]:
    """Read the input CSV and return a list of (url, priority, extra_fields) tuples.

    Supports two formats:
    - Standard: columns 'url' and 'priority'
    - Citation: columns 'page', 'share' (+ any other columns preserved as extras)
    """
    entries = []
    with open(filepath, "r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Try standard format first
            url = row.get("url", "").strip()
            priority = row.get("priority", "").strip()

            # Fall back to citation format
            if not url:
                page = row.get("page", "").strip()
                if page:
                    url = page if page.startswith("http") else f"https://{page}"
                priority = priority or row.get("share", "").strip()

            # Preserve all original columns as extras
            extras = {k: v for k, v in row.items() if k not in ("url", "page")}

            if url:
                entries.append((url, priority, extras))
    return entries


def write_output(filepath: str, results: list[OutreachResult]):
    """Write results to a CSV file."""
    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        headers = results[0].csv_headers() if results else OutreachResult._BASE_HEADERS
        writer.writerow(headers)
        for r in results:
            writer.writerow(r.to_row())


def main():
    if len(sys.argv) < 3:
        print("Usage: python outreach_finder.py <input.csv> <output.csv>")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2]

    entries = read_input(input_file)
    print(f"Loaded {len(entries)} URLs from {input_file}")

    results = []
    with Scraper() as scraper:
        for i, (url, priority, extras) in enumerate(entries, 1):
            print(f"\n[{i}/{len(entries)}]", end="")
            send_override = extras.pop("send_override", "").strip()
            result = process_url(url, priority, scraper, send_override=send_override)
            result.extras = extras
            results.append(result)

    write_output(output_file, results)
    print(f"\n{'='*60}")
    print(f"Done! Results written to {output_file}")
    print(f"Processed {len(results)} URLs")


if __name__ == "__main__":
    main()
