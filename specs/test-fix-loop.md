# Spec: Test-Fix Loop

## Purpose

The test-fix loop is an automated quality improvement cycle. It runs integration tests against live data, audits the output CSV for data quality defects, fixes one defect per iteration, and verifies the fix doesn't cause regressions.

## Quality Rules

These rules are applied to every row in the integration test output CSV. A row that violates any rule is a defect.

### R1: site_type must be valid

`site_type` must be one of: `Affiliate/Review`, `Vendor Blog`, `Outreach`.

No row should have an empty site_type or any value not in this list.

### R2: Known vendors must not be classified as unknown

The following domains (and their subdomains) are known vendors and must be classified as `Vendor Blog`, not `Outreach` with `unknown_default:needs_review`:

- zendesk.com — Zendesk
- hubspot.com — HubSpot
- freshworks.com — Freshworks
- zoho.com — Zoho
- pipedrive.com — Pipedrive
- monday.com — Monday.com
- insightly.com — Insightly
- nutshell.com — Nutshell
- copper.com — Copper
- close.com — Close
- streak.com — Streak
- nimble.com — Nimble
- keap.com — Keap
- agilecrm.com — Agile CRM
- sugarcrm.com — SugarCRM
- vtiger.com — Vtiger
- bitrix24.com — Bitrix24

If a domain appears in the CSV with `classification_reason` containing `unknown_default`, check whether it is a known SaaS vendor. If so, add it to `KNOWN_OUTREACH_SITES` in `classifier.py`.

### R3: Known social/platform sites must not be classified as unknown

- youtube.com — YouTube (Social, not_applicable)
- linkedin.com — LinkedIn (Social, not_applicable)
- twitter.com / x.com — Twitter/X (Social, not_applicable)
- facebook.com — Facebook (Social, not_applicable)
- quora.com — Quora (Social, not_applicable)

These should be in the known lists. Classify social/forum sites as `Affiliate/Review` with `not_applicable` send classification, since outreach doesn't apply.

### R4: contact_form_url must not contain ad/tracking URLs

`contact_form_url` must never contain:
- `doubleclick.net` or `adclick.g.doubleclick.net`
- `googlesyndication.com`
- `googleadservices.com`
- Any URL longer than 500 characters (likely a tracking redirect)
- URLs with `utm_source`, `utm_medium`, `utm_campaign` as the primary path (ad landing pages)

If a contact_form_url violates this rule, the extraction logic in `extractors.py` needs a URL filter.

### R5: author_name must be a real person's name

`author_name` must pass ALL of these checks:
- 2 to 4 words, each capitalized
- No company/brand names (should not match company_name or domain)
- No generic terms ("Reviews", "Team", "Staff", "Editorial")
- No strings ending in "Reviews", "Media", "Group", "Inc", "LLC"
- No single-word names unless clearly a mononym (rare, flag for review)

Specific known-bad patterns:
- "HomeStartup Reviews" — contains "Reviews", not a person
- "Editorial Team", "Staff Writer" — generic, already in blocklist but verify
- Domain name as author (e.g., "Pcmag" or "Techradar")

### R6: company_name must not be empty for known sites

If the domain is in any known list, `company_name` must be populated with the proper name from that list.

### R7: send_classification must be consistent with site_type

- If `site_type` is `Affiliate/Review` then `send_classification` must be `not_applicable`
- If `site_type` is `Vendor Blog` then `send_classification` must be `manual_send`
- If `site_type` is `Outreach` then `send_classification` must be `manual_send` or `auto_send`

A known vendor (like Zendesk) classified as `auto_send` is wrong — known vendors are always `manual_send`.

### R8: team_contacts must not contain cookie/legal junk

`team_contacts` field must not contain:
- "Always Active" (cookie consent UI)
- "Marketing cookies"
- "cookie policy" / "privacy policy"
- "Meal Kits" or other unrelated product categories scraped from nav
- Text matching pattern: `Always Active (*)`

### R9: affiliate_instructions must not be garbled

`affiliate_instructions` must not contain:
- Raw HTML form field names (e.g., "form_build_id, form_id")
- Entire newsletter signup forms masquerading as intake instructions
- Marketing copy paragraphs unrelated to the intake process
- More than 500 characters of non-actionable text

If the extraction is pulling in junk, the `extract_affiliate_instructions()` function needs better text filtering.

### R10: Bot-protected sites should have graceful notes

If a page cannot be scraped (Forbes, Reddit, etc.), the `notes` field should explain this clearly. The result should still have correct site_type and company_name from the known lists.

### R11: verified_email must be a valid email format

If `verified_email` is non-empty, it must:
- Contain exactly one `@`
- Have a domain part matching the `domain` column (or a known alias)
- Not be a generic address (info@, support@, admin@, noreply@)

### R12: email_source must be consistent

- If `verified_email` is non-empty, `email_source` must be "hunter"
- If `verified_email` is empty and `author_email_candidates` is non-empty,
  `email_source` must be "pattern"
- If both are empty, `email_source` must be ""

## Severity Classification

| Severity | Definition | Action |
|----------|-----------|--------|
| CRITICAL | Wrong site_type, ad URLs in contact fields | Fix immediately |
| HIGH | Known vendor as unknown, junk author names, missing required fields | Fix this iteration if no CRITICAL |
| MEDIUM | Garbled affiliate_instructions, cookie text in team_contacts | Fix after HIGH |
| LOW | Minor formatting, verbose notes | Skip unless nothing else to fix |

## Fix Ledger

All fixes are tracked in `test_results/fixes.log`. Each line records:
- Timestamp
- Severity
- Domain or pattern affected
- Description of the fix

The agent reads this file at startup to avoid re-fixing the same issue.

## Stopping Conditions

The test-fix loop should stop when:
1. All quality rules pass on the latest CSV output
2. All remaining defects are LOW severity
3. All remaining defects require human judgment (blocked)
4. Max iterations reached (safety net)

## Blocking Conditions

Write a block report to `blocked/testfix-<slug>.md` when:
- The correct classification for a domain is ambiguous
- A fix would require changing a spec
- The defect requires API credentials or external data not available
- A fix would break an existing unit test that enforces intentional behavior

## Relationship to Main Loop

- The test-fix loop does NOT read or modify `IMPLEMENTATION_PLAN.md`
- It does NOT pick up tasks from the implementation plan
- It operates independently and can run concurrently with the main loop (on a separate branch if needed)
- Commits use the `[testfix]` prefix instead of `[task-N]`
