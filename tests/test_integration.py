"""Integration tests — runs the real pipeline against a sample of the citation data.

Requires DataForSEO credentials in .env or environment variables.
Skips automatically if credentials are not available.

Usage:
    ./run_tests.sh tests/test_integration.py -v
"""

import sys
import os
import csv
import tempfile
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from scraper import Scraper
from outreach_finder import process_url, read_input, write_output
from models import OutreachResult


# ---------------------------------------------------------------------------
# Skip all tests if no credentials
# ---------------------------------------------------------------------------

def _has_credentials():
    login = os.environ.get("DATAFORSEO_LOGIN", "") or os.environ.get("DATAFORSEO_USERNAME", "")
    password = os.environ.get("DATAFORSEO_PASSWORD", "")
    return bool(login and password)


pytestmark = pytest.mark.skipif(
    not _has_credentials(),
    reason="DataForSEO credentials not available",
)


# ---------------------------------------------------------------------------
# Result collection — writes all OutreachResults to a CSV after tests finish
# ---------------------------------------------------------------------------

_collected_results: list[OutreachResult] = []


def _save_results():
    """Write collected results to test_results/integration_output_<timestamp>.csv."""
    if not _collected_results:
        return
    results_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "test_results")
    os.makedirs(results_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    out_path = os.path.join(results_dir, f"integration_output_{timestamp}.csv")
    write_output(out_path, _collected_results)
    print(f"\nIntegration test output saved to: {out_path}")


def record_result(result: OutreachResult) -> OutreachResult:
    """Record a result for end-of-session CSV export."""
    _collected_results.append(result)
    return result


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def scraper():
    """Shared scraper instance for all integration tests."""
    s = Scraper()
    yield s
    s.stop()
    _save_results()


# A representative sample: known affiliate, known vendor, known non-affiliate,
# and a couple unknowns — drawn from the real citation data.
SAMPLE_URLS = [
    # (url, expected_site_type, expected_send_classification)
    ("https://techradar.com/best/the-best-crm-for-startups", "Affiliate/Review", "not_applicable"),
    ("https://capsulecrm.com/blog/best-crm-for-founders/", "Outreach", "manual_send"),
    ("https://pcmag.com/picks/the-best-small-business-crm-software", "Affiliate/Review", "not_applicable"),
    ("https://forbes.com/advisor/business/software/best-crm-software/", "Affiliate/Review", "not_applicable"),
    ("https://uschamber.com/co/start/strategy/low-cost-crm-tools", "Outreach", "manual_send"),
]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSingleUrlProcessing:
    """Process individual URLs and validate output fields."""

    @pytest.mark.parametrize("url,expected_type,expected_send", SAMPLE_URLS)
    def test_classification_correct(self, scraper, url, expected_type, expected_send):
        result = record_result(process_url(url, "high", scraper))
        assert result.site_type == expected_type, (
            f"{url}: expected site_type={expected_type}, got {result.site_type} "
            f"(reason: {result.classification_reason})"
        )
        assert result.send_classification == expected_send, (
            f"{url}: expected send={expected_send}, got {result.send_classification}"
        )

    @pytest.mark.parametrize("url,expected_type,expected_send", SAMPLE_URLS)
    def test_required_fields_populated(self, scraper, url, expected_type, expected_send):
        result = record_result(process_url(url, "high", scraper))

        # Every result must have these
        assert result.url == url
        assert result.domain != ""
        assert result.site_type != ""
        assert result.send_classification != ""
        assert result.authority_score != ""
        assert result.company_name != ""

    def test_affiliate_has_no_email_candidates(self, scraper):
        result = record_result(process_url("https://g2.com/categories/crm", "high", scraper))
        assert result.site_type == "Affiliate/Review"
        assert result.author_email_candidates == ""

    def test_vendor_blog_generates_email_candidates(self, scraper):
        result = record_result(process_url("https://capsulecrm.com/blog/best-crm-for-founders/", "medium", scraper))
        if result.author_name:
            assert result.author_email_candidates != "", (
                f"Author '{result.author_name}' found but no email candidates generated"
            )

    def test_no_junk_author_names(self, scraper):
        """Author names should never be common nav terms or generic phrases."""
        junk = {"home", "menu", "about", "contact", "blog", "admin",
                "staff writer", "editorial team", "the team"}
        for url, _, _ in SAMPLE_URLS:
            result = record_result(process_url(url, "high", scraper))
            if result.author_name:
                assert result.author_name.lower() not in junk, (
                    f"{url}: junk author name '{result.author_name}'"
                )


class TestBatchProcessing:
    """Test processing a batch from the real input file."""

    def test_process_first_10_urls(self, scraper):
        """Process the top 10 citation URLs and validate basic output integrity."""
        input_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "input.csv")
        if not os.path.exists(input_path):
            pytest.skip("input.csv not found")

        entries = read_input(input_path)[:10]
        results = []

        for url, priority, extras in entries:
            send_override = extras.pop("send_override", "").strip()
            result = record_result(process_url(url, priority, scraper, send_override=send_override))
            result.extras = extras
            results.append(result)

        # All 10 should produce results
        assert len(results) == 10

        # Every result has required fields
        for r in results:
            assert r.url != ""
            assert r.domain != ""
            assert r.site_type in ("Affiliate/Review", "Outreach", "Outreach")
            assert r.send_classification in ("not_applicable", "manual_send", "auto_send")
            assert r.company_name != ""

        # Write output and verify CSV is well-formed
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            out_path = f.name
        try:
            write_output(out_path, results)
            with open(out_path, newline="", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            assert len(rows) == 10
            # Headers should include extras from input
            assert "rank" in reader.fieldnames or "category" in reader.fieldnames
        finally:
            os.unlink(out_path)

    def test_no_duplicate_classifications(self, scraper):
        """Known domains should always get the same classification."""
        input_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "input.csv")
        if not os.path.exists(input_path):
            pytest.skip("input.csv not found")

        entries = read_input(input_path)

        # Find entries with the same domain appearing multiple times
        from collections import defaultdict
        domain_entries = defaultdict(list)
        for url, priority, extras in entries[:50]:
            from scraper import get_domain
            domain = get_domain(url).replace("www.", "")
            domain_entries[domain].append(url)

        # For domains that appear more than once, classification should be consistent
        for domain, urls in domain_entries.items():
            if len(urls) < 2:
                continue
            results = []
            for url in urls[:2]:
                r = record_result(process_url(url, "high", scraper))
                results.append(r)
            assert results[0].site_type == results[1].site_type, (
                f"Inconsistent classification for {domain}: "
                f"{results[0].url}={results[0].site_type}, "
                f"{results[1].url}={results[1].site_type}"
            )
