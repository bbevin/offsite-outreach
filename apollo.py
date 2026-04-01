"""Thin client for the Apollo.io People Enrichment API.

Used as a fallback when Hunter.io does not return a verified email.
Callers should use find_email(), which returns a typed dict or None on failure.
"""

import os
import sys
import time
import requests
from typing import Optional, TypedDict


APOLLO_API_BASE = "https://api.apollo.io/api/v1"
APOLLO_TIMEOUT = 10  # seconds

# Rate limiting: minimum seconds between API calls
_MIN_CALL_INTERVAL = 1.0
_last_call_ts: float = 0.0

# Circuit breaker: stop calling after credits exhausted
_credits_exhausted = False


class ApolloEmailResult(TypedDict, total=False):
    email: str
    first_name: str
    last_name: str
    title: str
    linkedin_url: str
    confidence: str  # "high", "medium", "low", or ""


def _get_api_key() -> Optional[str]:
    return os.environ.get("APOLLO_API_KEY", "").strip() or None


def _rate_limit():
    """Sleep if needed to maintain minimum interval between calls."""
    global _last_call_ts
    now = time.time()
    elapsed = now - _last_call_ts
    if _last_call_ts > 0 and elapsed < _MIN_CALL_INTERVAL:
        time.sleep(_MIN_CALL_INTERVAL - elapsed)
    _last_call_ts = time.time()


def find_email(domain: str, first_name: str, last_name: str) -> Optional[ApolloEmailResult]:
    """Call Apollo.io People Match: domain + name -> email.

    Returns ApolloEmailResult dict on success, None on any failure
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
        resp = requests.post(
            f"{APOLLO_API_BASE}/people/match",
            json={
                "first_name": first_name,
                "last_name": last_name,
                "organization_name": domain,
                "domain": domain,
            },
            headers={
                "X-Api-Key": api_key,
                "Content-Type": "application/json",
            },
            timeout=APOLLO_TIMEOUT,
        )

        if resp.status_code == 402:
            _credits_exhausted = True
            print("  [Apollo] Credits exhausted — skipping future calls", file=sys.stderr)
            return None

        if resp.status_code == 429:
            print("  [Apollo] Rate limited — skipping", file=sys.stderr)
            return None

        if resp.status_code != 200:
            print(f"  [Apollo] HTTP {resp.status_code} — skipping", file=sys.stderr)
            return None

        person = resp.json().get("person") or {}
        email = person.get("email")
        if not email:
            return None

        return ApolloEmailResult(
            email=email,
            first_name=person.get("first_name", ""),
            last_name=person.get("last_name", ""),
            title=person.get("title", ""),
            linkedin_url=person.get("linkedin_url", ""),
            confidence=person.get("email_confidence", ""),
        )

    except requests.RequestException as e:
        print(f"  [Apollo] Request error: {e}", file=sys.stderr)
        return None
    except (ValueError, KeyError) as e:
        print(f"  [Apollo] Parse error: {e}", file=sys.stderr)
        return None


def reset_circuit_breaker():
    """Reset the credits-exhausted flag. Useful for testing."""
    global _credits_exhausted, _last_call_ts
    _credits_exhausted = False
    _last_call_ts = 0.0
