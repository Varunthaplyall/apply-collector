"""
Normalization and deduplication layer for the job pipeline.

Applies:
  1. Deterministic dedup by dedup_key (title + company + location)
  2. Reject filter for known scam patterns / pointless titles
  3. Basic statistics
"""

import logging
import re
from typing import Sequence

from data_collection.database import get_connection
from data_collection.models import JobPosting

logger = logging.getLogger(__name__)

# --- Reject patterns ---
# Titles that are clearly not real software engineering jobs
REJECT_TITLE_PATTERNS: list[re.Pattern] = [
    re.compile(r"(?i)driver|delivery|cashier|bartender|waiter|waitress|nanny"),
    re.compile(r"(?i)secret shopper|mystery shopper"),
    re.compile(r"(?i)data entry|admin assistant|administrative assistant"),
    re.compile(r"(?i)warehouse|packer|picker|packaging"),
    re.compile(r"(?i)customer service rep|call center"),
    re.compile(r"(?i)insurance agent|sales representative|real estate"),
    re.compile(r"(?i)cleaner|housekeeping|janitor|maintenance"),
    re.compile(r"(?i)security guard|security officer"),
    re.compile(r"(?i)caregiver|cna|nursing assistant|home health aide"),
    re.compile(r"(?i)receptionist|front desk"),
    re.compile(r"(?i)make money|work from home.*easy|earn.*daily"),
    re.compile(r"(?i)truck driver|dispatcher|courier"),
    re.compile(r"(?i)phlebotomist|medical assistant|dental assistant"),
    re.compile(r"(?i)electrician|plumber|hvac|mechanic"),
    re.compile(r"(?i)hiring.*immediately|urgent.*hiring"),
    re.compile(r"(?i)no experience needed.*work from home"),
    re.compile(r"(?i)commission.?only|100%.*commission"),
]

# Companies that are known recruitment agencies (not direct hire)
REJECT_COMPANY_PATTERNS: list[re.Pattern] = [
    re.compile(r"(?i)robert half|tek systems|aquent|kforce|randstad"),
    re.compile(r"(?i)adecco|manpower|kelly services|spherion"),
    re.compile(r"(?i)staffing|recruiting|recruitment|employment"),
    re.compile(r"(?i)hcl technologies|wipro|infosys|tcs|tech mahindra"),
    re.compile(r"(?i)cognizant|accenture|capgemini|ibm"),
]


def normalize_title(title: str) -> str:
    """Normalize title for fuzzy matching."""
    import re
    # Remove common prefixes/suffixes
    title = title.lower().strip()
    title = re.sub(r'\s*\([^)]*\)', '', title)  # Remove parenthetical (e.g., "(Remote)")
    # Remove "role - SenioritySuffix" patterns (e.g., "Lead - Senior" → "Lead")
    # Only remove the hyphen and the seniority word, preserving the rest
    title = re.sub(r'\s*-\s*(senior|sr\.?|junior|jr\.?|intern)\b', '', title, flags=re.IGNORECASE)
    # Remove common seniority prefixes/qualifiers (keep "lead", "staff", "principal" as they can be part of titles)
    title = re.sub(r'\b(senior|sr\.?|junior|jr\.?|intern)\b', '', title, flags=re.IGNORECASE)
    # Clean up whitespace, orphaned hyphens, and dots
    title = re.sub(r'\s*-\s*', ' ', title)     # Collapse remaining hyphens
    title = re.sub(r'[.\s]+', ' ', title)       # Remove dots, collapse whitespace
    title = title.strip()
    return title


def normalize_location(location: str) -> str:
    """Normalize location for fuzzy matching."""
    if not location:
        return ""
    location = location.lower().strip()
    # Remove common suffixes
    location = re.sub(r'\s*,\s*(india|in|us|usa|united states|uk|united kingdom)$', '', location)
    location = re.sub(r'\s+', ' ', location).strip()
    return location


def get_stats(conn=None) -> dict:
    """Get statistics about the current database."""
    close = conn is None
    conn = conn or get_connection()
    stats = {}

    stats["total"] = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]

    stats["by_source"] = {
        row["source"]: row["count"]
        for row in conn.execute(
            "SELECT source, COUNT(*) as count FROM jobs GROUP BY source ORDER BY count DESC"
        ).fetchall()
    }

    stats["by_company_top"] = [
        row["company"]
        for row in conn.execute(
            "SELECT company, COUNT(*) as c FROM jobs GROUP BY company ORDER BY c DESC LIMIT 20"
        ).fetchall()
    ]

    stats["title_examples"] = [
        row["title"]
        for row in conn.execute(
            "SELECT title FROM jobs ORDER BY scraped_at DESC LIMIT 10"
        ).fetchall()
    ]

    stats["newest_date"] = conn.execute(
        "SELECT MAX(scraped_at) FROM jobs"
    ).fetchone()[0]

    if close:
        conn.close()

    return stats


def print_stats(conn=None) -> None:
    """Print formatted statistics."""
    close = conn is None
    conn = conn or get_connection()

    total = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    print(f"\n{'='*50}")
    print(f"  Job Database Statistics")
    print(f"  Total jobs: {total}")
    print(f"{'='*50}")

    print("\nBy source:")
    for row in conn.execute(
        "SELECT source, COUNT(*) as c FROM jobs GROUP BY source ORDER BY c DESC"
    ):
        print(f"  {row['source']:>15}: {row['c']}")

    print("\nTop companies:")
    for i, row in enumerate(
        conn.execute(
            "SELECT company, COUNT(*) as c FROM jobs GROUP BY company ORDER BY c DESC LIMIT 20"
        ).fetchall(),
        start=1,
    ):
        pct = row["c"] / total * 100
        print(f"  {i:>2}. {row['company']:<20} {row['c']:>5} ({pct:4.1f}%)")

    print(f"\nNewest scrape: {conn.execute('SELECT MAX(scraped_at) FROM jobs').fetchone()[0]}")

    if close:
        conn.close()


if __name__ == "__main__":
    print_stats()
