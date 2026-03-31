"""Thin client for the Hunter.io API.

All Hunter API calls go through this module. Callers should use
find_email(), which returns a typed dict or None on failure.
"""

import os
import sys
import time
import requests
from typing import Optional, TypedDict


HUNTER_API_BASE = "https://api.hunter.io/v2"
HUNTER_TIMEOUT = 10  # seconds

# Rate limiting: minimum seconds between API calls
_MIN_CALL_INTERVAL = 1.0
_last_call_ts: float = 0.0

# Circuit breaker: stop calling after credits exhausted
_credits_exhausted = False


class HunterEmailResult(TypedDict, total=False):
    email: str
    score: int  # confidence 0-100
    first_name: str
    last_name: str
    position: str
    linkedin_url: str
    sources: int


def _get_api_key() -> Optional[str]:
    return os.environ.get("HUNTER_API_KEY", "").strip() or None


def _rate_limit():
    """Sleep if needed to maintain minimum interval between calls."""
    global _last_call_ts
    now = time.time()
    elapsed = now - _last_call_ts
    if _last_call_ts > 0 and elapsed < _MIN_CALL_INTERVAL:
        time.sleep(_MIN_CALL_INTERVAL - elapsed)
    _last_call_ts = time.time()


def find_email(domain: str, first_name: str, last_name: str) -> Optional[HunterEmailResult]:
    """Call Hunter.io Email Finder: domain + name -> verified email.

    Returns HunterEmailResult dict on success, None on any failure
    (missing key, network error, no result, credits exhausted).
    """
    global _credits_exhausted

    if _credits_exhausted:
        return None

    api_key = _get_api_key()
    if not api_key:
        return None

    if not domain or not first_name or not last_name:
        return None

    _rate_limit()

    try:
        resp = requests.get(
            f"{HUNTER_API_BASE}/email-finder",
            params={
                "domain": domain,
                "first_name": first_name,
                "last_name": last_name,
                "api_key": api_key,
            },
            timeout=HUNTER_TIMEOUT,
        )

        if resp.status_code == 402:
            _credits_exhausted = True
            print("  [Hunter] Credits exhausted — skipping future calls", file=sys.stderr)
            return None

        if resp.status_code == 429:
            print("  [Hunter] Rate limited — skipping", file=sys.stderr)
            return None

        if resp.status_code != 200:
            print(f"  [Hunter] HTTP {resp.status_code} — skipping", file=sys.stderr)
            return None

        data = resp.json().get("data", {})
        email = data.get("email")
        if not email:
            return None

        return HunterEmailResult(
            email=email,
            score=data.get("score", 0),
            first_name=data.get("first_name", ""),
            last_name=data.get("last_name", ""),
            position=data.get("position", ""),
            linkedin_url=data.get("linkedin", ""),
            sources=data.get("sources", 0),
        )

    except requests.RequestException as e:
        print(f"  [Hunter] Request error: {e}", file=sys.stderr)
        return None
    except (ValueError, KeyError) as e:
        print(f"  [Hunter] Parse error: {e}", file=sys.stderr)
        return None


def reset_circuit_breaker():
    """Reset the credits-exhausted flag. Useful for testing."""
    global _credits_exhausted, _last_call_ts
    _credits_exhausted = False
    _last_call_ts = 0.0
