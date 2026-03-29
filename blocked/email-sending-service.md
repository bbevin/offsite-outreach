# Blocked: Integrate email sending

## What I was trying to do
Implement email sending integration for `auto_send` targets — the final step in the automated outreach pipeline. This connects the template system (Task 12) to actual email delivery, turning the system from a research tool into an outreach execution tool.

## Why I'm blocked
Need a decision on which email sending service to use and corresponding API credentials. The choice affects:
- How emails are authenticated (SPF/DKIM/DMARC setup on the sending domain)
- Rate limits and deliverability
- Cost structure
- Reply tracking capabilities
- Whether we can use a shared sending domain or need a dedicated one

## What I tried
- Reviewed the existing template system (`templates/auto_send_default.md`, `templates/auto_send_followup.md`) — ready for variable substitution
- Assessed available MCP tools (Gmail is available but unsuitable for programmatic pipeline sends)
- Evaluated common options below

## Recommendations

### Option 1: SendGrid (Recommended)
**Pros:** Best API ergonomics, free tier (100 emails/day) covers testing, excellent deliverability, built-in reply tracking via inbound parse webhook, good Python SDK (`sendgrid`).
**Cons:** Requires domain verification for production sending.
**What I need:** API key + verified sender email address.

### Option 2: Amazon SES
**Pros:** Cheapest at scale ($0.10/1000 emails), integrates well if you're already on AWS.
**Cons:** More setup overhead (sandbox mode requires manual verification of each recipient for testing), no built-in reply tracking.
**What I need:** AWS credentials with SES permissions + verified sender identity.

### Option 3: Mailgun
**Pros:** Good deliverability, generous free tier (1000 emails/month for 3 months), built-in tracking.
**Cons:** Free tier expires, slightly more expensive than SES at scale.
**What I need:** API key + sending domain.

### Option 4: Gmail API (via service account or OAuth)
**Pros:** No additional service to set up, sends from your actual Gmail address.
**Cons:** 500 emails/day limit (personal) or 2000/day (Workspace), harder to track at scale, Google may flag high-volume automated sending.
**What I need:** OAuth credentials or service account with domain-wide delegation.

## What I'll do once unblocked
1. Add the chosen email service's Python SDK to requirements
2. Create `email_sender.py` with: connection setup, template rendering, send function, retry logic, and logging
3. Add a `--send` flag to `outreach_finder.py` that triggers actual sending for `auto_send` rows
4. Create `outreach_log.csv` to track: recipient, template used, send time, status, message ID
5. Add rate limiting to respect the service's sending limits
6. Wire up the followup template with a configurable delay

## Interim impact
**The system is fully functional without this.** All pipeline stages work — scraping, classification, extraction, contact enrichment, and template generation. The output CSV contains everything needed for manual or semi-automated outreach. This task adds the "last mile" of actually pressing send.
