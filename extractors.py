from __future__ import annotations

import json
import re
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from models import AuthorInfo, ContactInfo, TeamContact
from scraper import Scraper, get_base_url, make_absolute, rate_limit

# ---------------------------------------------------------------------------
# Author name validation
# ---------------------------------------------------------------------------

_NAV_BLOCKLIST = {
    "home", "menu", "about", "contact", "blog", "news", "login",
    "sign up", "subscribe", "search", "skip to content", "close",
    "toggle navigation", "main menu", "navigation", "back", "next",
    "previous", "read more", "learn more", "see all", "view all",
    "categories", "tags", "archive", "sitemap", "faq", "help",
    "resources", "products", "services", "pricing", "features",
    "solutions", "company", "careers", "press", "media",
}

_GENERIC_BLOCKLIST = {
    "admin", "administrator", "editor", "staff", "team", "contributor",
    "guest", "anonymous", "author", "writer", "editorial", "editorial team",
    "staff writer", "guest author", "guest contributor", "the team",
    "marketing team", "content team", "editorial staff",
}

_JUNK_CHARS_RE = re.compile(r"[<>@#$%^&*(){}[\]|\\/:;]")
_URL_RE = re.compile(r"https?://|www\.|\.com|\.org|\.net")
_EMAIL_RE = re.compile(r"\S+@\S+\.\S+")


def _is_valid_author_name(name: str, domain: str = "") -> bool:
    """Return True if name looks like a real human author name."""
    if not name or not name.strip():
        return False

    name = name.strip()

    # Length checks
    if len(name) > 60:
        return False

    words = name.split()
    if len(words) > 4 or len(words) < 2:
        return False

    # Blocklist checks (case-insensitive)
    lower = name.lower().strip()
    if lower in _NAV_BLOCKLIST or lower in _GENERIC_BLOCKLIST:
        return False

    # Check if name matches domain (brand name, not an author)
    if domain:
        domain_base = domain.replace("www.", "").split(".")[0].lower()
        name_compressed = lower.replace(" ", "").replace("-", "")
        if name_compressed == domain_base or domain_base == name_compressed:
            return False

    # Reject strings with URLs, emails, or special characters
    if _JUNK_CHARS_RE.search(name):
        return False
    if _URL_RE.search(name):
        return False
    if _EMAIL_RE.search(name):
        return False

    # Each word should start with a capital letter (basic name heuristic)
    # Allow short connectors like "de", "van", "von", "el", "al", "di", "le"
    connectors = {"de", "van", "von", "el", "al", "di", "le", "la", "del", "der", "den", "das", "do", "da", "and", "of"}
    for word in words:
        if word.lower() in connectors:
            continue
        if not word[0].isupper():
            return False

    return True


def _extract_domain(page_url: str) -> str:
    """Extract bare domain from a URL."""
    from urllib.parse import urlparse
    parsed = urlparse(page_url)
    return parsed.netloc or ""


# ---------------------------------------------------------------------------
# Author extraction
# ---------------------------------------------------------------------------

def extract_author(soup: BeautifulSoup, page_url: str) -> AuthorInfo:
    """Try multiple strategies to find the article author."""
    base = get_base_url(page_url)
    domain = _extract_domain(page_url)

    # 1. <meta name="author">
    meta = soup.find("meta", attrs={"name": "author"})
    if meta and meta.get("content", "").strip():
        name = meta["content"].strip()
        if _is_valid_author_name(name, domain):
            return AuthorInfo(name=name)

    # 2. JSON-LD schema
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            items = data if isinstance(data, list) else [data]
            for item in items:
                if item.get("@type") in ("Article", "NewsArticle", "BlogPosting", "WebPage"):
                    author = item.get("author")
                    if isinstance(author, list):
                        author = author[0] if author else None
                    if isinstance(author, dict):
                        name = author.get("name", "")
                        url = author.get("url", "")
                        if name and _is_valid_author_name(name, domain):
                            return AuthorInfo(name=name, url=url)
                    elif isinstance(author, str) and author:
                        if _is_valid_author_name(author, domain):
                            return AuthorInfo(name=author)
        except (json.JSONDecodeError, TypeError, KeyError):
            continue

    # 3. Common CSS selectors
    selectors = [
        "[rel='author']",
        ".author-name", ".author a", ".byline a", ".post-author a",
        ".entry-author a", ".article-author a", ".contributor a",
        ".author", ".byline", ".post-author", ".entry-author",
    ]
    for sel in selectors:
        el = soup.select_one(sel)
        if el:
            name = el.get_text(strip=True)
            href = el.get("href", "")
            if name and _is_valid_author_name(name, domain):
                url = make_absolute(base, href) if href else ""
                return AuthorInfo(name=name, url=url)

    # 4. Look for "By <name>" pattern near article top
    for tag in soup.find_all(["p", "span", "div", "a"], limit=50):
        text = tag.get_text(strip=True)
        m = re.match(r"^[Bb]y\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})$", text)
        if m:
            candidate = m.group(1)
            if _is_valid_author_name(candidate, domain):
                href = tag.get("href", "")
                url = make_absolute(base, href) if href else ""
                return AuthorInfo(name=candidate, url=url)

    return AuthorInfo()


# ---------------------------------------------------------------------------
# Contact / affiliate program detection
# ---------------------------------------------------------------------------

AFFILIATE_KEYWORDS = [
    "advertise", "advertising", "partner", "partnerships", "affiliate",
    "sponsor", "sponsorship", "work with us", "media kit", "mediakit",
    "become a partner", "join our program",
]

CONTACT_KEYWORDS = [
    "contact us", "contact", "get in touch", "reach out",
]

COMMON_PATHS = [
    "/advertise", "/advertising", "/partners", "/partnerships",
    "/affiliate", "/affiliate-program", "/affiliates",
    "/sponsor", "/sponsorship", "/media-kit",
    "/contact", "/contact-us",
]


def detect_contact_method(soup: BeautifulSoup, page_url: str, scraper: Scraper) -> ContactInfo:
    """Scan page links and common paths to find the best contact method."""
    base = get_base_url(page_url)

    # 1. Scan <a> tags on the page for affiliate/partner links
    for a_tag in soup.find_all("a", href=True):
        link_text = a_tag.get_text(strip=True).lower()
        href = a_tag["href"].lower()
        combined = f"{link_text} {href}"

        for kw in AFFILIATE_KEYWORDS:
            if kw in combined:
                url = make_absolute(base, a_tag["href"])
                return ContactInfo(
                    contact_type="affiliate_form",
                    contact_form_url=url,
                    notes=f"Found affiliate/partner link: '{a_tag.get_text(strip=True)}'",
                )

    # 2. Check common paths on the domain
    for path in COMMON_PATHS:
        test_url = base + path
        if scraper.check_url_exists(test_url):
            is_affiliate = any(kw in path for kw in ["advertis", "partner", "affiliate", "sponsor", "media"])
            ct = "affiliate_form" if is_affiliate else "contact_form"
            return ContactInfo(
                contact_type=ct,
                contact_form_url=test_url,
                notes=f"Found via path check: {path}",
            )
        rate_limit()

    # 3. Scan for general contact links
    for a_tag in soup.find_all("a", href=True):
        link_text = a_tag.get_text(strip=True).lower()
        for kw in CONTACT_KEYWORDS:
            if kw in link_text:
                url = make_absolute(base, a_tag["href"])
                return ContactInfo(
                    contact_type="contact_form",
                    contact_form_url=url,
                    notes=f"Found contact link: '{a_tag.get_text(strip=True)}'",
                )

    return ContactInfo(contact_type="direct_contact", notes="No form found; manual outreach needed")


# ---------------------------------------------------------------------------
# Company name extraction
# ---------------------------------------------------------------------------

def extract_company_name(soup: BeautifulSoup, domain: str) -> str:
    """Extract the site/company name from known sites, meta tags, or domain."""
    from classifier import get_site_name

    # 1. Use known site name when available (most reliable)
    known = get_site_name(domain)
    if known:
        return known

    # 2. og:site_name meta tag
    og = soup.find("meta", property="og:site_name")
    if og and og.get("content", "").strip():
        return og["content"].strip()

    # 3. JSON-LD Organization/WebSite name
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            items = data if isinstance(data, list) else [data]
            for item in items:
                if item.get("@type") in ("Organization", "WebSite"):
                    name = item.get("name", "")
                    if name:
                        return name
        except (json.JSONDecodeError, TypeError):
            continue

    # 4. Domain-based fallback with proper casing
    name = domain.replace("www.", "").split(".")[0]
    return name.replace("-", " ").title()


# ---------------------------------------------------------------------------
# Team / about page extraction
# ---------------------------------------------------------------------------

ABOUT_PATHS = ["/about", "/about-us", "/team", "/our-team", "/people", "/staff"]

MARKETING_KEYWORDS = [
    "marketing", "digital marketing", "growth", "partnerships",
    "content", "seo", "communications", "business development",
]


def find_team_contacts(page_url: str, scraper: Scraper) -> tuple[str, list[TeamContact]]:
    """Check about/team pages for marketing-related contacts."""
    base = get_base_url(page_url)
    contacts = []
    about_url = ""

    for path in ABOUT_PATHS:
        test_url = base + path
        if scraper.check_url_exists(test_url):
            about_url = test_url
            rate_limit()
            soup = scraper.fetch_page(test_url)
            if soup:
                contacts = _extract_marketing_people(soup, test_url)
            break
        rate_limit()

    return about_url, contacts


_JUNK_TEXT_PATTERNS = [
    # Cookie consent language
    "we use cookies", "accept all", "cookie policy", "cookie settings",
    "cookie preferences", "manage cookies", "cookies help us",
    "by continuing", "consent to cookies", "this website uses cookies",
    "we and our partners", "accept cookies", "reject all",
    # Legal boilerplate
    "privacy policy", "terms of service", "terms of use",
    "terms and conditions", "all rights reserved", "copyright ©",
    "gdpr", "data protection", "legal notice", "disclaimer",
    # Other non-contact junk
    "subscribe to", "sign up for", "newsletter", "unsubscribe",
    "follow us on", "share this", "powered by",
]


def _is_junk_element(text: str) -> bool:
    """Return True if text looks like cookie banner, legal, or other junk."""
    lower = text.lower()
    return any(pat in lower for pat in _JUNK_TEXT_PATTERNS)


def _is_junk_role(role: str) -> bool:
    """Return True if the role text is junk rather than a real job title."""
    if len(role) > 100:
        return True
    lower = role.lower()
    return any(pat in lower for pat in _JUNK_TEXT_PATTERNS)


def _extract_marketing_people(soup: BeautifulSoup, page_url: str) -> list[TeamContact]:
    """Scan a team/about page for people with marketing-related roles."""
    contacts = []

    for el in soup.find_all(["div", "li", "section", "article"], limit=200):
        text = el.get_text(separator=" ", strip=True)
        lower_text = text.lower()

        if not any(kw in lower_text for kw in MARKETING_KEYWORDS):
            continue

        # Skip elements that are cookie banners, legal text, etc.
        if _is_junk_element(text):
            continue

        lines = el.get_text(separator="\n", strip=True).split("\n")
        name = ""
        role = ""
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if any(kw in line.lower() for kw in MARKETING_KEYWORDS):
                if not _is_junk_role(line):
                    role = line
            elif re.match(r"^[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3}$", line) and len(line) < 40:
                name = line
        if name and role:
            contacts.append(TeamContact(name=name, role=role))
            if len(contacts) >= 5:
                break

    return contacts


# ---------------------------------------------------------------------------
# LinkedIn search URL
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Affiliate instructions extraction
# ---------------------------------------------------------------------------

_AFFILIATE_INSTRUCTION_KEYWORDS = [
    "submit", "list your", "get listed", "add your", "claim your",
    "sign up", "register", "apply", "join", "enroll",
    "partner program", "affiliate program", "vendor program",
    "advertise with", "sponsor", "media kit",
    "pricing", "cost", "rate", "package", "tier", "plan",
    "requirements", "eligibility", "criteria", "qualify",
    "review process", "turnaround", "approval",
    "contact us", "get in touch", "reach out", "email us",
    "affiliate network", "impact", "shareasale", "cj affiliate",
    "awin", "partnerize", "rakuten",
]


def extract_affiliate_instructions(contact_form_url: str, scraper: Scraper) -> str:
    """Scrape the partner/advertise page and extract instructions for getting listed.

    Returns a concise summary of the submission process, pricing, requirements,
    and contact info found on the page.
    """
    if not contact_form_url:
        return ""

    rate_limit()
    soup = scraper.fetch_page(contact_form_url)
    if not soup:
        return f"Partner page at {contact_form_url} could not be fetched"

    instructions_parts = []

    # Check if the page has a form
    forms = soup.find_all("form")
    if forms:
        form_fields = []
        for form in forms[:3]:
            for inp in form.find_all(["input", "select", "textarea"], limit=20):
                label = (
                    inp.get("placeholder", "")
                    or inp.get("aria-label", "")
                    or inp.get("name", "")
                )
                if label and label.lower() not in ("submit", "csrf", "token", "hidden"):
                    form_fields.append(label)
        if form_fields:
            instructions_parts.append(
                f"Online form submission at {contact_form_url}. "
                f"Fields: {', '.join(form_fields[:10])}"
            )
        else:
            instructions_parts.append(f"Online form submission at {contact_form_url}")

    # Extract relevant text blocks from the page
    relevant_blocks = []
    for el in soup.find_all(
        ["p", "li", "h2", "h3", "h4", "div", "span", "td"], limit=300
    ):
        text = el.get_text(separator=" ", strip=True)
        if not text or len(text) < 15 or len(text) > 500:
            continue
        lower = text.lower()
        # Skip junk
        if any(junk in lower for junk in _JUNK_TEXT_PATTERNS):
            continue
        # Check if the text contains relevant keywords
        if any(kw in lower for kw in _AFFILIATE_INSTRUCTION_KEYWORDS):
            # Avoid duplicates (substring check)
            if not any(text in existing for existing in relevant_blocks):
                relevant_blocks.append(text)

    # Deduplicate and limit
    if relevant_blocks:
        # Take most relevant blocks, cap total length
        summary_parts = []
        total_len = 0
        for block in relevant_blocks[:8]:
            if total_len + len(block) > 800:
                break
            summary_parts.append(block)
            total_len += len(block)
        if summary_parts:
            instructions_parts.append(" | ".join(summary_parts))

    # Look for email addresses on the page
    email_matches = set()
    page_text = soup.get_text()
    for match in re.finditer(r"[\w.+-]+@[\w-]+\.[\w.-]+", page_text):
        email = match.group(0)
        # Skip common junk emails
        if not any(
            junk in email.lower()
            for junk in ["@example", "@sentry", "@wix", "noreply", "no-reply", "@2x"]
        ):
            email_matches.add(email)
    if email_matches:
        instructions_parts.append(f"Contact email(s): {', '.join(sorted(email_matches)[:3])}")

    if not instructions_parts:
        return f"Partner/advertise page found at {contact_form_url} but no specific instructions extracted"

    return ". ".join(instructions_parts)


def generate_email_candidates(author_name: str, domain: str) -> str:
    """Generate candidate email addresses from author name and domain.

    Returns a semicolon-separated string of candidate emails using common
    corporate email patterns.
    """
    if not author_name or not domain:
        return ""

    # Clean domain: strip www. prefix
    domain = domain.replace("www.", "")

    # Parse author name into parts, ignoring connectors
    connectors = {"de", "van", "von", "el", "al", "di", "le", "la", "del", "der", "den", "das", "do", "da", "and", "of"}
    parts = [p.lower() for p in author_name.split() if p.lower() not in connectors]
    if len(parts) < 2:
        return ""

    first = parts[0]
    last = parts[-1]
    first_initial = first[0]
    last_initial = last[0]

    candidates = [
        f"{first}@{domain}",
        f"{first}.{last}@{domain}",
        f"{first}{last}@{domain}",
        f"{first_initial}{last}@{domain}",
        f"{first}{last_initial}@{domain}",
        f"{first}_{last}@{domain}",
        f"{last}@{domain}",
        f"{first_initial}.{last}@{domain}",
    ]

    return "; ".join(candidates)


def build_linkedin_search_url(company_name: str, author_name: str = "") -> str:
    """Build a LinkedIn people-search URL.

    When an author name is available, search for that person at the company.
    Otherwise fall back to a general marketing/partnerships search.
    """
    if author_name:
        query = f"{author_name} {company_name}"
    else:
        query = f"{company_name} marketing OR partnerships OR digital"
    return f"https://www.linkedin.com/search/results/people/?keywords={quote_plus(query)}"


def build_linkedin_profile_url(author_name: str) -> str:
    """Attempt to construct a likely LinkedIn profile URL from an author name.

    LinkedIn profile slugs are typically lowercase first-last or firstname-lastname.
    Returns a best-guess URL (not guaranteed to resolve).
    """
    if not author_name:
        return ""
    connectors = {"de", "van", "von", "el", "al", "di", "le", "la", "del", "der", "den", "das", "do", "da", "and", "of"}
    parts = [p.lower() for p in author_name.split() if p.lower() not in connectors]
    if len(parts) < 2:
        return ""
    slug = "-".join(parts)
    return f"https://www.linkedin.com/in/{slug}"
