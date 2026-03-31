# Spec: Scraping Reliability

## Goal
Maximize the number of URLs that return usable page content. A "Failed to fetch page" result with no data is a system failure.

## Current state
- DataForSEO is the only scraping mechanism (3-tier: instant pages, raw HTML, content parsing)
- When all three fail, the system checks `known_sites.py` for hardcoded fallback data
- If no fallback exists, the URL gets empty results with "Failed to fetch page"
- Known failure: blog.salesflare.com returns no data despite being publicly accessible

## Required fallback chain

```
DataForSEO instant pages
  |  (fail)
  v
DataForSEO raw HTML
  |  (fail)
  v
DataForSEO content parsing
  |  (fail)
  v
Direct HTTP GET (requests library, browser-like User-Agent)    <-- NEW
  |  (fail)
  v
known_sites.py hardcoded fallback
  |  (not found)
  v
Return empty result with "Failed to fetch page" note
```

## Direct HTTP fallback requirements
- Use a realistic User-Agent header (Chrome on desktop)
- Follow redirects (allow_redirects=True)
- Timeout: 15 seconds
- Parse response with BeautifulSoup + lxml (same as DataForSEO path)
- Only attempt if DataForSEO returned None (don't duplicate successful fetches)

## Acceptance criteria

1. blog.salesflare.com successfully returns parsed HTML via the direct fallback
2. Sites that DataForSEO can already fetch are unaffected (no behavior change)
3. The `notes` field indicates which fetch method succeeded (e.g., "Fetched via direct HTTP fallback")
4. The fallback does not add more than 15 seconds of latency per URL (timeout bound)
