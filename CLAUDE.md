# Offsite Outreach Pipeline

## Credentials

All API credentials are stored in `.env` in the project root. Source it before running the pipeline:

```bash
set -a && source .env && set +a
```

Current keys in `.env`:
- `DATAFORSEO_USERNAME` / `DATAFORSEO_PASSWORD` — page scraping
- `HUNTER_API_KEY` — email enrichment (primary)

- `APOLLO_API_KEY` — email enrichment (fallback)
- `ANTHROPIC_API_KEY` — LLM author extraction fallback

## Product Wishlist

Future features and improvements are tracked in `PRODUCT_WISHLIST.md`.

## Running the pipeline

```bash
source .env && python3 outreach_finder.py input.csv output.csv
```
