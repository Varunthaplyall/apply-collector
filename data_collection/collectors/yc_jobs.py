"""
YC Jobs / HN "Who is hiring?" collector.

Fetches top-level comments from recent "Ask HN: Who is hiring?" threads
posted by the `whoishiring` account, and parses them as individual job
postings using the community's pipe-separated format:

    Company | Role | Location | [Other info ...]

Source: Hacker News Algolia API (no auth required).

Usage:
    # Fetch last 3 months of threads (default)
    AsyncYCCollector()
    # Fetch last 6 months
    AsyncYCCollector(months_back=6)
"""

import asyncio
import logging
import re
from datetime import datetime, timezone
from html import unescape
from typing import Optional, Sequence

import httpx

from data_collection.collectors.base import AsyncBaseCollector
from data_collection.models import JobPosting, JobSource

logger = logging.getLogger(__name__)

# Engineering/tech role keywords for filtering
_ENG_KEYWORDS = {
    "engineer", "developer", "swe", "sde", "backend", "frontend",
    "fullstack", "full-stack", "full stack", "devops", "sre",
    "infrastructure", "platform", "data engineer", "ml engineer",
    "machine learning", "software", "systems engineer", "staff engineer",
    "principal engineer", "architect", "cto", "vp engineering",
    "engineering manager", "tech lead", "lead engineer",
    "founding engineer", "security engineer", "mobile",
    "android", "ios developer", "python", "rust", "golang", "java",
    "typescript", "react", "node", "kubernetes",
}

# Non-tech keywords to exclude (case-insensitive substrings)
_EXCLUDE_KEYWORDS = {
    "account exec", "sales", "marketing", "recruiter",
    "customer support", "account manager", "business development",
    "product manager", "designer", "ux ", "ui designer",
    "copywriter", "content writer", "operations",
}


def _strip_html(text: str) -> str:
    """Remove HTML tags and unescape entities."""
    text = unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(text.split()).strip()


def _is_engineering_role(text: str) -> bool:
    """Heuristic: does this comment look like an engineering job post?"""
    lower = text.lower()
    # Must have at least one engineering keyword
    has_eng = any(kw in lower for kw in _ENG_KEYWORDS)
    # Exclude pure non-tech roles
    is_excluded = any(kw in lower for kw in _EXCLUDE_KEYWORDS)
    return has_eng and not is_excluded


def _parse_comment(text: str) -> dict:
    """Parse a HN hiring comment into structured fields.

    Standard format: Company | Role | Location | [Details...]
    Returns dict with keys: company, title, location, description.
    """
    parts = [p.strip() for p in text.split("|")]

    company = ""
    title = ""
    location = ""
    description = text  # full text as description

    if len(parts) >= 3:
        company = parts[0]
        title = parts[1]
        location = parts[2]
    elif len(parts) == 2:
        company = parts[0]
        # Try to figure out if second part is role or location
        second = parts[1]
        if _is_engineering_role(second):
            title = second
        else:
            # Might be "Company | Remote" style
            location = second
            title = company  # company name is all we have
    elif len(parts) == 1:
        # No pipes — try to extract company from first line
        lines = text.split("\n")
        company = lines[0][:80] if lines else ""

    # Clean up trailing whitespace / newlines
    company = company.rstrip("–—- ").strip()
    title = title.rstrip("–—- ").strip()

    return {
        "company": company,
        "title": title,
        "location": location,
        "description": description[:2000],
    }


class AsyncYCCollector(AsyncBaseCollector):
    """Collect engineering job postings from HN "Who is hiring?" threads."""

    source_name = "yc_jobs"

    ALGOLIA_API = "https://hn.algolia.com/api/v1"

    def __init__(
        self,
        months_back: int = 3,
        timeout: float = 30.0,
    ):
        self.months_back = months_back
        self.timeout = timeout

    async def _find_hiring_threads(
        self, client: httpx.AsyncClient
    ) -> list[dict]:
        """Find recent 'Who is hiring?' threads via Algolia search."""
        # Search for threads by whoishiring
        resp = await client.get(
            f"{self.ALGOLIA_API}/search",
            params={
                "tags": "story,author_whoishiring",
                "hitsPerPage": self.months_back + 2,  # buffer
            },
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        hits = data.get("hits", [])

        # Sort by objectID descending (newest first) and take N months
        hits.sort(key=lambda h: int(h.get("objectID", 0)), reverse=True)
        # Filter to "Who is hiring?" threads only
        hiring = [
            h for h in hits
            if "who is hiring" in h.get("title", "").lower()
        ]
        return hiring[: self.months_back]

    async def _fetch_thread_comments(
        self, client: httpx.AsyncClient, story_id: str
    ) -> list[dict]:
        """Fetch all top-level comments from a HN story."""
        resp = await client.get(
            f"{self.ALGOLIA_API}/items/{story_id}",
            timeout=self.timeout,
        )
        resp.raise_for_status()
        item = resp.json()
        return item.get("children", [])

    async def collect(self) -> Sequence[JobPosting]:
        """Collect engineering job posts from recent HN hiring threads."""
        jobs: list[JobPosting] = []
        seen_keys: set[str] = set()

        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; JobAggregator/1.0)",
            "Accept": "application/json",
        }

        async with httpx.AsyncClient(headers=headers) as client:
            # 1. Find recent hiring threads
            threads = await self._find_hiring_threads(client)
            self.logger.info("[YC] Found %d recent hiring threads", len(threads))

            for thread in threads:
                story_id = thread["objectID"]
                title = thread.get("title", "")
                thread_date = thread.get("created_at", "")
                self.logger.info("[YC] Fetching comments from: %s", title)

                comments = await self._fetch_thread_comments(client, story_id)
                thread_jobs = 0

                for comment in comments:
                    raw_text = comment.get("text", "")
                    if not raw_text:
                        continue

                    text = _strip_html(raw_text)

                    # Filter to engineering roles
                    if not _is_engineering_role(text):
                        continue

                    parsed = _parse_comment(text)
                    if not parsed["company"]:
                        continue

                    # Dedup by company+title
                    dedup_key = f"{parsed['company'].lower()}|{parsed['title'].lower()}"
                    if dedup_key in seen_keys:
                        continue
                    seen_keys.add(dedup_key)

                    # Parse thread date
                    posted_at = None
                    if thread_date:
                        try:
                            posted_at = datetime.fromisoformat(
                                thread_date.replace("Z", "+00:00")
                            )
                        except Exception:
                            pass

                    comment_id = comment.get("id", "")
                    source_id = f"hn-{story_id}-{comment_id}"

                    # Build URL back to the HN comment
                    url = f"https://news.ycombinator.com/item?id={comment_id}"

                    jobs.append(
                        JobPosting(
                            source=JobSource.YC_JOBS,
                            source_id=source_id,
                            title=parsed["title"][:200] or "Engineering Role",
                            company=parsed["company"][:200],
                            location=parsed["location"][:200],
                            url=url,
                            description=parsed["description"],
                            posted_at=posted_at,
                        )
                    )
                    thread_jobs += 1

                self.logger.info(
                    "[YC] %s: %d engineering jobs from %d comments",
                    title,
                    thread_jobs,
                    len(comments),
                )

                # Small politeness delay between threads
                await asyncio.sleep(0.5)

        self.logger.info("[YC] Total: %d engineering job postings", len(jobs))
        return jobs
