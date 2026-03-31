"""Tests for models.py and parse_citations.py."""

import sys
import os
import tempfile
import csv
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from models import OutreachResult, AuthorInfo, ContactInfo, TeamContact
from parse_citations import share_to_priority, parse


# ── OutreachResult ────────────────────────────────────────────────────────


class TestOutreachResult:

    def test_default_values(self):
        r = OutreachResult()
        assert r.url == ""
        assert r.domain == ""
        assert r.extras == {}

    def test_csv_headers_base(self):
        r = OutreachResult()
        headers = r.csv_headers()
        assert headers[0] == "url"
        assert "site_type" in headers
        assert "send_classification" in headers
        assert "affiliate_network" in headers
        assert len(headers) == 21  # base headers count (19 + verified_email, email_source)

    def test_csv_headers_with_extras(self):
        r = OutreachResult(extras={"rank": "1", "category": "Earned Media"})
        headers = r.csv_headers()
        assert "category" in headers
        assert "rank" in headers
        # extras are sorted alphabetically
        extra_part = headers[21:]
        assert extra_part == ["category", "rank"]

    def test_to_row_length_matches_headers(self):
        r = OutreachResult(url="https://example.com", domain="example.com",
                           extras={"rank": "5"})
        assert len(r.to_row()) == len(r.csv_headers())

    def test_to_row_values(self):
        r = OutreachResult(url="https://ex.com", priority="high", domain="ex.com",
                           company_name="Example", site_type="Outreach")
        row = r.to_row()
        assert row[0] == "https://ex.com"
        assert row[1] == "high"
        assert row[3] == "Example"


# ── Data classes ──────────────────────────────────────────────────────────


class TestDataClasses:

    def test_author_info(self):
        a = AuthorInfo(name="John Doe", url="https://example.com/john")
        assert a.name == "John Doe"
        assert a.url == "https://example.com/john"

    def test_contact_info(self):
        c = ContactInfo(contact_type="affiliate_form",
                        contact_form_url="https://example.com/partners")
        assert c.contact_type == "affiliate_form"

    def test_team_contact(self):
        t = TeamContact(name="Jane", role="VP Marketing", url="/team/jane")
        assert t.name == "Jane"
        assert t.role == "VP Marketing"


# ── parse_citations.py ───────────────────────────────────────────────────


class TestShareToPriority:

    def test_high(self):
        assert share_to_priority(2.0) == "high"
        assert share_to_priority(5.5) == "high"

    def test_medium(self):
        assert share_to_priority(1.0) == "medium"
        assert share_to_priority(1.99) == "medium"

    def test_low(self):
        assert share_to_priority(0.5) == "low"
        assert share_to_priority(0.0) == "low"


class TestParseCitations:

    def test_basic_parse(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["rank", "page", "category", "mentioned", "share", "share delta"])
            writer.writerow(["1", "techradar.com/best/crm", "Earned Media", "Not Mentioned", "4.77", "0.93"])
            writer.writerow(["2", "https://crm.org/list", "Other", "Mentioned", "1.5", "-0.2"])
            input_path = f.name

        output_path = input_path + ".out.csv"
        try:
            parse(input_path, output_path)

            with open(output_path, newline="") as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            assert len(rows) == 2
            # First row: no https prefix → gets added
            assert rows[0]["url"] == "https://techradar.com/best/crm"
            assert rows[0]["priority"] == "high"
            assert rows[0]["rank"] == "1"
            # Second row: already has https
            assert rows[1]["url"] == "https://crm.org/list"
            assert rows[1]["priority"] == "medium"
        finally:
            os.unlink(input_path)
            if os.path.exists(output_path):
                os.unlink(output_path)
