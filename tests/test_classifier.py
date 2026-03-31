"""Tests for classifier.py — site classification logic."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from bs4 import BeautifulSoup

from classifier import (
    classify_site,
    classify_site_with_content,
    get_site_name,
    _detect_affiliate_disclosure,
    _detect_affiliate_links,
    _detect_affiliate_content_structure,
    _detect_vendor_blog,
)


# ── classify_site (static known-list lookup) ──────────────────────────────


class TestClassifySite:
    """Static domain-to-type classification."""

    @pytest.mark.parametrize("domain,expected", [
        ("g2.com", "Affiliate/Review"),
        ("capterra.com", "Affiliate/Review"),
        ("pcmag.com", "Affiliate/Review"),
        ("techradar.com", "Affiliate/Review"),
        ("forbes.com", "Affiliate/Review"),
        ("nerdwallet.com", "Affiliate/Review"),
        ("crm.org", "Affiliate/Review"),
        ("reddit.com", "Affiliate/Review"),
        ("wirecutter.com", "Affiliate/Review"),
        ("boringbusinessnerd.com", "Affiliate/Review"),
    ])
    def test_known_affiliate_sites(self, domain, expected):
        assert classify_site(domain) == expected

    @pytest.mark.parametrize("domain,expected", [
        ("capsulecrm.com", "Vendor Blog"),
        ("salesflare.com", "Vendor Blog"),
        ("blog.salesflare.com", "Vendor Blog"),
    ])
    def test_known_outreach_sites(self, domain, expected):
        assert classify_site(domain) == expected

    @pytest.mark.parametrize("domain,expected", [
        ("uschamber.com", "Outreach"),
        ("nytimes.com", "Outreach"),
    ])
    def test_known_non_affiliate_sites(self, domain, expected):
        assert classify_site(domain) == expected

    def test_www_prefix_stripped(self):
        assert classify_site("www.g2.com") == "Affiliate/Review"
        assert classify_site("www.capsulecrm.com") == "Vendor Blog"
        assert classify_site("www.uschamber.com") == "Outreach"

    def test_unknown_domain_returns_unknown(self):
        assert classify_site("totallyunknown123.com") == "Unknown"

    def test_subdomain_of_known_affiliate(self):
        assert classify_site("reviews.pcmag.com") == "Affiliate/Review"

    def test_subdomain_of_known_outreach(self):
        assert classify_site("blog.capsulecrm.com") == "Vendor Blog"


# ── get_site_name ─────────────────────────────────────────────────────────


class TestGetSiteName:

    def test_known_affiliate(self):
        assert get_site_name("g2.com") == "G2"
        assert get_site_name("pcmag.com") == "PCMag"

    def test_known_outreach(self):
        assert get_site_name("capsulecrm.com") == "Capsule CRM"

    def test_known_non_affiliate(self):
        assert get_site_name("uschamber.com") == "US Chamber of Commerce"

    def test_unknown_returns_none(self):
        assert get_site_name("randomsite.io") is None

    def test_www_stripped(self):
        assert get_site_name("www.forbes.com") == "Forbes Advisor"


# ── _detect_affiliate_disclosure ──────────────────────────────────────────


class TestDetectAffiliateDisclosure:

    def test_detects_commission_language(self):
        assert _detect_affiliate_disclosure("We may earn a commission if you buy through our links.")

    def test_detects_affiliate_links_phrase(self):
        assert _detect_affiliate_disclosure("This page contains affiliate links.")

    def test_no_false_positive_on_normal_text(self):
        assert not _detect_affiliate_disclosure("Our CRM helps you manage customer relationships.")

    def test_case_insensitive(self):
        assert _detect_affiliate_disclosure("AFFILIATE DISCLOSURE: we partner with brands.")


# ── _detect_affiliate_links ──────────────────────────────────────────────


class TestDetectAffiliateLinks:

    def _make_soup(self, links):
        html = "<html><body>"
        for href in links:
            html += f'<a href="{href}">link</a>'
        html += "</body></html>"
        return BeautifulSoup(html, "html.parser")

    def test_detects_redirect_domains(self):
        soup = self._make_soup([
            "https://go.redirectingat.com/foo",
            "https://click.linksynergy.com/bar",
            "https://shareasale.com/baz",
        ])
        assert _detect_affiliate_links(soup) is True

    def test_detects_tracking_params(self):
        soup = self._make_soup([
            "https://example.com/product?ref=abc",
            "https://example.com/product?tag=def",
            "https://example.com/product?aff=ghi",
        ])
        assert _detect_affiliate_links(soup) is True

    def test_detects_redirect_paths(self):
        soup = self._make_soup([
            "https://example.com/go/product1",
            "https://example.com/recommends/product2",
            "https://example.com/out/product3",
        ])
        assert _detect_affiliate_links(soup) is True

    def test_no_false_positive_on_clean_links(self):
        soup = self._make_soup([
            "https://example.com/about",
            "https://example.com/contact",
            "https://google.com",
        ])
        assert _detect_affiliate_links(soup) is False

    def test_threshold_requires_3_links(self):
        soup = self._make_soup([
            "https://go.redirectingat.com/foo",
            "https://click.linksynergy.com/bar",
        ])
        assert _detect_affiliate_links(soup) is False


# ── _detect_affiliate_content_structure ───────────────────────────────────


class TestDetectAffiliateContentStructure:

    def test_detects_best_heading_plus_ctas(self):
        html = """
        <html><body>
        <h1>Best CRM Software for 2026</h1>
        <a href="https://crm1.com">Visit Site</a>
        <a href="https://crm2.com">Try It Free</a>
        <a href="https://crm3.com">Get Started</a>
        </body></html>
        """
        soup = BeautifulSoup(html, "html.parser")
        assert _detect_affiliate_content_structure(soup) is True

    def test_no_false_positive_on_vendor_blog(self):
        html = """
        <html><body>
        <h1>How to Choose a CRM</h1>
        <p>We built Capsule to help small businesses manage contacts.</p>
        <a href="/pricing">See Pricing</a>
        </body></html>
        """
        soup = BeautifulSoup(html, "html.parser")
        assert _detect_affiliate_content_structure(soup) is False


# ── _detect_vendor_blog ───────────────────────────────────────────────────


class TestDetectVendorBlog:

    def test_blog_subdomain(self):
        assert _detect_vendor_blog("blog.salesflare.com") is True
        assert _detect_vendor_blog("blog.example.com") is True

    def test_non_blog_domain(self):
        assert _detect_vendor_blog("salesflare.com") is False
        assert _detect_vendor_blog("www.example.com") is False


# ── classify_site_with_content ────────────────────────────────────────────


class TestClassifySiteWithContent:

    def test_known_affiliate_returns_known_list(self):
        site_type, reason = classify_site_with_content("pcmag.com")
        assert site_type == "Affiliate/Review"
        assert reason == "known_list"

    def test_known_outreach_returns_known_list(self):
        site_type, reason = classify_site_with_content("capsulecrm.com")
        assert site_type == "Vendor Blog"
        assert reason == "known_list"

    def test_unknown_domain_no_content_defaults_outreach(self):
        site_type, reason = classify_site_with_content("randomsite123.com")
        assert site_type == "Outreach"
        assert "unknown_default" in reason

    def test_vendor_blog_domain_pattern(self):
        site_type, reason = classify_site_with_content("blog.unknowncompany.com")
        assert site_type == "Vendor Blog"
        assert reason == "domain_pattern"

    def test_content_signals_disclosure(self):
        html = """
        <html><body>
        <p>We may earn a commission if you buy through our links.</p>
        <p>Some review content here.</p>
        </body></html>
        """
        soup = BeautifulSoup(html, "html.parser")
        site_type, reason = classify_site_with_content("unknownsite.com", soup)
        assert site_type == "Affiliate/Review"
        assert "disclosure" in reason

    def test_content_signals_affiliate_links(self):
        html = "<html><body>"
        for i in range(5):
            html += f'<a href="https://go.redirectingat.com/product{i}">Buy</a>'
        html += "</body></html>"
        soup = BeautifulSoup(html, "html.parser")
        site_type, reason = classify_site_with_content("unknownsite2.com", soup)
        assert site_type == "Affiliate/Review"
        assert "affiliate_links" in reason or "disclosure" in reason

    def test_clean_unknown_site_defaults_outreach(self):
        html = """
        <html><body>
        <h1>Our Company Blog</h1>
        <p>We built our product to solve customer problems.</p>
        <a href="/pricing">Pricing</a>
        </body></html>
        """
        soup = BeautifulSoup(html, "html.parser")
        site_type, reason = classify_site_with_content("mybiz.com", soup)
        assert site_type == "Outreach"
        assert "unknown_default" in reason

    def test_vendor_blog_not_misclassified_as_affiliate(self):
        """A vendor blog with a partner page should NOT be classified as affiliate."""
        html = """
        <html><body>
        <h1>Best CRM Tools for Startups</h1>
        <p>We compared various CRM options for founders.</p>
        <a href="/partners">Partners</a>
        </body></html>
        """
        soup = BeautifulSoup(html, "html.parser")
        # Domain is in known outreach list
        site_type, reason = classify_site_with_content("capsulecrm.com", soup)
        assert site_type == "Vendor Blog"
        assert reason == "known_list"
