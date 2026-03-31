# Spec: Affiliate vs. Outreach Classification

## Goal
Accurately classify each URL as either an **affiliate play** or an **outreach play**. This is the first and most important routing decision — it determines the entire downstream workflow.

## Definitions

**Affiliate play** — The site's business model depends on sending traffic to other companies' products and getting paid for it (CPC, CPL, CPA, affiliate commissions, pay-for-inclusion). Getting listed requires a formal submission (partner form, media kit, affiliate network enrollment) rather than personal outreach. Examples: G2, Capterra, PCMag, TechRadar, NerdWallet.

**Outreach play** — The site sells its own product/service, or is an organization whose content is not driven by affiliate revenue. Getting listed requires direct outreach to the person who controls the content. Examples: Capsule CRM, Salesflare, US Chamber of Commerce.

## The core test

> Does this site's business model depend on sending qualified traffic to other companies' products, and getting paid for that traffic?

If yes -> Affiliate. If no -> Outreach.

**A partner/media/sponsor page alone does NOT make a site an affiliate site.** Many non-affiliate organizations accept sponsors (industry orgs, conferences, trade associations). The test is whether affiliate revenue is the primary business model.

## Classification signals

### Affiliate/Review indicators
1. **Known affiliate site list** — Domain is in `KNOWN_AFFILIATE_SITES` in classifier.py (~80+ sites). This is the most reliable signal.
2. **Affiliate disclosure language** on the page:
   - "we may earn a commission"
   - "affiliate links"
   - "advertising disclosure"
   - "at no extra cost to you"
   - "how we make money"
3. **Affiliate tracking parameters** in outbound links:
   - `?ref=`, `?tag=`, `?aff=`, `?via=`, `?partner=`
   - Redirect domains: `go.redirectingat.com`, `click.linksynergy.com`, `shareasale.com`, `tracking.impact.com`
   - Site-owned redirects: `/go/`, `/out/`, `/redirect/`, `/recommends/`
4. **"List Your Product"** or **CPC/CPL pricing page** describing how vendors can get listed
5. **Content structure**: organized by product categories, heavy on "Best X" listicles with comparison tables and CTA buttons

### Outreach (non-affiliate) indicators
- Site sells its own product/service as primary revenue
- Domain matches vendor pattern: `blog.{company}.com`, `{company}.com/blog/`
- Author is an employee of the domain's company
- Site promotes its own product as top recommendation in the article
- No affiliate disclosure present
- Revenue comes from subscriptions, membership, events, consulting — not referral commissions

### Explicitly NOT affiliate
These categories should always be classified as outreach, even if they have partner/sponsor pages:
- **Industry organizations** (US Chamber, CompTIA, SaaStr) — revenue is membership/events
- **Vendor blogs comparing competitors** (HubSpot, Salesflare, Capsule) — revenue is SaaS subscriptions
- **News publishers with ad sales** (WSJ, Bloomberg) — revenue is subscriptions/display ads
- **Platform marketplaces** (Salesforce AppExchange, Shopify App Store) — revenue is platform take rate
- **Analyst firms** (Gartner research, Forrester) — revenue is research subscriptions/consulting

### Hybrid sites (edge cases)
Some sites sell their own product AND earn affiliate commissions (Zapier, HubSpot, ClickUp). The test: if you remove the affiliate revenue, does the site still have a viable business? If yes (SaaS revenue), classify as **outreach** (Vendor Blog).

### Known parent companies
Sites owned by these companies are almost certainly affiliate operations:
- **Future plc**: TechRadar, Tom's Guide, Tom's Hardware, Laptop Mag, Windows Central
- **Red Ventures**: CNET, ZDNet, Bankrate, CreditCards.com
- **Dotdash Meredith**: Investopedia, Lifewire, The Balance
- **Ziff Davis**: PCMag, Mashable
- **Gartner Digital Markets**: Capterra, GetApp, Software Advice

## Affiliate outreach instructions extraction

For every affiliate site, the system must also scrape the partner/advertise/intake page and extract the **specific instructions** the site provides for getting listed. This goes in the `affiliate_instructions` output field.

### What to extract
- Step-by-step submission process (if documented)
- Required affiliate network enrollment (e.g., "Join our program on Impact Radius")
- Pricing info if visible (CPC rates, sponsorship packages, listing fees)
- Contact email or form for ad sales / partnerships
- Turnaround time or review process details
- Any eligibility requirements ("must have 100+ reviews", "SaaS products only")

### Where to find it
Scrape the URL found in `contact_form_url` (the partner/advertise/media kit page) and extract the relevant content. If the page is a form, note "online form submission" and describe any visible fields. If the page describes a process, summarize the steps.

### Examples of good output
- "Submit product via partner form at techradar.com/about-us#affiliate. Requires product details and affiliate network info."
- "G2 vendor profile: claim your profile at sell.g2.com. Free tier available. Paid tiers start at $X/mo for enhanced listings and lead capture."
- "Reddit: self-serve ad platform at ads.reddit.com. Create campaign targeting specific subreddits. No editorial review process."
- "Forbes Advisor: contact Forbes Connect (forbes.com/connect) for branded content partnerships. Enterprise pricing, not self-serve."

## Acceptance criteria

1. Every URL in output.csv has a `site_type` that correctly reflects whether it's an affiliate or outreach play.
2. Sites are NEVER classified as affiliate solely because they have a partner/sponsor page.
3. All sites in the current input/output are classified correctly:
   - techradar.com -> Affiliate/Review
   - crm.org -> Affiliate/Review
   - capsulecrm.com -> Vendor Blog (outreach)
   - reddit.com -> Affiliate/Review
   - boringbusinessnerd.com -> Affiliate/Review
   - forbes.com -> Affiliate/Review
   - uschamber.com -> Outreach (NOT affiliate — industry org with sponsor page)
   - pcmag.com -> Affiliate/Review
   - blog.salesflare.com -> Vendor Blog (outreach)
4. Classification works for domains not in the known lists by using page signals (affiliate disclosure, tracking params, content structure).
5. Every affiliate site has an `affiliate_instructions` field with specific steps for getting listed, extracted from the partner/advertise page.
6. Unknown sites default to outreach and are flagged for human review.
