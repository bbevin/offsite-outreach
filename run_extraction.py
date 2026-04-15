import csv
import sys
import time
import hashlib
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

# Patch extractors to track which strategy fires
import extractors as ext_module


def _split_author_name(full_name: str) -> tuple[str, str]:
    """Split 'First Last' into ('First', 'Last')."""
    parts = full_name.strip().split(None, 1)
    if not parts:
        return "", ""
    return parts[0], parts[1] if len(parts) > 1 else ""


def infer_page_type(url: str) -> str:
    """Infer page type from URL path patterns."""
    parsed = urlparse(url)
    path = parsed.path.lower()
    domain = parsed.netloc.replace("www.", "").lower()

    # Social / community
    social_domains = {"reddit.com", "youtube.com", "linkedin.com", "twitter.com",
                      "facebook.com", "instagram.com", "quora.com", "medium.com"}
    if any(s in domain for s in social_domains):
        return "social"

    # Wikipedia
    if "wikipedia.org" in domain:
        return "reference"

    # Marketplace / ecommerce
    if "etsy.com" in domain:
        return "ecommerce"
    ecommerce_patterns = ["/products/", "/product/", "/shop/", "/listing/",
                          "/seller/", "/sales/", "/cart", "/checkout"]
    if any(p in path for p in ecommerce_patterns):
        return "ecommerce"

    # Blog / article
    article_patterns = ["/blog/", "/blogs/", "/article/", "/articles/",
                        "/post/", "/posts/", "/news/", "/magazine/",
                        "/resources/", "/guides/", "/guide/", "/reviews/",
                        "/review/", "/tips/", "/learn/"]
    if any(p in path for p in article_patterns):
        return "article"

    # Substack is always articles
    if "substack.com" in domain:
        return "article"

    # Landing / product pages
    landing_patterns = ["/features/", "/pricing/", "/plans/", "/solutions/",
                        "/use-case/", "/use-cases/", "/industries/",
                        "/comparisons/", "/compare/"]
    if any(p in path for p in landing_patterns):
        return "landing_page"

    # Vendor homepages (path is / or empty)
    if path in ("", "/"):
        return "homepage"

    return "unknown"

_rule_count = 0
_llm_count = 0
_empty_count = 0

_orig_llm = ext_module._llm_extract_author

def _patched_llm(soup, page_url):
    result = _orig_llm(soup, page_url)
    return result  # tracking happens in extract_author wrapper

from models import AuthorInfo
from bs4 import BeautifulSoup
from scraper import Scraper, get_base_url, rate_limit

# Patch extract_author to track fallback usage
_orig_extract = ext_module.extract_author

def _tracked_extract(soup, page_url):
    global _rule_count, _llm_count, _empty_count
    # Run strategies 1-4 manually to see if rules suffice
    from extractors import (
        _clean_author_text, _is_valid_author_name, _extract_domain,
        _llm_extract_author
    )
    import json
    from scraper import make_absolute, get_base_url

    base = get_base_url(page_url)
    domain = _extract_domain(page_url)

    # Strategy 1: meta author
    meta = soup.find("meta", attrs={"name": "author"})
    if meta and meta.get("content", "").strip():
        name = _clean_author_text(meta["content"].strip())
        if _is_valid_author_name(name, domain):
            _rule_count += 1
            return AuthorInfo(name=name)

    # Strategy 2: JSON-LD
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            items = data if isinstance(data, list) else [data]
            for item in items:
                if item.get("@type") in ("Article", "NewsArticle", "BlogPosting", "WebPage"):
                    author = item.get("author")
                    if isinstance(author, list): author = author[0] if author else None
                    if isinstance(author, dict):
                        name = author.get("name", "")
                        url = author.get("url", "")
                        if name and _is_valid_author_name(_clean_author_text(name), domain):
                            _rule_count += 1
                            return AuthorInfo(name=_clean_author_text(name), url=url)
                    elif isinstance(author, str) and author:
                        cleaned = _clean_author_text(author)
                        if _is_valid_author_name(cleaned, domain):
                            _rule_count += 1
                            return AuthorInfo(name=cleaned)
        except:
            continue

    # Strategy 3: CSS selectors
    selectors = [
        "[rel='author']", ".author-name", ".author a", ".byline a", ".post-author a",
        ".entry-author a", ".article-author a", ".contributor a",
        "[class*='author'] [class*='name']",
        ".author", ".byline", ".post-author", ".entry-author", "[class*='author']",
    ]
    _nav_classes = {"breadcrumb", "nav", "menu", "sidebar", "footer", "header-nav", "navigation"}
    for sel in selectors:
        el = soup.select_one(sel)
        if el:
            el_classes = {c.lower() for c in el.get("class", [])}
            if el_classes & _nav_classes:
                continue
            name = el.get_text(strip=True)
            href = el.get("href", "")
            cleaned = _clean_author_text(name)
            if cleaned and _is_valid_author_name(cleaned, domain):
                url = make_absolute(base, href) if href else ""
                _rule_count += 1
                return AuthorInfo(name=cleaned, url=url)
            if not _is_valid_author_name(cleaned, domain):
                for child in el.find_all(["a","span","p","div","strong","em"], recursive=True):
                    child_text = _clean_author_text(child.get_text(strip=True))
                    if child_text and _is_valid_author_name(child_text, domain):
                        child_href = child.get("href", "") or href
                        url = make_absolute(base, child_href) if child_href else ""
                        _rule_count += 1
                        return AuthorInfo(name=child_text, url=url)

    # Strategy 4: By pattern
    _menu_classes = {"mega-menu","nav","menu","sidebar","footer","breadcrumb","navigation","header-nav","tab-content"}
    _camelcase_re = re.compile(r"[a-z][A-Z]")
    for tag in soup.find_all(["p","span","div","a"], limit=200):
        tag_classes = " ".join(tag.get("class",[]) + [c for p in tag.parents for c in (p.get("class") or [])]).lower()
        if any(mc in tag_classes for mc in _menu_classes):
            continue
        text = tag.get_text(strip=True)
        m = re.match(r"^[Bb]y\s+([A-Z][a-z]+(?:[-\s]+[A-Z][a-z]+){1,3})(?:\s*,.*)?$", text)
        if m:
            candidate = m.group(1)
            if _is_valid_author_name(candidate, domain):
                _rule_count += 1
                return AuthorInfo(name=candidate)

    # Strategy 5: LLM fallback
    result = _llm_extract_author(soup, page_url)
    if result.name:
        _llm_count += 1
    else:
        _empty_count += 1
    return result

ext_module.extract_author = _tracked_extract

# --- Main script ---
SKIP_PAGE_TYPES = {"social", "ecommerce", "landing_page", "reference", "homepage"}

scraper = Scraper()
results = []

with open("input.csv") as f:
    rows = list(csv.DictReader(f))

total = len(rows)
print(f"Processing {total} URLs...", flush=True)

for i, row in enumerate(rows, 1):
    url = row["url"].strip()

    # Skip non-article page types
    page_type = infer_page_type(url)
    if page_type in SKIP_PAGE_TYPES:
        results.append({**row, "author_first_name": "", "author_last_name": "", "author_url": "", "extraction_method": "skipped", "page_type": page_type})
        print(f"[{i}/{total}] SKIP  [{page_type}]  {url}", flush=True)
        continue

    try:
        rate_limit()
        soup = scraper.fetch_page(url)
        # Prefer DataForSEO's page_type; fall back to URL inference
        page_type = infer_page_type(url)
        if not soup:
            results.append({**row, "author_first_name": "", "author_last_name": "", "author_url": "", "extraction_method": "fetch_failed", "page_type": page_type})
            print(f"[{i}/{total}] FAIL  [{page_type}]  {url}", flush=True)
            continue
        before_rule = _rule_count
        before_llm  = _llm_count
        info = ext_module.extract_author(soup, url)

        if _rule_count > before_rule:
            method = "rule"
        elif _llm_count > before_llm:
            method = "llm"
        else:
            method = "none"

        first, last = _split_author_name(info.name or "")
        results.append({**row, "author_first_name": first, "author_last_name": last, "author_url": info.url or "", "extraction_method": method, "page_type": page_type})
        print(f"[{i}/{total}] {method.upper():4s}  {info.name or '(none)':30s}  [{page_type}]  {url}", flush=True)

    except Exception as e:
        results.append({**row, "author_first_name": "", "author_last_name": "", "author_url": "", "extraction_method": "error", "page_type": infer_page_type(url)})
        print(f"[{i}/{total}] ERR   {e}  {url}", flush=True)

# Write output
ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
outfile = f"test_results/author_extraction_all_{ts}.csv"
fieldnames = list(rows[0].keys()) + ["author_first_name", "author_last_name", "author_url", "extraction_method", "page_type"]
with open(outfile, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(results)

# Summary
rule_hits  = sum(1 for r in results if r["extraction_method"] == "rule")
llm_hits   = sum(1 for r in results if r["extraction_method"] == "llm")
none_hits  = sum(1 for r in results if r["extraction_method"] == "none")
skipped    = sum(1 for r in results if r["extraction_method"] == "skipped")
failed     = sum(1 for r in results if r["extraction_method"] in ("fetch_failed","error"))

print(f"\n{'='*50}")
print(f"Results saved to {outfile}")
print(f"  Total URLs:    {total}")
print(f"  Skipped:       {skipped}")
print(f"  Fetch failed:  {failed}")
print(f"  Rule-based:    {rule_hits}")
print(f"  LLM fallback:  {llm_hits}")
print(f"  No author:     {none_hits}")
