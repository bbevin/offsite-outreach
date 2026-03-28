from __future__ import annotations

"""
Known publisher contact info for sites that block automated scraping.

When a site can't be scraped, we fall back to this directory of well-known
publishers with their standard advertising/partnership contact pages.
"""

from models import OutreachResult

# Map domain -> partial OutreachResult fields
KNOWN_SITES: dict[str, dict] = {
    "forbes.com": {
        "company_name": "Forbes",
        "contact_type": "affiliate_form",
        "contact_form_url": "https://www.forbes.com/connect/",
        "notes": "Forbes Connect is their branded content/partnerships platform. Could not scrape page (bot protection).",
    },
    "reddit.com": {
        "company_name": "Reddit",
        "contact_type": "affiliate_form",
        "contact_form_url": "https://ads.reddit.com/",
        "notes": "Reddit Ads platform. For organic placement, engage directly in subreddit. Could not scrape page (bot protection).",
    },
    "pcmag.com": {
        "company_name": "PCMag (Ziff Davis)",
        "contact_type": "affiliate_form",
        "contact_form_url": "https://www.pcmag.com/series/advertising-content",
        "company_about_url": "https://www.pcmag.com/about",
        "notes": "Ziff Davis advertising content program. Could not scrape page (bot protection).",
    },
    "nytimes.com": {
        "company_name": "The New York Times",
        "contact_type": "affiliate_form",
        "contact_form_url": "https://nytmediakit.com/",
        "notes": "NYT media kit. Could not scrape page (bot protection).",
    },
    "wirecutter.com": {
        "company_name": "Wirecutter (NYT)",
        "contact_type": "contact_form",
        "contact_form_url": "https://nytmediakit.com/",
        "notes": "Wirecutter is owned by NYT. Use NYT media kit. Could not scrape page (bot protection).",
    },
    "cnet.com": {
        "company_name": "CNET (Ziff Davis)",
        "contact_type": "affiliate_form",
        "contact_form_url": "https://www.cnet.com/about/",
        "notes": "CNET advertising. Could not scrape page (bot protection).",
    },
}


def get_known_site_result(domain: str) -> dict | None:
    """Look up a domain in the known sites directory. Returns field overrides or None."""
    # Try exact match first, then try base domain
    clean = domain.replace("www.", "")
    for known_domain, info in KNOWN_SITES.items():
        if clean == known_domain or clean.endswith("." + known_domain):
            return info
    return None
