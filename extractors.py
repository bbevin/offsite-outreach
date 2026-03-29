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
    """Extract the site/company name from meta tags or title."""
    og = soup.find("meta", property="og:site_name")
    if og and og.get("content", "").strip():
        return og["content"].strip()

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

def build_linkedin_search_url(company_name: str) -> str:
    query = f"{company_name} marketing OR partnerships OR digital"
    return f"https://www.linkedin.com/search/results/people/?keywords={quote_plus(query)}"
