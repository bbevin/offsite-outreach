# Spec: Send Classification (Manual vs. Automated)

## Goal
For non-affiliate (outreach) targets, classify whether the outreach email should be manually written or can be sent via an automated template. This only applies to Vendor Blog / outreach play sites.

## Classification logic

### manual_send
The site is a reputable, recognized company where a poorly written or generic email would damage the relationship or get ignored. Signals:
- Domain is a recognized brand (present in `KNOWN_CLASSIFICATIONS` with a proper name)
- High domain authority or traffic (if available from DataForSEO or similar)
- Company has a significant web presence (multiple subdomains, large site)
- The article is on a primary company blog (not a guest post on a micro-site)

### auto_send
The site is a small, low-authority publisher where a templated email is appropriate. Signals:
- Domain is not recognized (not in `KNOWN_CLASSIFICATIONS`)
- Low traffic / niche site
- Thin content (few pages, minimal site structure)
- Personal blog or micro-site pattern (single author, no team page)

### not_applicable
- Site is classified as affiliate play — outreach is via form submission, not email
- Site is Social/Forum — outreach is via the platform's ad system

## Authority signals (in priority order)

1. **Known brand list** — If the domain is in `KNOWN_CLASSIFICATIONS` with a recognized name, it's `manual_send`. This is the most reliable signal and works without any external API.
2. **Domain authority score** — If available from DataForSEO or a similar API. Threshold TBD (likely needs human input to calibrate).
3. **Site structure heuristics** — Has team/about page, multiple authors, structured navigation = higher authority.
4. **Manual override** — Input CSV can include a `send_override` column to force classification.

## Output fields

- `send_classification`: `manual_send` | `auto_send` | `not_applicable`
- `authority_score`: The primary signal used (e.g., "known_brand", "da:45", "heuristic:low")

## Acceptance criteria

1. Every row in output.csv has a `send_classification` value
2. Affiliate/Review sites are always `not_applicable`
3. Known vendor brands (Salesflare, Capsule CRM) are `manual_send`
4. The system has a clear, defensible reason for each classification (visible in `authority_score`)
5. Manual override from input CSV is respected when present
