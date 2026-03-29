from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AuthorInfo:
    name: str = ""
    url: str = ""


@dataclass
class ContactInfo:
    contact_type: str = ""  # affiliate_form, contact_form, direct_contact
    contact_form_url: str = ""
    notes: str = ""


@dataclass
class TeamContact:
    name: str = ""
    role: str = ""
    url: str = ""


@dataclass
class OutreachResult:
    url: str = ""
    priority: str = ""
    domain: str = ""
    company_name: str = ""
    site_type: str = ""
    classification_reason: str = ""
    contact_type: str = ""
    contact_form_url: str = ""
    author_name: str = ""
    author_url: str = ""
    linkedin_search_url: str = ""
    company_about_url: str = ""
    team_contacts: str = ""
    notes: str = ""
    extras: dict = field(default_factory=dict)

    _BASE_HEADERS = [
        "url", "priority", "domain", "company_name", "site_type", "classification_reason",
        "contact_type", "contact_form_url",
        "author_name", "author_url",
        "linkedin_search_url", "company_about_url",
        "team_contacts", "notes",
    ]

    def csv_headers(self) -> list[str]:
        extra_keys = sorted(self.extras.keys()) if self.extras else []
        return self._BASE_HEADERS + extra_keys

    def to_row(self) -> list[str]:
        base = [
            self.url, self.priority, self.domain, self.company_name,
            self.site_type, self.classification_reason,
            self.contact_type, self.contact_form_url,
            self.author_name, self.author_url,
            self.linkedin_search_url, self.company_about_url,
            self.team_contacts, self.notes,
        ]
        extra_keys = sorted(self.extras.keys()) if self.extras else []
        return base + [self.extras.get(k, "") for k in extra_keys]
