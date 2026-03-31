"""Tests for extractors.py — author, contact, company, email, LinkedIn, affiliate extraction."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import MagicMock, patch
from bs4 import BeautifulSoup

from extractors import (
    _is_valid_author_name,
    extract_author,
    extract_company_name,
    generate_email_candidates,
    build_linkedin_search_url,
    build_linkedin_profile_url,
    detect_affiliate_networks,
    _is_junk_element,
    _is_junk_role,
)


# ── Author name validation ───────────────────────────────────────────────


class TestIsValidAuthorName:

    @pytest.mark.parametrize("name", [
        "John Smith",
        "Jane Doe",
        "Maria Garcia Lopez",
        "Jean Pierre Dupont",
    ])
    def test_valid_names(self, name):
        assert _is_valid_author_name(name) is True

    @pytest.mark.parametrize("name", [
        "Home",          # nav term (1 word)
        "Menu",          # nav term (1 word)
        "admin",         # generic (1 word)
        "",              # empty
        "   ",           # whitespace
    ])
    def test_rejects_single_words(self, name):
        assert _is_valid_author_name(name) is False

    @pytest.mark.parametrize("name", [
        "Skip To Content",
        "Read More",
        "Learn More",
    ])
    def test_rejects_nav_phrases(self, name):
        # These are in blocklist (case-insensitive)
        assert _is_valid_author_name(name) is False

    @pytest.mark.parametrize("name", [
        "Editorial Team",
        "Staff Writer",
        "Guest Contributor",
        "The Team",
    ])
    def test_rejects_generic_author_phrases(self, name):
        assert _is_valid_author_name(name) is False

    def test_rejects_urls(self):
        assert _is_valid_author_name("https://example.com") is False

    def test_rejects_emails(self):
        assert _is_valid_author_name("john@example.com") is False

    def test_rejects_special_chars(self):
        assert _is_valid_author_name("John <script>") is False
        assert _is_valid_author_name("John $mith") is False

    def test_rejects_too_long(self):
        assert _is_valid_author_name("A" * 61 + " B") is False

    def test_rejects_more_than_4_words(self):
        assert _is_valid_author_name("One Two Three Four Five") is False

    def test_rejects_lowercase_start(self):
        assert _is_valid_author_name("john Smith") is False

    def test_allows_connectors(self):
        assert _is_valid_author_name("Ludwig van Beethoven") is True
        assert _is_valid_author_name("Carlos de Silva") is True

    def test_rejects_domain_match(self):
        assert _is_valid_author_name("Capsulecrm", domain="capsulecrm.com") is False

    def test_rejects_domain_match_with_spaces(self):
        # "boring business nerd" compressed == "boringbusinessnerd" == domain base
        assert _is_valid_author_name("Boring Business Nerd", domain="boringbusinessnerd.com") is False


# ── Author extraction ────────────────────────────────────────────────────


class TestExtractAuthor:

    def test_meta_author(self):
        html = '<html><head><meta name="author" content="Jane Smith"></head><body></body></html>'
        soup = BeautifulSoup(html, "html.parser")
        author = extract_author(soup, "https://example.com/article")
        assert author.name == "Jane Smith"

    def test_json_ld_author(self):
        html = '''<html><head>
        <script type="application/ld+json">
        {"@type": "Article", "author": {"@type": "Person", "name": "Bob Jones", "url": "https://example.com/bob"}}
        </script>
        </head><body></body></html>'''
        soup = BeautifulSoup(html, "html.parser")
        author = extract_author(soup, "https://example.com/article")
        assert author.name == "Bob Jones"
        assert author.url == "https://example.com/bob"

    def test_json_ld_author_string(self):
        html = '''<html><head>
        <script type="application/ld+json">
        {"@type": "BlogPosting", "author": "Alice Park"}
        </script>
        </head><body></body></html>'''
        soup = BeautifulSoup(html, "html.parser")
        author = extract_author(soup, "https://example.com/post")
        assert author.name == "Alice Park"

    def test_css_selector_author(self):
        html = '<html><body><span class="author-name">Carlos Rivera</span></body></html>'
        soup = BeautifulSoup(html, "html.parser")
        author = extract_author(soup, "https://example.com/article")
        assert author.name == "Carlos Rivera"

    def test_byline_pattern(self):
        html = '<html><body><span>By Sarah Chen</span></body></html>'
        soup = BeautifulSoup(html, "html.parser")
        author = extract_author(soup, "https://example.com/article")
        assert author.name == "Sarah Chen"

    def test_rejects_junk_author_name(self):
        html = '<html><head><meta name="author" content="Home"></head><body></body></html>'
        soup = BeautifulSoup(html, "html.parser")
        author = extract_author(soup, "https://example.com/article")
        assert author.name == ""

    def test_no_author_returns_empty(self):
        html = "<html><body><p>Just some content.</p></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        author = extract_author(soup, "https://example.com/article")
        assert author.name == ""
        assert author.url == ""


# ── Company name extraction ──────────────────────────────────────────────


class TestExtractCompanyName:

    def test_known_site_name(self):
        html = "<html><body></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        assert extract_company_name(soup, "pcmag.com") == "PCMag"

    def test_og_site_name(self):
        html = '<html><head><meta property="og:site_name" content="Cool Blog"></head><body></body></html>'
        soup = BeautifulSoup(html, "html.parser")
        assert extract_company_name(soup, "unknownsite.com") == "Cool Blog"

    def test_json_ld_organization(self):
        html = '''<html><head>
        <script type="application/ld+json">
        {"@type": "Organization", "name": "Acme Corp"}
        </script>
        </head><body></body></html>'''
        soup = BeautifulSoup(html, "html.parser")
        assert extract_company_name(soup, "unknownsite2.com") == "Acme Corp"

    def test_domain_fallback(self):
        html = "<html><body></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        result = extract_company_name(soup, "cool-widgets.com")
        assert result == "Cool Widgets"


# ── Email candidate generation ────────────────────────────────────────────


class TestGenerateEmailCandidates:

    def test_basic_generation(self):
        result = generate_email_candidates("John Smith", "example.com")
        candidates = result.split("; ")
        assert "john@example.com" in candidates
        assert "john.smith@example.com" in candidates
        assert "johnsmith@example.com" in candidates
        assert "jsmith@example.com" in candidates
        assert "johns@example.com" in candidates
        assert "john_smith@example.com" in candidates
        assert "smith@example.com" in candidates
        assert "j.smith@example.com" in candidates

    def test_strips_www(self):
        result = generate_email_candidates("Jane Doe", "www.example.com")
        assert "jane@example.com" in result

    def test_ignores_connectors(self):
        result = generate_email_candidates("Ludwig van Beethoven", "music.com")
        candidates = result.split("; ")
        assert "ludwig@music.com" in candidates
        assert "ludwig.beethoven@music.com" in candidates

    def test_empty_name(self):
        assert generate_email_candidates("", "example.com") == ""

    def test_empty_domain(self):
        assert generate_email_candidates("John Smith", "") == ""

    def test_single_name_returns_empty(self):
        assert generate_email_candidates("Madonna", "example.com") == ""


# ── LinkedIn URL building ────────────────────────────────────────────────


class TestBuildLinkedinSearchUrl:

    def test_author_targeted_search(self):
        url = build_linkedin_search_url("Acme Corp", author_name="John Smith")
        assert "John+Smith" in url or "John%20Smith" in url
        assert "Acme" in url

    def test_generic_search_without_author(self):
        url = build_linkedin_search_url("Acme Corp")
        assert "marketing" in url or "partnerships" in url

    def test_returns_linkedin_url(self):
        url = build_linkedin_search_url("Test Co")
        assert url.startswith("https://www.linkedin.com/search/results/people/")


class TestBuildLinkedinProfileUrl:

    def test_basic_profile(self):
        url = build_linkedin_profile_url("John Smith")
        assert url == "https://www.linkedin.com/in/john-smith"

    def test_ignores_connectors(self):
        url = build_linkedin_profile_url("Carlos de Silva")
        assert url == "https://www.linkedin.com/in/carlos-silva"

    def test_empty_name(self):
        assert build_linkedin_profile_url("") == ""

    def test_single_name_returns_empty(self):
        assert build_linkedin_profile_url("Madonna") == ""


# ── Affiliate network detection ──────────────────────────────────────────


class TestDetectAffiliateNetworks:

    def _make_soup(self, html):
        return BeautifulSoup(html, "html.parser")

    def test_detects_impact(self):
        soup = self._make_soup('<html><body><a href="https://tracking.impact.com/foo">link</a></body></html>')
        result = detect_affiliate_networks(soup)
        assert "Impact" in result

    def test_detects_shareasale(self):
        soup = self._make_soup('<html><body><a href="https://shareasale.com/r/123">link</a></body></html>')
        result = detect_affiliate_networks(soup)
        assert "ShareASale" in result

    def test_detects_cj(self):
        soup = self._make_soup('<html><body><a href="https://anrdoezrs.net/click">link</a></body></html>')
        result = detect_affiliate_networks(soup)
        assert "CJ Affiliate" in result

    def test_detects_from_text(self):
        soup = self._make_soup('<html><body><p>We use the Awin affiliate network.</p></body></html>')
        result = detect_affiliate_networks(soup)
        assert "Awin" in result

    def test_detects_from_script_src(self):
        soup = self._make_soup('<html><body><script src="https://go.skimresources.com/tracker.js"></script></body></html>')
        result = detect_affiliate_networks(soup)
        assert "Skimlinks" in result

    def test_multiple_networks(self):
        soup = self._make_soup('''<html><body>
        <a href="https://tracking.impact.com/a">link</a>
        <a href="https://shareasale.com/b">link</a>
        </body></html>''')
        result = detect_affiliate_networks(soup)
        assert "Impact" in result
        assert "ShareASale" in result

    def test_no_networks(self):
        soup = self._make_soup('<html><body><a href="https://example.com">link</a></body></html>')
        assert detect_affiliate_networks(soup) == ""

    def test_partner_soup_also_scanned(self):
        main_soup = self._make_soup("<html><body></body></html>")
        partner_soup = self._make_soup('<html><body><a href="https://awin1.com/link">link</a></body></html>')
        result = detect_affiliate_networks(main_soup, partner_soup)
        assert "Awin" in result


# ── Junk text filtering ──────────────────────────────────────────────────


class TestJunkFiltering:

    @pytest.mark.parametrize("text", [
        "We use cookies to improve your experience",
        "Accept All Cookies",
        "Privacy Policy | Terms of Service",
        "Subscribe to our newsletter",
        "Copyright © 2026 All Rights Reserved",
    ])
    def test_junk_elements_detected(self, text):
        assert _is_junk_element(text) is True

    def test_real_content_not_junk(self):
        assert _is_junk_element("Sarah Chen, VP of Marketing") is False

    def test_junk_role_too_long(self):
        assert _is_junk_role("A" * 101) is True

    def test_junk_role_cookie_text(self):
        assert _is_junk_role("We use cookies to improve experience") is True

    def test_valid_role(self):
        assert _is_junk_role("VP of Marketing") is False
