from __future__ import annotations

# Domain -> (site_type, site_name)
KNOWN_CLASSIFICATIONS: dict[str, tuple[str, str]] = {
    "techradar.com": ("Affiliate/Review", "TechRadar"),
    "crm.org": ("Affiliate/Review", "CRM.org"),
    "capsulecrm.com": ("Vendor Blog", "Capsule CRM"),
    "reddit.com": ("Social/Forum", "Reddit"),
    "boringbusinessnerd.com": ("Affiliate/Review", "Boring Business Nerd"),
    "forbes.com": ("Publisher/Editorial", "Forbes"),
    "uschamber.com": ("Industry/Trade Org", "US Chamber of Commerce"),
    "pcmag.com": ("Affiliate/Review", "PCMag"),
    "blog.salesflare.com": ("Vendor Blog", "Salesflare"),
    "salesflare.com": ("Vendor Blog", "Salesflare"),
    "wirecutter.com": ("Affiliate/Review", "Wirecutter"),
    "cnet.com": ("Affiliate/Review", "CNET"),
    "nerdwallet.com": ("Affiliate/Review", "NerdWallet"),
    "nytimes.com": ("Publisher/Editorial", "The New York Times"),
    "g2.com": ("Affiliate/Review", "G2"),
    "capterra.com": ("Affiliate/Review", "Capterra"),
    "trustradius.com": ("Affiliate/Review", "TrustRadius"),
    "softwareadvice.com": ("Affiliate/Review", "Software Advice"),
    "getapp.com": ("Affiliate/Review", "GetApp"),
    "businessnewsdaily.com": ("Publisher/Editorial", "Business News Daily"),
    "investopedia.com": ("Affiliate/Review", "Investopedia"),
    "thebalancemoney.com": ("Affiliate/Review", "The Balance"),
}


def classify_site(domain: str) -> str:
    """Return the site_type for a domain, or 'Unknown' if not classified."""
    clean = domain.replace("www.", "")
    if clean in KNOWN_CLASSIFICATIONS:
        return KNOWN_CLASSIFICATIONS[clean][0]
    for known_domain, (site_type, _) in KNOWN_CLASSIFICATIONS.items():
        if clean.endswith("." + known_domain):
            return site_type
    return "Unknown"


def get_site_name(domain: str) -> str | None:
    """Return the known site name for a domain, or None."""
    clean = domain.replace("www.", "")
    if clean in KNOWN_CLASSIFICATIONS:
        return KNOWN_CLASSIFICATIONS[clean][1]
    for known_domain, (_, name) in KNOWN_CLASSIFICATIONS.items():
        if clean.endswith("." + known_domain):
            return name
    return None
