# Agent Operational Guide

You are an autonomous agent working on the Offsite Outreach & Negotiation System. You run in a Ralph Loop — each invocation starts with fresh context. All state lives on disk.

## Your workflow each iteration

1. Read `IMPLEMENTATION_PLAN.md` to find the highest-priority `[ ]` task
2. Check `blocked/` for any resolved blockers (human may have edited a block file and flipped a task back to `[ ]`)
3. Read the relevant spec in `specs/` for acceptance criteria
4. Read `DESIGN.md` for architectural context
5. Implement the task — one task only, keep scope tight
6. Test your work: run the pipeline against `input.csv` and validate output
7. If the task cannot be completed due to a dependency you can't resolve:
   - Mark it `[BLOCKED]` in `IMPLEMENTATION_PLAN.md`
   - Write a detailed block report to `blocked/<task-slug>.md` (see DESIGN.md section 7 for format)
   - Move on to the next `[ ]` task
8. If the task is done: mark it `[x]`, commit your changes, `git push`, and exit

## Rules

- ONE task per iteration. Do not combine tasks.
- Do NOT modify specs or the design doc unless a task explicitly calls for it.
- Do NOT guess API keys, credentials, or external service decisions. Block and move on.
- Always run the test suite after code changes (see Testing Protocol below). If DataForSEO credentials aren't available, test what you can (imports, unit logic, data model changes) and note the limitation.
- Commit and push after completing a task. Commit message format: `[task-N] short description`. Always `git push` after committing so progress is visible on GitHub.
- If all remaining tasks are `[BLOCKED]`, exit with a message summarizing what's blocked and what the human needs to do.

## Testing Protocol

Every code change must pass the test suite before committing. The test suite lives in `tests/` and is run via `./run_tests.sh`.

### 1. Run the full test suite

```bash
./run_tests.sh
```

All tests must pass (exit code 0). Do NOT commit if any tests fail.

### 2. What the tests cover

| Test file | Module(s) tested | What it validates |
|---|---|---|
| `tests/test_classifier.py` | `classifier.py` | Known-list classification (affiliate, outreach, non-affiliate), www stripping, subdomain matching, content-based signals (disclosure, affiliate links, content structure), vendor blog domain patterns, no false positives |
| `tests/test_extractors.py` | `extractors.py` | Author name validation (blocklists, length, casing, connectors, domain match), author extraction (meta/JSON-LD/CSS/byline), company name extraction, email candidate generation, LinkedIn URL building, affiliate network detection, junk text filtering |
| `tests/test_models.py` | `models.py`, `parse_citations.py` | Data class defaults, CSV header generation, extras handling, row serialization, citation parser priority mapping |
| `tests/test_scraper.py` | `scraper.py` | URL utility functions (get_domain, get_base_url, make_absolute) — no network calls |
| `tests/test_pipeline.py` | `outreach_finder.py` | Send classification logic, full process_url with mocked scraper (affiliate sites, vendor blogs, unknown sites, failed fetches, known site fallback), CSV read/write roundtrip |

### 3. When modifying code

- If you change classification logic → run `tests/test_classifier.py`
- If you change extraction logic → run `tests/test_extractors.py`
- If you change the data model → run `tests/test_models.py`
- If you change the pipeline orchestrator → run `tests/test_pipeline.py`
- **Always run the full suite before committing** to catch cross-module regressions

### 4. When adding new functionality

- Add tests for new functions in the corresponding test file
- For new acceptance criteria from specs, add test cases that validate them
- If adding a new module, create `tests/test_<module>.py`

### 5. Test without network access

All tests use mock scrapers and synthetic HTML — no DataForSEO credentials or network access required. This means tests can run in any environment.

### 6. Pipeline smoke test (optional, requires credentials)

If DataForSEO credentials are available, also run:

```bash
python3 outreach_finder.py input.csv test_output.csv
```

This validates the full pipeline against real data but is NOT required for every commit.

## Slack notifications

When you mark a task as `[BLOCKED]`, send a Slack DM to the user (channel ID: `C0APQ0G2SA0`) using the `mcp__claude_ai_Slack__slack_send_message` tool. The message must include:

- Which task is blocked (task number and name)
- A brief summary of why (2-3 sentences max)
- Your top recommendation for unblocking
- A pointer to the full block report file (e.g., "Full details in `blocked/email-verification-api.md`")

Format example:
```
*Ralph Loop: Task blocked* 🚧

*Task 11: Integrate email sending* is blocked.
Need a decision on which email sending service to use — the system needs API credentials and the choice affects template format. I recommend SendGrid (best API ergonomics for transactional email, free tier covers testing).

Full details and all options: `blocked/email-sending-service.md`
```

Also send a Slack DM when all remaining tasks are blocked, summarizing everything that needs human input.

## Key files

| File | Purpose | Read/Write |
|------|---------|------------|
| `IMPLEMENTATION_PLAN.md` | Task list with priorities and statuses | Read + Write (status updates only) |
| `DESIGN.md` | Architecture and requirements | Read only |
| `AGENTS.md` | This file. Your operational guide. | Read only |
| `specs/*.md` | Acceptance criteria per feature area | Read only |
| `blocked/*.md` | Block reports for human review | Write |
| `outreach_finder.py` | Pipeline orchestrator | Read + Write |
| `scraper.py` | Page fetching | Read + Write |
| `extractors.py` | Data extraction logic | Read + Write |
| `classifier.py` | Site classification | Read + Write |
| `models.py` | Data model | Read + Write |
| `known_sites.py` | Hardcoded fallback data | Read + Write |
| `tests/test_*.py` | Test suite | Read + Write |
| `run_tests.sh` | Test runner | Read only |
| `parse_citations.py` | Citation CSV parser | Read + Write |
| `input.csv` | Test input | Read only |
| `output.csv` | Production output | Do not modify |
