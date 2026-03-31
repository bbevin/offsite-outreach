# Offsite Outreach & Negotiation System - Design Document

## 1. Objective

Get a given company placed into high-ranking "best X" listicle articles across the web. The system ingests a list of target URLs, analyzes each one to determine the outreach strategy, extracts contact information, and prepares the data needed to either automate or manually execute outreach.

## 2. Metrics for Success

1. **Accurate affiliate vs. outreach classification** — The system correctly identifies whether a URL is an affiliate play (requiring a form submission or formal intake process on the site) or an outreach play (requiring direct contact with the article author/editor). Misclassification here wastes effort: submitting a partner form to a vendor blog goes nowhere, and cold-emailing an affiliate site that has a self-serve intake process is unnecessary friction.

2. **Accurate contact identification** — For outreach targets, the system surfaces the right person (article author or editor) with a working LinkedIn profile URL or email address. For affiliate targets, it identifies the correct intake steps (partner form URL, media kit, affiliate network). A result that says "contact found" but points to the wrong person or a dead link is a failure.

3. **Accurate manual vs. automated send classification** — For non-affiliate (outreach) targets, the system correctly distinguishes between sites that require a carefully written manual pitch (reputable tech companies, major publishers) and sites where a templated automated email is appropriate (low-authority SEO blogs, thin content sites). Over-automating damages reputation with important targets; over-manualizing wastes time on low-value ones.

## 3. How It Works Today

### Input
A CSV of target URLs with priority scores. These are typically "best X" listicle articles where we want our company included.

### Pipeline

```
input.csv
  |
  v
[1. Scrape] ── DataForSEO API (3-tier fallback) ── known_sites.py fallback
  |
  v
[2. Classify] ── Map domain to site type (Affiliate/Review, Vendor Blog, Publisher/Editorial, etc.)
  |
  v
[3. Extract] ── Author name/URL, company name, contact method, team contacts, LinkedIn search
  |
  v
output.csv
```

### Current Modules

| Module | Responsibility |
|---|---|
| `outreach_finder.py` | Orchestrator. Reads input, runs pipeline, writes output. |
| `scraper.py` | Page fetching via DataForSEO API. Three strategies: instant pages, raw HTML, content parsing. |
| `classifier.py` | Hardcoded domain-to-type mapping. Falls back to "Unknown". |
| `extractors.py` | Author extraction (meta/JSON-LD/CSS/regex), contact detection (link scanning, path probing), team page mining, LinkedIn URL builder. |
| `known_sites.py` | Hardcoded contact info for major publishers that block scraping (Forbes, Reddit, NYT, etc.). |
| `models.py` | Data classes: `AuthorInfo`, `ContactInfo`, `TeamContact`, `OutreachResult`. |

### Output Fields
`url`, `priority`, `domain`, `company_name`, `site_type`, `contact_type`, `contact_form_url`, `author_name`, `author_url`, `linkedin_search_url`, `company_about_url`, `team_contacts`, `notes` (plus any extra columns from input).

## 4. Target Architecture

The system should handle two fundamentally different outreach workflows based on site type.

### 4.1 Site Classification

Every URL is classified into one of two primary buckets that determine the outreach strategy:

| Classification | Description | Examples |
|---|---|---|
| **Vendor Page** | Article published by another company (competitor or adjacent). Written by an employee, not an independent reviewer. | `capsulecrm.com/blog/best-crm-for-founders`, `blog.salesflare.com/best-crm-for-startups` |
| **Affiliate/Review Page** | Article published by an independent reviewer, affiliate marketer, or editorial outlet monetized through affiliate links or sponsored content. | `techradar.com`, `crm.org`, `pcmag.com`, `forbes.com` |

Secondary types (Social/Forum, Industry/Trade Org) may exist but are lower priority.

### 4.2 Vendor Page Workflow

**Goal:** Identify the person who controls the article content and prepare outreach to request inclusion.

**Required output:**
- Author name and profile URL
- Author LinkedIn profile (direct link, not just a search)
- Estimated author email address (pattern-based: e.g., `firstname@domain.com`)
- Other editorial contacts from the team/about page (name, role, LinkedIn)
- **Send classification:** `manual_send` or `auto_send`

**Send classification logic:**
| Condition | Classification | Rationale |
|---|---|---|
| Reputable tech company (high domain authority, recognized brand) | `manual_send` | Requires a carefully crafted, personalized pitch. |
| Low-authority SEO page (thin content, small/unknown publisher) | `auto_send` | Can use a templated outreach email. Volume play. |

The authority signal could be derived from:
- Domain authority / traffic rank (available via DataForSEO or similar)
- Presence in `KNOWN_CLASSIFICATIONS` as a recognized brand
- Manual override in input CSV

### 4.3 Affiliate/Review Page Workflow

**Goal:** Determine if the affiliate site has a formal process for requesting product inclusion, and surface it.

**Required output:**
- Whether a formal intake process exists (partner form, media kit, sponsor page)
- Direct URL to the intake form/page
- If no formal process: fallback contact info (author email, general contact form)
- Affiliate network detection (e.g., if they use Impact, ShareASale, CJ — our company may need to be on that network first)

### 4.4 Shared Output

Both workflows produce:
- `company_name`, `domain`, `site_type`
- `contact_type`: one of `affiliate_form`, `contact_form`, `direct_contact`
- `contact_form_url`: link to the relevant form/page
- `send_classification`: `manual_send`, `auto_send`, or `not_applicable`
- `notes`: processing context, fallback reasons

## 5. Key Gaps (Current State vs. Target)

### 5.1 Scraping Reliability
- **Problem:** DataForSEO is the only fetch mechanism. When it fails (e.g., Salesflare), the entire extraction is skipped with no data.
- **Fix:** Add a direct `requests` fallback with browser-like headers before giving up. Reserve `known_sites.py` as a last resort for sites that actively block all scraping.

### 5.2 Classification Accuracy
- **Problem:** Classification is a static hardcoded map. Unknown domains get "Unknown" and aren't routed to the right workflow.
- **Fix:** Use page signals to classify dynamically:
  - Affiliate disclosure presence -> Affiliate/Review
  - Author is an employee of the domain's company -> Vendor Blog
  - Domain matches a known pattern (e.g., `blog.{company}.com`) -> Vendor Blog

### 5.3 Send Classification (New)
- **Problem:** No concept of `manual_send` vs `auto_send` exists yet. All results are treated the same.
- **Fix:** Add authority scoring. For vendor pages, flag high-authority sites as `manual_send` and low-authority as `auto_send`.

### 5.4 Contact Quality
- **Problem:** Author extraction is noisy (e.g., "Home" extracted as author name for boringbusinessnerd.com). Team contacts pick up cookie banner text. Company names aren't properly cased.
- **Fix:** Add validation heuristics:
  - Reject author names that match common navigation terms
  - Filter team contact text against known junk patterns (cookie banners, legal boilerplate)
  - Use `known_sites.py` name as company name when available

### 5.5 Email Discovery (New)
- **Problem:** No email extraction or generation. LinkedIn search URL is the closest thing, but it's a generic search, not a direct profile link.
- **Fix:** For vendor pages, generate candidate emails from author name + domain using common patterns (`first@`, `first.last@`, `firstl@`). Optionally verify via SMTP or an email verification API.

### 5.6 Automated Send (Future)
- **Problem:** The system currently only produces a CSV. The next step — actually sending outreach — is not implemented.
- **Fix:** Phase 2. For `auto_send` targets, integrate with an email sending service using templated outreach. For `affiliate_form` targets with a known intake URL, potentially auto-fill forms.

## 6. Proposed Phases

### Phase 1: Fix the Foundation
- Add direct HTTP fallback to scraper
- Fix extraction quality issues (author validation, junk filtering, company name cleanup)
- Add `send_classification` field to the output model
- Implement authority-based send classification for vendor pages

### Phase 2: Enrich Contact Data
- Email pattern generation for vendor page contacts
- Direct LinkedIn profile resolution (vs. generic search URL)
- Affiliate network detection for review pages

### Phase 3: Automated Outreach
- Email template system for `auto_send` targets
- Integration with email sending service
- Tracking/logging of outreach attempts and responses

## 7. Ralph Loop Protocol

This project uses a Ralph Loop for autonomous development. The agent runs in a `while :; do cat PROMPT.md | claude ; done` loop, picking one task per iteration from `IMPLEMENTATION_PLAN.md`, implementing it, testing it, committing, and exiting.

### Blocked Task Protocol

Some tasks require human input before the agent can proceed — classification decisions, API credentials, authority thresholds, etc. When the agent encounters a dependency it cannot resolve on its own, it must:

1. **Mark the task as `[BLOCKED]`** in `IMPLEMENTATION_PLAN.md`
2. **Create a detailed block report** in `blocked/` (one file per blocked task, e.g., `blocked/email-verification-api.md`)
3. **Move on** to the next unblocked task

Each block report must include:

```markdown
# Blocked: <task name>

## What I was trying to do
<1-2 sentences on the task and why it matters>

## Why I'm blocked
<Specific dependency or decision needed. Be precise — "need API key" is not enough.>

## What I tried
<Any research, alternatives explored, or partial work completed before blocking>

## Recommendations
<Ranked list of options for the human to unblock this, with pros/cons for each>

## What I'll do once unblocked
<Exactly what the agent will implement once the blocker is resolved — so the human
knows what they're unblocking and can provide the right level of detail>

## Interim impact
<What other tasks are affected by this blocker, if any. Can the system still run
without this? What degrades?>
```

The human unblocks by:
- Editing the block report with a decision/answer
- Changing the task status from `[BLOCKED]` to `[ ]` in `IMPLEMENTATION_PLAN.md`
- Optionally adding context files the agent should read

The agent checks for resolved blockers at the start of each iteration by scanning for `[ ]` tasks that have a corresponding `blocked/*.md` file with human edits.

### Task States

```
[ ]        — Ready to pick up
[x]        — Completed
[BLOCKED]  — Waiting on human input (see blocked/ directory)
[SKIPPED]  — Deprioritized or no longer relevant
```

## 8. Data Model (Target)

```
OutreachResult:
  # Identity
  url: str
  domain: str
  company_name: str
  site_type: str                    # "Vendor Blog" | "Affiliate/Review" | ...
  priority: str

  # Classification
  send_classification: str          # "manual_send" | "auto_send" | "not_applicable"
  authority_score: str              # signal used for send classification

  # Contact - Primary
  contact_type: str                 # "affiliate_form" | "contact_form" | "direct_contact"
  contact_form_url: str
  affiliate_instructions: str       # NEW: specific steps for getting listed on affiliate sites

  # Contact - People
  author_name: str
  author_url: str
  author_email: str                 # NEW: generated or discovered
  author_linkedin: str              # NEW: direct profile URL
  team_contacts: str                # name (role) pairs
  linkedin_search_url: str

  # Meta
  company_about_url: str
  notes: str
  extras: dict                      # passthrough from input CSV
```
