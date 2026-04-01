"""Unit tests for apollo.py — all API calls are mocked, zero credits consumed."""

import os
from unittest.mock import patch, MagicMock

import pytest

import apollo


@pytest.fixture(autouse=True)
def _reset_apollo():
    """Reset module state before each test."""
    apollo.reset_circuit_breaker()
    yield


@pytest.fixture
def mock_api_key():
    with patch.dict(os.environ, {"APOLLO_API_KEY": "test-key-123"}):
        yield


def _mock_response(status_code=200, json_data=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    return resp


class TestFindEmail:
    @patch("apollo.requests.post")
    def test_returns_email_on_success(self, mock_post, mock_api_key):
        mock_post.return_value = _mock_response(200, {
            "person": {
                "email": "john@example.com",
                "first_name": "John",
                "last_name": "Smith",
                "title": "Marketing Manager",
                "linkedin_url": "https://linkedin.com/in/john-smith",
                "email_confidence": "high",
            }
        })
        result = apollo.find_email("example.com", "John", "Smith")
        assert result is not None
        assert result["email"] == "john@example.com"
        assert result["title"] == "Marketing Manager"
        assert result["confidence"] == "high"
        mock_post.assert_called_once()

    @patch("apollo.requests.post")
    def test_returns_none_when_no_api_key(self, mock_post):
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("APOLLO_API_KEY", None)
            result = apollo.find_email("example.com", "John", "Smith")
        assert result is None
        mock_post.assert_not_called()

    @patch("apollo.requests.post")
    def test_returns_none_on_empty_inputs(self, mock_post, mock_api_key):
        assert apollo.find_email("", "John", "Smith") is None
        assert apollo.find_email("example.com", "", "Smith") is None
        assert apollo.find_email("example.com", "John", "") is None
        mock_post.assert_not_called()

    @patch("apollo.requests.post")
    def test_returns_none_on_http_error(self, mock_post, mock_api_key):
        import requests as req
        mock_post.side_effect = req.ConnectionError("Connection refused")
        result = apollo.find_email("example.com", "John", "Smith")
        assert result is None

    @patch("apollo.requests.post")
    def test_returns_none_on_402_credits_exhausted(self, mock_post, mock_api_key):
        mock_post.return_value = _mock_response(402)
        result = apollo.find_email("example.com", "John", "Smith")
        assert result is None
        # Circuit breaker: second call should not hit API
        mock_post.reset_mock()
        result2 = apollo.find_email("example.com", "Jane", "Doe")
        assert result2 is None
        mock_post.assert_not_called()

    @patch("apollo.requests.post")
    def test_returns_none_on_429_rate_limit(self, mock_post, mock_api_key):
        mock_post.return_value = _mock_response(429)
        result = apollo.find_email("example.com", "John", "Smith")
        assert result is None

    @patch("apollo.requests.post")
    def test_returns_none_when_no_person_in_response(self, mock_post, mock_api_key):
        mock_post.return_value = _mock_response(200, {"person": None})
        result = apollo.find_email("example.com", "John", "Smith")
        assert result is None

    @patch("apollo.requests.post")
    def test_returns_none_when_no_email_in_person(self, mock_post, mock_api_key):
        mock_post.return_value = _mock_response(200, {"person": {"email": None}})
        result = apollo.find_email("example.com", "John", "Smith")
        assert result is None

    @patch("apollo.time.sleep")
    @patch("apollo.requests.post")
    def test_rate_limiting(self, mock_post, mock_sleep, mock_api_key):
        mock_post.return_value = _mock_response(200, {
            "person": {"email": "a@b.com", "email_confidence": "high"}
        })
        apollo.find_email("example.com", "John", "Smith")
        apollo.find_email("example.com", "Jane", "Doe")
        assert mock_sleep.called
