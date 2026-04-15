"""Client configuration loader.

Each client has a YAML file in clients/ with a competitor blacklist.
The pipeline refuses to run without a valid --client flag so that
competitor domains are always checked before any enrichment.
"""

import os
import sys
from pathlib import Path

import yaml


CLIENTS_DIR = Path(__file__).parent / "clients"


def list_clients() -> list[str]:
    """Return available client slugs (filenames without .yaml)."""
    if not CLIENTS_DIR.is_dir():
        return []
    return sorted(p.stem for p in CLIENTS_DIR.glob("*.yaml"))


def load_client(slug: str) -> dict:
    """Load a client config by slug. Exits with error if not found or empty competitors."""
    path = CLIENTS_DIR / f"{slug}.yaml"
    if not path.exists():
        available = ", ".join(list_clients()) or "(none)"
        print(f"Error: Unknown client '{slug}'. Available clients: {available}")
        sys.exit(1)

    with open(path) as f:
        config = yaml.safe_load(f)

    if not config:
        print(f"Error: Client config '{path}' is empty or invalid.")
        sys.exit(1)

    competitors = config.get("competitors") or []
    if not competitors:
        print(f"Error: No competitors defined for client '{slug}'.")
        print(f"       Add competitor domains to {path} before running the pipeline.")
        print(f"       This ensures you never accidentally enrich competitor URLs.")
        sys.exit(1)

    return {
        "name": config.get("name", slug),
        "slug": slug,
        "competitors": [d.lower().replace("www.", "") for d in competitors],
    }
