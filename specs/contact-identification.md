# Spec: Contact Identification

## Goal
For every URL, produce actionable contact information — either a person to email (outreach play) or a process to follow (affiliate play).

## Requirements by site type

### Outreach play (Vendor Blog)
The output must include:
- **Author name** — The actual human who wrote the article. Must be a real name (2-4 capitalized words), not a navigation element, brand name, or junk text.
- **Author URL** — Link to the author's profile page on the site (if available).
- **Author LinkedIn** — A LinkedIn search URL that includes the author's full name and company, not just a generic company search.
- **Author email candidates** — Verified email from Hunter.io when available, otherwise pattern-generated emails based on author name + domain.
- **Verified email** — Hunter.io-verified email address (empty if unavailable or low confidence).
- **Email source** — Provenance tracking: "hunter" if verified, "pattern" if fallback-generated.
- **Team contacts** — Marketing/partnerships people from the about/team page. Must be actual names and roles, not cookie banner text or legal boilerplate.

### Affiliate play (Affiliate/Review)
The output must include:
- **Contact form URL** — Direct link to the partner form, media kit, advertise page, or sponsor submission.
- **Contact type** — `affiliate_form` if a formal intake process exists, `contact_form` if only a general contact page was found, `direct_contact` if nothing was found.
- **Affiliate network** — Which network the site uses, if detectable (Phase 2).

## Validation rules

### Author name blocklist
Reject any extracted "author" that matches:
- Navigation terms: Home, Menu, About, Contact, Blog, News, Login, Sign Up, Subscribe, Search
- Generic terms: Admin, Editor, Staff, Team, Contributor, Guest, Anonymous
- Brand names that match the domain (e.g., "Capsule CRM" on capsulecrm.com is the company, not an author)
- Strings containing URLs, email addresses, or special characters
- Strings longer than 60 characters or with more than 4 words

### Team contacts validation
Reject team contact text that contains:
- Cookie consent language ("we use cookies", "accept all", "cookie policy")
- Legal boilerplate ("privacy policy", "terms of service", "all rights reserved")
- Marketing copy (long sentences > 100 chars that aren't name+role pairs)

### Company name
- Use the known site name from `classifier.py` when available
- Fall back to og:site_name meta tag, then JSON-LD, then domain parsing
- Domain-parsed names must be properly cased ("Capsule CRM" not "Capsulecrm")

## Acceptance criteria

1. No junk author names in output (Home, Menu, navigation terms, etc.)
2. No cookie/legal text in team_contacts field
3. Company names match known proper names when available
4. LinkedIn search URLs include author name when known (not just company name)
5. Every affiliate site has a contact_form_url or an explicit note explaining why none was found
