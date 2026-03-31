"""Tests for scraper.py — utility functions (no network calls)."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from scraper import get_domain, get_base_url, make_absolute


class TestGetDomain:

    def test_basic(self):
        assert get_domain("https://www.example.com/path") == "www.example.com"

    def test_no_www(self):
        assert get_domain("https://example.com/path") == "example.com"

    def test_subdomain(self):
        assert get_domain("https://blog.example.com/post") == "blog.example.com"

    def test_with_port(self):
        assert get_domain("https://example.com:8080/path") == "example.com:8080"


class TestGetBaseUrl:

    def test_basic(self):
        assert get_base_url("https://www.example.com/path/page") == "https://www.example.com"

    def test_http(self):
        assert get_base_url("http://example.com/foo") == "http://example.com"


class TestMakeAbsolute:

    def test_relative_path(self):
        assert make_absolute("https://example.com", "/contact") == "https://example.com/contact"

    def test_already_absolute(self):
        assert make_absolute("https://example.com", "https://other.com/page") == "https://other.com/page"

    def test_relative_no_slash(self):
        result = make_absolute("https://example.com/blog/", "post")
        assert result == "https://example.com/blog/post"
