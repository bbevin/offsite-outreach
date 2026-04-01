# Product Wishlist

Features and improvements to implement in the future.

---

## Scraper Cache (S3 backing store)

Add a persistent cache for DataForSEO scrape results to avoid re-fetching pages across runs.

- Store scraped HTML in S3 keyed by URL hash (e.g. `s3://bucket/cache/{url_hash}.html.gz`)
- Short TTL (e.g. 7 days) to balance freshness vs. cost
- Fall through to DataForSEO on cache miss, write result back to S3
- Start with SQLite locally for development, swap to S3 for production deployments
- Estimated savings: ~$1/run on current input size, scales linearly with URL list growth
