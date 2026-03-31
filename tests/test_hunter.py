"""Unit tests for hunter.py — all API calls are mocked, zero credits consumed."""

import os
from unittest.mock import patch, MagicMock

import pytest

import hunter


@pytest.fixture(autouse=True)
def _reset_hunter():
    """Reset module state before each test."""
    hunter.reset_circuit_breaker()
    yield


@pytest.fixture
def mock_api_key():
    with patch.dict(os.environ, {"HUNTER_API_KEY": "test-key-123"}):
        yield


def _mock_response(status_code=200, json_data=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    return resp


class TestFindEmail:
    @patch("hunter.requests.get")
    def test_returns_email_on_success(self, mock_get, mock_api_key):
        mock_get.return_value = _mock_response(200, {
            "data": {
                "email": "john@example.com",
                "score": 95,
                "first_name": "John",
                "last_name": "Smith",
                "position": "Marketing Manager",
                "linkedin": "https://linkedin.com/in/john-smith",
                "sources": 3,
            }
        })
        result = hunter.find_email("example.com", "John", "Smith")
        assert result is not None
        assert result["email"] == "john@example.com"
        assert result["score"] == 95
        assert result["linkedin_url"] == "https://linkedin.com/in/john-smith"
        mock_get.assert_called_once()

    @patch("hunter.requests.get")
    def test_returns_none_when_no_api_key(self, mock_get):
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("HUNTER_API_KEY", None)
            result = hunter.find_email("example.com", "John", "Smith")
        assert result is None
        mock_get.assert_not_called()

    @patch("hunter.requests.get")
    def test_returns_none_on_empty_inputs(self, mock_get, mock_api_key):
        assert hunter.find_email("", "John", "Smith") is None
        assert hunter.find_email("example.com", "", "Smith") is None
        assert hunter.find_email("example.com", "John", "") is None
        mock_get.assert_not_called()

    @patch("hunter.requests.get")
    def test_returns_none_on_http_error(self, mock_get, mock_api_key):
        import requests as req
        mock_get.side_effect = req.ConnectionError("Connection refused")
        result = hunter.find_email("example.com", "John", "Smith")
        assert result is None

    @patch("hunter.requests.get")
    def test_returns_none_on_402_credits_exhausted(self, mock_get, mock_api_key):
        mock_get.return_value = _mock_response(402)
        result = hunter.find_email("example.com", "John", "Smith")
        assert result is None
        # Circuit breaker: second call should not hit API
        mock_get.reset_mock()
        result2 = hunter.find_email("example.com", "Jane", "Doe")
        assert result2 is None
        mock_get.assert_not_called()

    @patch("hunter.requests.get")
    def test_returns_none_on_429_rate_limit(self, mock_get, mock_api_key):
        mock_get.return_value = _mock_response(429)
        result = hunter.find_email("example.com", "John", "Smith")
        assert result is None

    @patch("hunter.requests.get")
    def test_returns_none_when_no_email_in_response(self, mock_get, mock_api_key):
        mock_get.return_value = _mock_response(200, {"data": {"email": None}})
        result = hunter.find_email("example.com", "John", "Smith")
        assert result is None

    @patch("hunter.time.sleep")
    @patch("hunter.requests.get")
    def test_rate_limiting(self, mock_get, mock_sleep, mock_api_key):
        mock_get.return_value = _mock_response(200, {
            "data": {"email": "a@b.com", "score": 90}
        })
        # First call sets timestamp, second should trigger sleep
        hunter.find_email("example.com", "John", "Smith")
        hunter.find_email("example.com", "Jane", "Doe")
        assert mock_sleep.called
