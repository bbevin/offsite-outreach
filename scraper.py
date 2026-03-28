from __future__ import annotations

import os
import time
import base64
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin

RATE_LIMIT_SECONDS = 1  # DataForSEO handles rate limiting server-side, keep minimal

DATAFORSEO_API_URL = "https://api.dataforseo.com/v3/on_page/content_parsing/live"
DATAFORSEO_INSTANT_URL = "https://api.dataforseo.com/v3/on_page/instant_pages"
DATAFORSEO_RAW_HTML_URL = "https://api.dataforseo.com/v3/on_page/raw_html"


class Scraper:
    """Fetches pages via the DataForSEO On-Page API."""

    def __init__(self, login: str | None = None, password: str | None = None):
        self._login = login or os.environ.get("DATAFORSEO_LOGIN", "") or os.environ.get("DATAFORSEO_USERNAME", "")
        self._password = password or os.environ.get("DATAFORSEO_PASSWORD", "")
        if not self._login or not self._password:
            raise ValueError(
                "DataForSEO credentials required. Set DATAFORSEO_LOGIN and "
                "DATAFORSEO_PASSWORD environment variables."
            )
        creds = base64.b64encode(f"{self._login}:{self._password}".encode()).decode()
        self._headers = {
            "Authorization": f"Basic {creds}",
            "Content-Type": "application/json",
        }
        self._session = requests.Session()
        self._session.headers.update(self._headers)

    def start(self):
        pass  # session is ready on init

    def stop(self):
        self._session.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.stop()

    def fetch_page(self, url: str) -> BeautifulSoup | None:
        """Fetch a URL via DataForSEO Instant Pages and return parsed HTML."""
        # Step 1: Submit instant page task with store_raw_html
        payload = [
            {
                "url": url,
                "store_raw_html": True,
                "enable_javascript": True,
                "enable_browser_rendering": True,
            }
        ]
        try:
            resp = self._session.post(DATAFORSEO_INSTANT_URL, json=payload, timeout=90)
            resp.raise_for_status()
            data = resp.json()

            if data.get("status_code") != 20000:
                print(f"  [warn] DataForSEO error: {data.get('status_message')}")
                return self._fetch_via_content_parsing(url)

            tasks = data.get("tasks", [])
            if not tasks or tasks[0].get("status_code") != 20000:
                msg = tasks[0].get("status_message") if tasks else "no tasks returned"
                print(f"  [warn] DataForSEO task error: {msg}")
                return self._fetch_via_content_parsing(url)

            task_id = tasks[0].get("id")
            result = tasks[0].get("result")

            # Check if the page returned a non-success status
            if result:
                for item in result:
                    items = item.get("items", [])
                    if isinstance(items, list) and items:
                        page_status = items[0].get("status_code", 0)
                        if page_status >= 400:
                            print(f"  [info] Page returned HTTP {page_status} via instant, trying content parsing...")
                            return self._fetch_via_content_parsing(url)

            # Step 2: Fetch raw HTML using the task ID
            if task_id:
                return self._fetch_raw_html(task_id, url)

            return self._fetch_via_content_parsing(url)

        except requests.RequestException as e:
            print(f"  [warn] Failed to fetch {url}: {e}")
            return self._fetch_via_content_parsing(url)

    def _fetch_raw_html(self, task_id: str, url: str) -> BeautifulSoup | None:
        """Retrieve raw HTML for a completed instant page task."""
        payload = [
            {
                "id": task_id,
                "url": url,
            }
        ]
        try:
            resp = self._session.post(DATAFORSEO_RAW_HTML_URL, json=payload, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            tasks = data.get("tasks", [])
            if not tasks or tasks[0].get("status_code") != 20000:
                # Fall back to content parsing if raw HTML fails
                print(f"  [info] Raw HTML unavailable, using content parsing")
                return self._fetch_via_content_parsing(url)

            result = tasks[0].get("result", [])
            if result:
                for r in result:
                    items = r.get("items")
                    if not items:
                        continue
                    # items can be a list or a dict
                    if isinstance(items, dict):
                        html = items.get("html", "")
                    elif isinstance(items, list) and items:
                        html = items[0].get("html", "")
                    else:
                        continue
                    if html:
                        return BeautifulSoup(html, "lxml")

            return self._fetch_via_content_parsing(url)

        except (requests.RequestException, Exception) as e:
            print(f"  [info] Raw HTML retrieval error: {e}, falling back to content parsing")
            return self._fetch_via_content_parsing(url)

    def _fetch_via_content_parsing(self, url: str) -> BeautifulSoup | None:
        """Fallback: use content parsing endpoint with browser rendering + alt proxies."""
        payload = [
            {
                "url": url,
                "enable_javascript": True,
                "enable_browser_rendering": True,
                "switch_pool": True,
            }
        ]
        try:
            resp = self._session.post(DATAFORSEO_API_URL, json=payload, timeout=60)
            resp.raise_for_status()
            data = resp.json()

            tasks = data.get("tasks", [])
            if not tasks or tasks[0].get("status_code") != 20000:
                msg = tasks[0].get("status_message") if tasks else "no tasks"
                print(f"  [warn] Content parsing failed: {msg}")
                return None

            result = tasks[0].get("result", [])
            if result:
                items = result[0].get("items", [])
                if isinstance(items, list) and items:
                    page_content = items[0].get("page_content", {})
                    # Build a minimal HTML doc from the parsed content
                    return self._content_to_soup(page_content, url)
            return None

        except requests.RequestException as e:
            print(f"  [warn] Content parsing failed for {url}: {e}")
            return None

    def _content_to_soup(self, page_content: dict, url: str) -> BeautifulSoup:
        """Convert DataForSEO parsed content back into a BeautifulSoup object."""
        parts = ["<html><head></head><body>"]

        for group_name in ("header", "main_topic", "secondary_topic", "footer"):
            group = page_content.get(group_name)
            if not group:
                continue
            items = group if isinstance(group, list) else [group]
            for item in items:
                if isinstance(item, dict):
                    text = item.get("text", "")
                    if text:
                        parts.append(f"<p>{text}</p>")
                    # Process sub-items
                    for sub in item.get("items", []):
                        if isinstance(sub, dict):
                            t = sub.get("text", "")
                            if t:
                                parts.append(f"<p>{t}</p>")

        parts.append("</body></html>")
        return BeautifulSoup("\n".join(parts), "lxml")

    def check_url_exists(self, url: str) -> bool:
        """Check whether a URL returns a success status via a lightweight HEAD request."""
        # Use a simple HEAD request for path checking — no need for DataForSEO here
        try:
            resp = requests.head(
                url,
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=10,
                allow_redirects=True,
            )
            return resp.status_code == 200
        except requests.RequestException:
            return False


# --- Utility functions (no state needed) ---

def get_base_url(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def get_domain(url: str) -> str:
    return urlparse(url).netloc


def make_absolute(base_url: str, href: str) -> str:
    return urljoin(base_url, href)


def rate_limit():
    time.sleep(RATE_LIMIT_SECONDS)
