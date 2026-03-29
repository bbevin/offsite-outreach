# Implementation Plan

## Phase 1: Fix the Foundation

- [x] **Task 1: Add direct HTTP fallback to scraper**
  When DataForSEO fails to fetch a page, fall back to a direct `requests.get` with browser-like headers before returning None. This fixes the Salesflare-type failures where the page is accessible but DataForSEO can't reach it.
  Spec: `specs/scraping-reliability.md`

- [x] **Task 2: Fix author extraction quality**
  Reject author names that match common navigation terms (Home, Menu, About, Contact, etc.). Add a blocklist of junk names. Validate that extracted names look like real human names (capitalized words, 2-4 parts, no URLs).
  Spec: `specs/contact-identification.md`

- [x] **Task 3: Fix team contacts junk text**
  Filter out cookie banner text, legal boilerplate, and other non-contact content from team_contacts extraction. Add a junk pattern blocklist.
  Spec: `specs/contact-identification.md`

- [x] **Task 4: Fix company name extraction**
  Use known site names from `classifier.py` when available instead of falling back to domain parsing. Ensure proper casing ("Capsule CRM" not "Capsulecrm").
  Spec: `specs/contact-identification.md`

- [ ] **Task 5: Implement affiliate vs. outreach classification**
  Replace the old site_type system with the new two-bucket classification. Use the known affiliate site list (~80+ domains) as the primary signal. For unknown domains, detect affiliate signals from page content: affiliate disclosure language, tracking parameters in outbound links, "list your product" pages, content structure patterns. Vendor blogs and non-affiliate orgs (like US Chamber) must NOT be classified as affiliate just because they have a partner page. See classifier.py for the updated known site lists.
  Spec: `specs/affiliate-vs-outreach.md`

- [ ] **Task 6: Add dynamic affiliate detection for unknown sites**
  For sites not in any known list, scan page content for affiliate signals: disclosure text ("we may earn a commission", "affiliate links"), affiliate tracking params in outbound links (?ref=, ?tag=, redirect domains), and content structure (comparison tables with CTA buttons). If no signals found, default to outreach and flag for human review.
  Spec: `specs/affiliate-vs-outreach.md`

- [ ] **Task 7: Extract affiliate outreach instructions**
  For every affiliate site, scrape the partner/advertise/intake page (the URL in contact_form_url) and extract the specific instructions they provide for getting listed. Capture: submission process, required affiliate network, pricing if visible, contact info, eligibility requirements. Store in new `affiliate_instructions` output field.
  Spec: `specs/affiliate-vs-outreach.md`

- [ ] **Task 8: Add send_classification field**
  Add `send_classification` and `authority_score` fields to OutreachResult. For vendor/outreach targets: classify as `manual_send` (recognized brand, high authority) or `auto_send` (low authority, unknown publisher). For affiliate targets: set to `not_applicable`. Update CSV output.
  Spec: `specs/send-classification.md`

## Phase 2: Enrich Contact Data

- [ ] **Task 9: Generate candidate email addresses**
  For outreach targets where we have an author name and domain, generate candidate emails using common patterns (first@domain, first.last@domain, firstl@domain). Store as `author_email_candidates` field.
  Spec: `specs/contact-identification.md`

- [ ] **Task 10: Improve LinkedIn contact resolution**
  Generate more targeted LinkedIn search URLs using author name (not just company name). Where possible, attempt to construct a direct profile URL from author metadata.
  Spec: `specs/contact-identification.md`

- [ ] **Task 11: Detect affiliate networks**
  For affiliate/review pages, scan for affiliate network indicators (Impact, ShareASale, CJ Affiliate, Awin, Partnerize, Rakuten). Surface which network the site uses so the outreach team knows if they need to be on that network.
  Spec: `specs/affiliate-vs-outreach.md`

## Phase 3: Automated Outreach

- [ ] **Task 12: Design email template system**
  Create a template system for auto_send outreach emails. Templates should support variable substitution (company name, author name, article URL, product name). Store templates in `templates/`.
  Spec: `specs/send-classification.md`

- [ ] **Task 13: Integrate email sending**
  Connect to an email sending service for auto_send targets. Send templated emails, log attempts and responses.
  Spec: `specs/send-classification.md`
