from __future__ import annotations

import re
from urllib.parse import urlparse, parse_qs

# ---------------------------------------------------------------------------
# Ecommerce platforms — never worth scraping for outreach. Product/category
# pages don't have authors or editorial contacts. Maintained as a hardcoded
# allowlist; expand as we encounter new ones.
# ---------------------------------------------------------------------------

ECOMMERCE_BLACKLIST: set[str] = {
    "amazon.com",
    "ebay.com",
    "walmart.com",
    "target.com",
    "etsy.com",
    "shopify.com",
    "alibaba.com",
    "aliexpress.com",
    "bestbuy.com",
    "costco.com",
    "wayfair.com",
    "homedepot.com",
    "lowes.com",
    "kroger.com",
    "walgreens.com",
    "cvs.com",
    "bjs.com",
    "wegmans.com",
    "priceritemarketplace.com",
}

# ---------------------------------------------------------------------------
# Known affiliate sites — business model depends on sending traffic to other
# companies' products and earning commissions (CPC, CPL, CPA, affiliate links,
# pay-for-inclusion). Organized by category.
# ---------------------------------------------------------------------------

# Review aggregators: users leave reviews on vendor profiles. Getting listed
# means claiming/creating a vendor profile (often self-serve). Engagement model
# is vendor profile management + soliciting customer reviews.
KNOWN_REVIEW_AGGREGATORS: dict[str, str] = {
    "g2.com": "G2",
    "capterra.com": "Capterra",
    "trustradius.com": "TrustRadius",
    "softwareadvice.com": "Software Advice",
    "getapp.com": "GetApp",
    "sourceforge.net": "SourceForge",
    "saasworthy.com": "SaaSWorthy",
    "serchen.com": "Serchen",
    "softwaresuggest.com": "SoftwareSuggest",
    "selecthub.com": "SelectHub",
    "crozdesk.com": "Crozdesk",
    "peerspot.com": "PeerSpot",
    "clutch.co": "Clutch",
    "goodfirms.co": "GoodFirms",
    "saasgenius.com": "SaaSGenius",
    "comparecamp.com": "CompareCamp",
    "featuredcustomers.com": "Featured Customers",
    "trustpilot.com": "Trustpilot",
    "spiceworks.com": "Spiceworks",
    "saashub.com": "SaaSHub",
    "stackshare.io": "StackShare",
    "slant.co": "Slant",
    "alternativeto.net": "AlternativeTo",
    "producthunt.com": "Product Hunt",
}

# Affiliate/editorial sites: editors write "best X" listicles monetized via
# affiliate commissions. Getting listed means pitching an editor or going
# through a partner/media kit intake process.
KNOWN_AFFILIATE_SITES: dict[str, str] = {
    # --- Tech editorial / review sites ---
    "pcmag.com": "PCMag",
    "techradar.com": "TechRadar",
    "cnet.com": "CNET",
    "tomsguide.com": "Tom's Guide",
    "tomshardware.com": "Tom's Hardware",
    "wirecutter.com": "Wirecutter",
    "zdnet.com": "ZDNet",
    "mashable.com": "Mashable",
    "lifewire.com": "Lifewire",
    "howtogeek.com": "How-To Geek",
    "digitaltrends.com": "Digital Trends",
    "laptopmag.com": "Laptop Mag",
    "androidauthority.com": "Android Authority",
    "9to5mac.com": "9to5Mac",
    "9to5google.com": "9to5Google",
    "makeuseof.com": "MakeUseOf",
    "windowscentral.com": "Windows Central",
    "expertreviews.co.uk": "Expert Reviews",
    "theverge.com": "The Verge",
    "eweek.com": "eWeek",

    # --- Finance / business review sites ---
    "nerdwallet.com": "NerdWallet",
    "investopedia.com": "Investopedia",
    "thebalancemoney.com": "The Balance",
    "bankrate.com": "Bankrate",
    "forbes.com": "Forbes Advisor",
    "businessnewsdaily.com": "Business News Daily",
    "business.com": "Business.com",
    "merchantmaverick.com": "Merchant Maverick",
    "fitsmallbusiness.com": "Fit Small Business",
    "money.com": "Money",
    "creditcards.com": "CreditCards.com",
    "usnews.com": "U.S. News 360 Reviews",
    "financesonline.com": "FinancesOnline",
    "technologyadvice.com": "TechnologyAdvice",
    "betterbuys.com": "Better Buys",

    # --- Niche / comparison / listicle affiliate sites ---
    "emailtooltester.com": "EmailToolTester",
    "websitetooltester.com": "WebsiteToolTester",
    "tooltester.com": "Tooltester",
    "websiteplanet.com": "Website Planet",
    "hostingadvice.com": "HostingAdvice",
    "wpbeginner.com": "WPBeginner",
    "codeinwp.com": "CodeinWP",
    "bloggingwizard.com": "Blogging Wizard",
    "authorityhacker.com": "Authority Hacker",
    "backlinko.com": "Backlinko",
    "crm.org": "CRM.org",
    "boringbusinessnerd.com": "Boring Business Nerd",
}

# Social platforms are NEVER classified as affiliate, even if they have ad
# platforms. They require a fundamentally different engagement model
# (community participation, organic posting) than affiliate outreach.
SOCIAL_PLATFORM_BLACKLIST: set[str] = {
    "reddit.com",
    "youtube.com",
    "linkedin.com",
    "x.com",
    "twitter.com",
    "tiktok.com",
    "facebook.com",
    "instagram.com",
    "quora.com",
    "medium.com",
}

# ---------------------------------------------------------------------------
# Known vendor / outreach sites — these sell their own product. "Best X"
# content exists to capture SEO traffic and funnel to their own product,
# NOT to earn affiliate commissions.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Known non-affiliate sites — vendor blogs, industry orgs, analyst firms,
# platform marketplaces, etc. Treated as outreach targets.
# ---------------------------------------------------------------------------

KNOWN_NON_AFFILIATE_SITES: dict[str, str] = {
    "capsulecrm.com": "Capsule CRM",
    "salesflare.com": "Salesflare",
    "blog.salesflare.com": "Salesflare",
    "uschamber.com": "US Chamber of Commerce",
    "nytimes.com": "The New York Times",
}

# ---------------------------------------------------------------------------
# Parent company clusters — if a domain is owned by one of these, it's
# likely an affiliate operation.
# ---------------------------------------------------------------------------

AFFILIATE_PARENT_COMPANIES = {
    "Future plc": ["techradar.com", "tomsguide.com", "tomshardware.com", "laptopmag.com", "windowscentral.com"],
    "Red Ventures": ["cnet.com", "zdnet.com", "bankrate.com", "creditcards.com"],
    "Dotdash Meredith": ["investopedia.com", "lifewire.com", "thebalancemoney.com"],
    "Ziff Davis": ["pcmag.com", "mashable.com"],
    "Gartner": ["capterra.com", "getapp.com", "softwareadvice.com"],
}


def _matches_blacklist(domain: str, blacklist: set[str]) -> bool:
    """Return True if domain exactly matches or is a subdomain of any entry."""
    clean = domain.replace("www.", "")
    if clean in blacklist:
        return True
    return any(clean.endswith("." + d) for d in blacklist)


def should_skip_url(url: str, competitor_domains: list[str] | None = None) -> tuple[bool, str]:
    """Decide whether a URL should be skipped before any scraping work.

    Returns (skip, reason) where reason is one of:
    - "competitor"    — domain in client competitor blacklist
    - "social"        — domain in SOCIAL_PLATFORM_BLACKLIST
    - "ecommerce"     — domain in ECOMMERCE_BLACKLIST
    - "landing_page"  — URL path is empty or "/" (bare domain or subdomain)
    - ""              — do not skip
    """
    # Normalize: ensure scheme so urlparse populates netloc correctly
    if not url.startswith("http"):
        url = "https://" + url

    parsed = urlparse(url)
    domain = parsed.netloc.lower()

    # Competitor check first — these should never be enriched
    if competitor_domains and _matches_blacklist(domain, competitor_domains):
        return True, "competitor"

    if _matches_blacklist(domain, SOCIAL_PLATFORM_BLACKLIST):
        return True, "social"

    if _matches_blacklist(domain, ECOMMERCE_BLACKLIST):
        return True, "ecommerce"

    # Landing page: bare domain or subdomain with no meaningful path.
    # A query string alone (e.g. "/?utm=foo") still counts as a landing page.
    if parsed.path in ("", "/"):
        return True, "landing_page"

    return False, ""


def classify_site(domain: str) -> str:
    """Return site classification based on known domain lists."""
    clean = domain.replace("www.", "")

    # Social platforms are never affiliate — they need a different engagement model
    if clean in SOCIAL_PLATFORM_BLACKLIST:
        return "Social"
    for social_domain in SOCIAL_PLATFORM_BLACKLIST:
        if clean.endswith("." + social_domain):
            return "Social"

    # Check known review aggregators
    if clean in KNOWN_REVIEW_AGGREGATORS:
        return "Review Aggregator"
    for known_domain in KNOWN_REVIEW_AGGREGATORS:
        if clean.endswith("." + known_domain):
            return "Review Aggregator"

    # Check known affiliate/editorial sites
    if clean in KNOWN_AFFILIATE_SITES:
        return "Affiliate/Editorial"
    for known_domain in KNOWN_AFFILIATE_SITES:
        if clean.endswith("." + known_domain):
            return "Affiliate/Editorial"

    # Check known non-affiliate sites
    if clean in KNOWN_NON_AFFILIATE_SITES:
        return "Outreach"
    for known_domain in KNOWN_NON_AFFILIATE_SITES:
        if clean.endswith("." + known_domain):
            return "Outreach"

    return "Unknown"


# ---------------------------------------------------------------------------
# Affiliate disclosure phrases — presence on a page strongly suggests
# the site earns affiliate commissions.
# ---------------------------------------------------------------------------

AFFILIATE_DISCLOSURE_PHRASES = [
    "we may earn a commission",
    "we may receive a commission",
    "we earn a commission",
    "affiliate links",
    "affiliate disclosure",
    "advertising disclosure",
    "at no extra cost to you",
    "at no additional cost to you",
    "how we make money",
    "we may be compensated",
    "commission at no",
    "paid affiliate",
    "partner links",
    "earns commissions",
    "earn commissions",
    "compensated for referring",
    "referral fee",
]

# Affiliate tracking parameters commonly found in outbound links
AFFILIATE_TRACKING_PARAMS = {"ref", "tag", "aff", "via", "partner", "affid", "click_id", "subid"}

# Redirect domains used by affiliate networks
AFFILIATE_REDIRECT_DOMAINS = [
    "go.redirectingat.com",
    "click.linksynergy.com",
    "shareasale.com",
    "tracking.impact.com",
    "commission-junction.com",
    "awin1.com",
    "partnerize.com",
    "rakuten.com",
    "anrdoezrs.net",
    "jdoqocy.com",
    "tkqlhce.com",
    "dpbolvw.net",
    "kqzyfj.com",
]

# Site-owned redirect path patterns
AFFILIATE_REDIRECT_PATHS = ["/go/", "/out/", "/redirect/", "/recommends/", "/refer/"]


def _detect_affiliate_disclosure(text: str) -> bool:
    """Check if page text contains affiliate disclosure language."""
    lower = text.lower()
    return any(phrase in lower for phrase in AFFILIATE_DISCLOSURE_PHRASES)


def _detect_affiliate_links(soup) -> bool:
    """Check if page contains outbound links with affiliate tracking signals."""
    affiliate_link_count = 0
    total_outbound = 0

    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if not href.startswith("http"):
            continue

        try:
            parsed = urlparse(href)
        except Exception:
            continue

        total_outbound += 1

        # Check for affiliate redirect domains
        if any(domain in parsed.netloc for domain in AFFILIATE_REDIRECT_DOMAINS):
            affiliate_link_count += 1
            continue

        # Check for affiliate redirect paths
        if any(path in parsed.path for path in AFFILIATE_REDIRECT_PATHS):
            affiliate_link_count += 1
            continue

        # Check for affiliate tracking params
        params = parse_qs(parsed.query)
        if any(p in params for p in AFFILIATE_TRACKING_PARAMS):
            affiliate_link_count += 1

    # If 3+ affiliate-style links found, strong signal
    return affiliate_link_count >= 3


def _detect_affiliate_content_structure(soup) -> bool:
    """Check if page has structural patterns typical of affiliate listicles.

    Looks for:
    - Comparison tables (often with product names and pricing)
    - Multiple CTA buttons linking to external products
    - "Best X" style headings with numbered/ranked items
    - Pros/cons lists paired with external links
    """
    signals = 0

    # --- Signal 1: Comparison tables with external links ---
    for table in soup.find_all("table"):
        links_in_table = table.find_all("a", href=True)
        external_links = [
            a for a in links_in_table
            if a["href"].startswith("http") and not a["href"].startswith("javascript")
        ]
        if len(external_links) >= 2:
            signals += 1
            break

    # --- Signal 2: Multiple CTA-style buttons pointing to external products ---
    cta_patterns = re.compile(
        r"(visit\s+site|visit\s+website|try\s+(it\s+)?free|get\s+started|sign\s+up|"
        r"go\s+to|view\s+deal|check\s+price|see\s+plans|start\s+free\s+trial|"
        r"claim\s+offer|learn\s+more|view\s+pricing)",
        re.IGNORECASE,
    )
    cta_count = 0
    for a_tag in soup.find_all("a", href=True):
        text = a_tag.get_text(strip=True)
        if cta_patterns.search(text):
            href = a_tag["href"]
            if href.startswith("http"):
                cta_count += 1
    if cta_count >= 3:
        signals += 1

    # --- Signal 3: "Best X" style heading ---
    best_heading_re = re.compile(
        r"\bbest\b.{0,40}\b(software|tools?|apps?|platforms?|services?|solutions?|products?|"
        r"providers?|companies|alternatives?|options?|picks?)\b",
        re.IGNORECASE,
    )
    for tag in soup.find_all(["h1", "h2", "title"]):
        if best_heading_re.search(tag.get_text()):
            signals += 1
            break

    # --- Signal 4: Pros/cons lists (common in review listicles) ---
    pros_cons_re = re.compile(r"\b(pros|cons|advantages|disadvantages|strengths|weaknesses)\b", re.IGNORECASE)
    pros_cons_count = sum(
        1 for tag in soup.find_all(["h2", "h3", "h4", "strong", "b"])
        if pros_cons_re.search(tag.get_text())
    )
    if pros_cons_count >= 2:
        signals += 1

    # --- Signal 5: "List Your Product" / vendor listing page language ---
    listing_re = re.compile(
        r"(list\s+your\s+(product|company|tool|software|business)|"
        r"submit\s+your\s+(product|listing|tool|software)|"
        r"get\s+listed|add\s+your\s+(product|company|listing)|"
        r"advertise\s+with\s+us|sponsor(ship)?\s+packages?|"
        r"cost\s+per\s+(click|lead|acquisition)|"
        r"CPC\s+rat|CPL\s+rat|CPA\s+rat|"
        r"featured\s+listing|premium\s+listing|sponsored\s+listing)",
        re.IGNORECASE,
    )
    page_text = soup.get_text(separator=" ", strip=True)
    if listing_re.search(page_text):
        signals += 1

    # Need at least 2 structural signals to classify as affiliate content
    return signals >= 2


def classify_site_with_content(domain: str, soup=None) -> tuple[str, str]:
    """Classify a site using known lists first, then page content signals.

    Returns (site_type, classification_reason) tuple.
    site_type is one of: "Affiliate/Review", "Outreach"
    """
    # First try the static known-list classification
    static_result = classify_site(domain)
    if static_result != "Unknown":
        return static_result, "known_list"

    # If no page content available, default to outreach
    if soup is None:
        return "Outreach", "unknown_default"

    # Content-based classification for unknown domains
    page_text = soup.get_text(separator=" ", strip=True)

    # Check for affiliate disclosure language
    has_disclosure = _detect_affiliate_disclosure(page_text)

    # Check for affiliate tracking links
    has_affiliate_links = _detect_affiliate_links(soup)

    # Check for affiliate content structure (comparison tables, CTAs, "Best X" headings)
    has_affiliate_structure = _detect_affiliate_content_structure(soup)

    # If both disclosure AND affiliate links present, high confidence affiliate
    if has_disclosure and has_affiliate_links:
        return "Affiliate/Review", "content_signals:disclosure+links"

    # If disclosure alone, moderate confidence
    if has_disclosure:
        return "Affiliate/Review", "content_signals:disclosure"

    # If many affiliate links but no disclosure, still likely affiliate
    if has_affiliate_links:
        return "Affiliate/Review", "content_signals:affiliate_links"

    # Affiliate content structure with any other signal = affiliate
    if has_affiliate_structure and (has_disclosure or has_affiliate_links):
        return "Affiliate/Review", "content_signals:structure+other"

    # Strong structural signals alone (multiple patterns) suggest affiliate
    if has_affiliate_structure:
        return "Affiliate/Review", "content_signals:structure"

    # Default to outreach for unknown sites, flag for review
    return "Outreach", "unknown_default:needs_review"


def get_site_name(domain: str) -> str | None:
    """Return the known site name for a domain, or None."""
    clean = domain.replace("www.", "")

    for registry in (KNOWN_REVIEW_AGGREGATORS, KNOWN_AFFILIATE_SITES, KNOWN_NON_AFFILIATE_SITES):
        if clean in registry:
            return registry[clean]
        for known_domain, name in registry.items():
            if clean.endswith("." + known_domain):
                return name
    return None
