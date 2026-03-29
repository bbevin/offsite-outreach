#!/usr/bin/env python3
"""
Email template engine for automated outreach.

Loads templates from the templates/ directory, parses frontmatter for metadata
(name, description, subject line), and renders them with variable substitution.

Templates use {{variable_name}} syntax for placeholders.
"""

import os
import re
from dataclasses import dataclass, field
from typing import Optional

TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")

# Pattern for {{variable_name}} placeholders
VARIABLE_PATTERN = re.compile(r"\{\{(\w+)\}\}")

# Frontmatter delimiters
FRONTMATTER_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


@dataclass
class EmailTemplate:
    """A parsed email template with metadata and body."""
    slug: str
    name: str
    description: str
    subject: str
    body: str
    source_path: str

    def variables(self) -> list[str]:
        """Return all variable names used in both subject and body."""
        all_text = self.subject + "\n" + self.body
        return sorted(set(VARIABLE_PATTERN.findall(all_text)))

    def render(self, variables: dict[str, str]) -> tuple[str, str]:
        """Render the template with the given variables.

        Returns (subject, body) tuple.

        Raises ValueError if required variables are missing.
        """
        missing = [v for v in self.variables() if v not in variables]
        if missing:
            raise ValueError(f"Missing template variables: {', '.join(missing)}")

        def replace(match: re.Match) -> str:
            return variables.get(match.group(1), match.group(0))

        subject = VARIABLE_PATTERN.sub(replace, self.subject)
        body = VARIABLE_PATTERN.sub(replace, self.body)
        return subject, body


def _parse_frontmatter(content: str) -> tuple[dict[str, str], str]:
    """Parse YAML-like frontmatter from template content.

    Returns (metadata_dict, body_text).
    """
    match = FRONTMATTER_PATTERN.match(content)
    if not match:
        return {}, content

    frontmatter_text = match.group(1)
    body = content[match.end():].strip()

    metadata = {}
    for line in frontmatter_text.strip().split("\n"):
        if ":" in line:
            key, value = line.split(":", 1)
            value = value.strip().strip('"').strip("'")
            metadata[key.strip()] = value

    return metadata, body


def load_template(slug: str) -> Optional[EmailTemplate]:
    """Load a single template by slug (filename without extension)."""
    path = os.path.join(TEMPLATES_DIR, f"{slug}.md")
    if not os.path.exists(path):
        return None

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    metadata, body = _parse_frontmatter(content)

    return EmailTemplate(
        slug=slug,
        name=metadata.get("name", slug),
        description=metadata.get("description", ""),
        subject=metadata.get("subject", ""),
        body=body,
        source_path=path,
    )


def load_all_templates() -> list[EmailTemplate]:
    """Load all templates from the templates directory."""
    templates = []
    if not os.path.isdir(TEMPLATES_DIR):
        return templates

    for filename in sorted(os.listdir(TEMPLATES_DIR)):
        if filename.endswith(".md"):
            slug = filename[:-3]
            template = load_template(slug)
            if template:
                templates.append(template)

    return templates


def build_variables_from_result(result, product_name: str = "",
                                sender_name: str = "", sender_title: str = "") -> dict[str, str]:
    """Build a template variables dict from an OutreachResult.

    Args:
        result: An OutreachResult instance.
        product_name: The product being pitched (configured per-campaign).
        sender_name: The sender's name (configured per-campaign).
        sender_title: The sender's job title (configured per-campaign).

    Returns:
        Dict of variable_name -> value for template rendering.
    """
    author_name = result.author_name or ""
    author_first_name = author_name.split()[0] if author_name else "there"

    # Derive article title from URL path as a fallback
    article_title = ""
    if result.url:
        path = result.url.rstrip("/").split("/")[-1]
        article_title = path.replace("-", " ").replace("_", " ").title()

    return {
        "author_name": author_name or "Editor",
        "author_first_name": author_first_name,
        "company_name": result.company_name or result.domain,
        "domain": result.domain,
        "article_url": result.url,
        "article_title": article_title,
        "product_name": product_name,
        "sender_name": sender_name,
        "sender_title": sender_title,
    }
