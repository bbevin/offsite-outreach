# Spec: Hunter.io Email Enrichment

## Goal
Replace pattern-guessed email candidates with verified emails from Hunter.io
when available. Fall back gracefully to pattern generation when the API is
unavailable or returns no result.

## API Details
- Endpoint: `GET https://api.hunter.io/v2/email-finder`
- Params: `domain`, `first_name`, `last_name`, `api_key`
- Response: `{ data: { email, score, first_name, last_name, position, linkedin_url, sources } }`
- Each call = 1 credit

## Requirements

### R1: API key via environment
The `HUNTER_API_KEY` environment variable must be set. If absent, all
enrichment calls return None silently (no errors, no log spam).

### R2: Graceful fallback
If Hunter returns None, an HTTP error, a 402 (credits exhausted), or a
score below 50, the system must fall back to `generate_email_candidates()`.
The pipeline must never crash due to Hunter failures.

### R3: Credit conservation
- Unit tests must NEVER make real HTTP calls (mock `requests.get`)
- Integration tests are in a separate file, skipped by default
- A credits-exhausted flag prevents further API calls in the same run

### R4: Output fields
- `verified_email` — The Hunter-verified email, or empty string
- `email_source` — "hunter" if verified, "pattern" if fallback, "" if no email
- `author_email_candidates` — contains verified email if Hunter succeeded,
  or pattern-generated list if fallback

### R5: Rate limiting
At most 1 Hunter API call per second (conservative default).

## Acceptance Criteria
1. With HUNTER_API_KEY set: pipeline produces verified emails for known domains
2. With HUNTER_API_KEY unset: pipeline produces identical output to pre-integration
3. All existing tests pass without modification
4. `./run_tests.sh` does not consume API credits
5. `test_hunter_integration.py` can be run manually with real key
