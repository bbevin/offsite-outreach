"""Integration tests for Hunter.io API — requires HUNTER_API_KEY env var.

Run manually:
    HUNTER_API_KEY=xxx python3 -m pytest tests/test_hunter_integration.py -v

These tests consume real API credits. Do NOT include in CI or run_tests.sh.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from hunter import find_email

pytestmark = pytest.mark.skipif(
    not os.environ.get("HUNTER_API_KEY"),
    reason="HUNTER_API_KEY not set — skipping integration tests",
)


class TestHunterIntegration:
    def test_find_email_known_person(self):
        """Test against a known marketing contact at a large company."""
        result = find_email("hubspot.com", "Caroline", "Forsey")
        assert result is not None
        assert "@" in result.get("email", "")
        assert result.get("score", 0) > 0

    def test_find_email_nonexistent_person(self):
        result = find_email("example.com", "Zzzznotreal", "Personxyz")
        assert result is None or result.get("score", 0) < 30

    def test_empty_inputs_dont_waste_credits(self):
        result = find_email("", "", "")
        assert result is None
