"""Integration tests for the outreach pipeline.

Tests the pipeline logic without making real network calls by mocking the Scraper.
"""

import sys
import os
import csv
import tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import MagicMock, patch
from bs4 import BeautifulSoup

from outreach_finder import process_url, classify_send, read_input, write_output
from models import OutreachResult


def _make_mock_scraper(html=None, url_exists=False):
    """Create a mock scraper that returns given HTML as soup."""
    scraper = MagicMock()
    if html:
        soup = BeautifulSoup(html, "html.parser")
        scraper.fetch_page.return_value = soup
    else:
        scraper.fetch_page.return_value = None
    scraper.check_url_exists.return_value = url_exists
    scraper.last_fetch_method = "direct_http" if html else None
    return scraper


# ── classify_send ─────────────────────────────────────────────────────────


class TestClassifySend:

    def test_affiliate_gets_not_applicable(self):
        r = OutreachResult(site_type="Affiliate/Review", domain="pcmag.com")
        classify_send(r)
        assert r.send_classification == "not_applicable"
        assert r.authority_score == "affiliate_site"

    def test_known_outreach_brand_gets_manual(self):
        r = OutreachResult(site_type="Vendor Blog", domain="capsulecrm.com")
        classify_send(r)
        assert r.send_classification == "manual_send"
        assert r.authority_score == "known_brand"

    def test_known_non_affiliate_brand_gets_manual(self):
        r = OutreachResult(site_type="Outreach", domain="uschamber.com")
        classify_send(r)
        assert r.send_classification == "manual_send"
        assert r.authority_score == "known_brand"

    def test_domain_pattern_gets_manual(self):
        r = OutreachResult(site_type="Vendor Blog", domain="blog.newco.com",
                           classification_reason="domain_pattern")
        classify_send(r)
        assert r.send_classification == "manual_send"
        assert r.authority_score == "heuristic:vendor_blog_pattern"

    def test_unknown_publisher_gets_auto(self):
        r = OutreachResult(site_type="Outreach", domain="randomsite.com",
                           classification_reason="unknown_default:needs_review")
        classify_send(r)
        assert r.send_classification == "auto_send"
        assert r.authority_score == "heuristic:unknown_publisher"

    def test_send_override_takes_priority(self):
        r = OutreachResult(site_type="Affiliate/Review", domain="pcmag.com")
        classify_send(r, send_override="manual_send")
        assert r.send_classification == "manual_send"
        assert r.authority_score == "manual_override"


# ── process_url (mock scraper) ────────────────────────────────────────────


class TestProcessUrl:

    def test_known_affiliate_site(self):
        html = """
        <html><head>
        <meta property="og:site_name" content="TechRadar">
        <meta name="author" content="John Reviewer">
        </head><body>
        <p>We may earn a commission through affiliate links.</p>
        <a href="/deals">Deals</a>
        </body></html>
        """
        scraper = _make_mock_scraper(html)
        result = process_url("https://techradar.com/best/crm", "high", scraper)
        assert result.site_type == "Affiliate/Review"
        assert result.send_classification == "not_applicable"
        assert result.company_name == "TechRadar"

    def test_known_vendor_blog(self):
        html = """
        <html><head>
        <meta name="author" content="Sarah Founder">
        </head><body>
        <h1>Best CRM for Startups</h1>
        <p>We compared several CRM tools.</p>
        </body></html>
        """
        scraper = _make_mock_scraper(html)
        result = process_url("https://capsulecrm.com/blog/best-crm", "medium", scraper)
        assert result.site_type == "Vendor Blog"
        assert result.send_classification == "manual_send"
        assert result.author_name == "Sarah Founder"
        assert result.author_email_candidates != ""  # should generate candidates
        assert "sarah@capsulecrm.com" in result.author_email_candidates

    def test_unknown_site_defaults_outreach(self):
        html = """
        <html><head></head><body>
        <h1>Our Top CRM Picks</h1>
        <p>Here are our recommendations.</p>
        </body></html>
        """
        scraper = _make_mock_scraper(html)
        result = process_url("https://newblog123.com/best-crm", "low", scraper)
        assert result.site_type == "Outreach"
        assert result.send_classification == "auto_send"

    def test_failed_fetch_uses_known_sites(self):
        scraper = _make_mock_scraper(html=None)
        result = process_url("https://forbes.com/advisor/best-crm", "high", scraper)
        assert result.company_name == "Forbes"
        assert result.contact_type == "affiliate_form"

    def test_no_email_candidates_for_affiliate(self):
        html = """
        <html><head><meta name="author" content="Review Writer"></head>
        <body><p>Content</p></body></html>
        """
        scraper = _make_mock_scraper(html)
        result = process_url("https://g2.com/categories/crm", "high", scraper)
        assert result.site_type == "Affiliate/Review"
        assert result.author_email_candidates == ""

    def test_linkedin_url_includes_author(self):
        html = """
        <html><head><meta name="author" content="Alice Park"></head>
        <body><p>Article content</p></body></html>
        """
        scraper = _make_mock_scraper(html)
        result = process_url("https://randomsite.com/article", "low", scraper)
        assert "Alice" in result.linkedin_search_url


# ── read_input / write_output ────────────────────────────────────────────


class TestReadInput:

    def test_standard_format(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["url", "priority"])
            writer.writerow(["https://example.com/article", "high"])
            path = f.name
        try:
            entries = read_input(path)
            assert len(entries) == 1
            assert entries[0][0] == "https://example.com/article"
            assert entries[0][1] == "high"
        finally:
            os.unlink(path)

    def test_citation_format(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["rank", "page", "category", "mentioned", "share", "share delta"])
            writer.writerow(["1", "techradar.com/best/crm", "Earned Media", "Not Mentioned", "4.77", "0.93"])
            path = f.name
        try:
            entries = read_input(path)
            assert len(entries) == 1
            url, priority, extras = entries[0]
            assert url == "https://techradar.com/best/crm"
        finally:
            os.unlink(path)

    def test_extras_preserved(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["url", "priority", "rank", "category"])
            writer.writerow(["https://example.com", "high", "1", "Earned Media"])
            path = f.name
        try:
            entries = read_input(path)
            extras = entries[0][2]
            assert extras["rank"] == "1"
            assert extras["category"] == "Earned Media"
        finally:
            os.unlink(path)


class TestWriteOutput:

    def test_roundtrip(self):
        results = [
            OutreachResult(url="https://example.com", priority="high",
                           domain="example.com", company_name="Example",
                           site_type="Outreach", send_classification="auto_send"),
        ]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            path = f.name
        try:
            write_output(path, results)
            with open(path, newline="", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            assert len(rows) == 1
            assert rows[0]["url"] == "https://example.com"
            assert rows[0]["send_classification"] == "auto_send"
        finally:
            os.unlink(path)
