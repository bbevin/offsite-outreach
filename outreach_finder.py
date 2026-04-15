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
    extract_article_title,
    extract_author,
    extract_company_name,
    find_team_contacts,
    enrich_contact_email,
    generate_email_candidates,
)
import hunter
from known_sites import get_known_site_result
from classifier import (
    classify_site,
    classify_site_with_content,
    get_site_name,
    should_skip_url,
    KNOWN_NON_AFFILIATE_SITES,
)


def classify_send(result: OutreachResult, send_override: str = "") -> None:
    """Set send_classification and authority_score on result.

    Logic:
    - If send_override is provided in the input CSV, use it directly.
    - Affiliate/Review sites → not_applicable.
    - Known brand domains (in KNOWN_NON_AFFILIATE_SITES) → manual_send.
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

    # Check if domain is a known brand (non-affiliate org)
    clean_domain = result.domain.replace("www.", "")
    is_known_brand = (
        clean_domain in KNOWN_NON_AFFILIATE_SITES
        or any(clean_domain.endswith("." + d) for d in KNOWN_NON_AFFILIATE_SITES)
    )

    if is_known_brand:
        result.send_classification = "manual_send"
        result.authority_score = "known_brand"
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

    # 3. Extract company name and article title
    result.company_name = extract_company_name(soup, domain)
    print(f"  Company: {result.company_name}")
    result.article_title = extract_article_title(soup, url)
    if result.article_title:
        print(f"  Article: {result.article_title}")

    # 4. Extract author
    author = extract_author(soup, url)
    if author.name:
        parts = author.name.strip().split(None, 1)
        result.author_first_name = parts[0] if parts else ""
        result.author_last_name = parts[1] if len(parts) > 1 else ""
        print(f"  Author: {author.name}")
    result.author_url = author.url

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

    # 7. Enrich contact email (Hunter.io with pattern fallback)
    if result.site_type != "Affiliate/Review" and author.name:
        verified, candidates, source = enrich_contact_email(author.name, domain)
        result.author_email_candidates = candidates
        result.verified_email = verified
        result.email_source = source
        if verified:
            print(f"  Verified email (Hunter): {verified}")
        elif candidates:
            print(f"  Email candidates (patterns): {candidates}")

    # 7b. Department fallback — if author-based enrichment found nothing,
    # try Hunter domain-search for marketing contacts at the company.
    if (
        result.site_type != "Affiliate/Review"
        and not result.verified_email
        and not result.author_email_candidates
    ):
        rate_limit()
        contacts = hunter.find_department_contacts(domain, "marketing", limit=5)
        if contacts:
            result.marketing_contacts = "; ".join(
                f"{c['name']} ({c.get('position') or 'marketing'}) <{c['email']}>"
                for c in contacts if c.get("email")
            )
            print(f"  Marketing fallback: {len(contacts)} contacts")

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


def _make_skipped_result(url: str, priority: str, reason: str, extras: dict) -> OutreachResult:
    """Build a stub OutreachResult for a URL that was filtered out before scraping."""
    from scraper import get_domain
    result = OutreachResult(url=url, priority=priority)
    result.domain = get_domain(url)
    result.site_type = "Skipped"
    result.classification_reason = f"prefilter:{reason}"
    result.send_classification = "not_applicable"
    result.authority_score = f"skipped:{reason}"
    result.notes = f"Skipped before scraping: {reason}"
    result.extras = extras
    return result


def main():
    # Parse --client and --no-skip flags
    args = sys.argv[1:]
    client_slug = None
    no_skip = False
    positional = []

    i = 0
    while i < len(args):
        if args[i] == "--client" and i + 1 < len(args):
            client_slug = args[i + 1]
            i += 2
        elif args[i] == "--no-skip":
            no_skip = True
            i += 1
        else:
            positional.append(args[i])
            i += 1

    if len(positional) < 2 or not client_slug:
        from client_config import list_clients
        available = ", ".join(list_clients()) or "(none created yet)"
        print("Usage: python outreach_finder.py --client <CLIENT> <input.csv> <output.csv> [--no-skip]")
        print(f"\nAvailable clients: {available}")
        print("Client configs live in clients/<name>.yaml with competitor blacklists.")
        sys.exit(1)

    # Load client config — will exit if competitors list is empty
    from client_config import load_client
    client = load_client(client_slug)
    competitor_domains = client["competitors"]
    print(f"Client: {client['name']} ({len(competitor_domains)} competitor domains blacklisted)")

    input_file = positional[0]
    output_file = positional[1]

    entries = read_input(input_file)
    print(f"Loaded {len(entries)} URLs from {input_file}")

    # Pre-filter: partition into to_process and skipped
    to_process: list[tuple[str, str, dict]] = []
    skipped_results: list[OutreachResult] = []
    skip_counts: dict[str, int] = {}

    if no_skip:
        to_process = entries
        print("Pre-filtering disabled (--no-skip)")
    else:
        for url, priority, extras in entries:
            # Skip pages that already mention the client
            mentioned = extras.get("mentioned", "").strip().lower()
            if mentioned == "mentioned":
                skip, reason = True, "already_mentioned"
            else:
                skip, reason = should_skip_url(url, competitor_domains)
            if skip:
                skip_counts[reason] = skip_counts.get(reason, 0) + 1
                skipped_results.append(_make_skipped_result(url, priority, reason, extras))
            else:
                to_process.append((url, priority, extras))

        if skip_counts:
            summary = ", ".join(f"{n} {r}" for r, n in sorted(skip_counts.items()))
            print(f"Pre-filtered: skipping {len(skipped_results)} URLs ({summary})")
        print(f"Processing {len(to_process)} URLs")

    results: list[OutreachResult] = []
    checkpoint_file = output_file.replace(".csv", "_checkpoint.csv")
    with Scraper() as scraper:
        for i, (url, priority, extras) in enumerate(to_process, 1):
            print(f"\n[{i}/{len(to_process)}]", end="")
            send_override = extras.pop("send_override", "").strip()
            result = process_url(url, priority, scraper, send_override=send_override)
            result.extras = extras
            results.append(result)

            # Save checkpoint every 10 rows
            if i % 10 == 0:
                write_output(checkpoint_file, results + skipped_results)
                print(f"  [checkpoint saved: {i}/{len(to_process)}]")

    # Remove checkpoint after successful completion
    import os
    if os.path.exists(checkpoint_file):
        os.remove(checkpoint_file)

    # Raw log file: all results including skipped stubs
    all_results = results + skipped_results
    write_output(output_file, all_results)
    print(f"\n{'='*60}")
    print(f"Raw log written to {output_file} ({len(all_results)} rows)")

    # Clean file: only actionable outreach targets (no skipped rows)
    clean_file = output_file.replace(".csv", "_clean.csv")
    if results:
        write_output(clean_file, results)
    print(f"Clean file written to {clean_file} ({len(results)} rows)")
    print(f"  Filtered out {len(skipped_results)} skipped rows")


if __name__ == "__main__":
    main()
