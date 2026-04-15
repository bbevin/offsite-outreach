# Spec: Input pre-filtering

## Goal
Skip low-value URLs **before** any scraping or enrichment work happens, so we never burn DataForSEO / Hunter / Apollo / Anthropic credits on URLs that can't produce a useful outreach contact.

## Filter rules

`should_skip_url(url)` in `classifier.py` runs before `process_url()` and returns `(skip, reason)`. A URL is skipped if any of the following match:

1. **Social platforms** — domain matches `SOCIAL_PLATFORM_BLACKLIST` (reddit, youtube, linkedin, x.com, twitter, tiktok, facebook, instagram, quora, medium). These need community engagement, not scraped outreach. Reason: `social`.
2. **Ecommerce sites** — domain matches `ECOMMERCE_BLACKLIST` (amazon, walmart, target, ebay, etsy, shopify, alibaba, aliexpress, bestbuy, costco, wayfair, homedepot, lowes, kroger, walgreens, cvs, bjs, wegmans, priceritemarketplace). Product/category pages have no editorial author. Reason: `ecommerce`.
3. **Landing pages** — `urlparse(url).path in ("", "/")`. Bare domain or subdomain with no meaningful path. A query string alone (`/?utm=foo`) still counts as a landing page because the path is `/`. Reason: `landing_page`.

Both blacklists match exact domain or any subdomain (`foo.amazon.com` is skipped).

## Behavior

- Skipped URLs **are not dropped** — they appear in the output CSV with:
  - `site_type = "Skipped"`
  - `classification_reason = "prefilter:<reason>"`
  - `send_classification = "not_applicable"`
  - `authority_score = "skipped:<reason>"`
  - `notes = "Skipped before scraping: <reason>"`
- `outreach_finder.py` prints a pre-filter summary at the start of each run, e.g. `Pre-filtered: skipping 476 URLs (18 ecommerce, 248 landing_page, 210 social)`.
- `--no-skip` CLI flag bypasses all pre-filtering for one-off cases.

## Expanding the lists

- New social platforms → add to `SOCIAL_PLATFORM_BLACKLIST` in `classifier.py`.
- New ecommerce domains → add to `ECOMMERCE_BLACKLIST`. Start narrow; expand as we encounter false negatives in real input CSVs.
- Do **not** add affiliate/review sites or vendor blogs to these lists — those should still be classified and processed.

## Acceptance criteria

1. Running the pipeline on the juicebox combined CSV skips all reddit/youtube/linkedin URLs, all amazon/walmart/target URLs, and all bare-domain URLs before any scrape call is made.
2. Skipped URLs appear in the output CSV with `site_type=Skipped` and the correct `prefilter:<reason>`.
3. `--no-skip` flag processes everything (escape hatch).
4. Tests in `tests/test_filtering.py` cover all three skip reasons plus the non-skip case.
