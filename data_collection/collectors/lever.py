"""
Lever ATS collector — fetches job postings from companies using Lever.

API: GET https://api.lever.co/v0/postings/{slug}?mode=json
"""

import hashlib
import logging
from typing import Sequence

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from data_collection.collectors.base import BaseCollector
from data_collection.models import JobPosting, JobSource

logger = logging.getLogger(__name__)


class LeverCollector(BaseCollector):
    """Collect jobs from companies using Lever ATS."""

    source_name = JobSource.LEVER.value

    DEFAULT_SLUGS = ["cred", "meesho", "freshworks"]

    def __init__(self, slugs: list[str] | None = None, timeout: float = 15.0):
        self.slugs = slugs or self.DEFAULT_SLUGS
        self.timeout = timeout

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    def _fetch_postings(self, client: httpx.Client, slug: str) -> list[dict]:
        """Fetch all postings for a company slug."""
        url = f"https://api.lever.co/v0/postings/{slug}"
        resp = client.get(url, params={"mode": "json"}, timeout=self.timeout)
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else []

    def collect(self) -> Sequence[JobPosting]:
        jobs: list[JobPosting] = []
        seen_ids: set[str] = set()

        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; JobAggregator/1.0)",
            "Accept": "application/json",
        }

        with httpx.Client(headers=headers) as client:
            for slug in self.slugs:
                try:
                    raw_jobs = self._fetch_postings(client, slug)
                    for item in raw_jobs:
                        text = item.get("text", "")
                        title = text.strip() if isinstance(text, str) else ""
                        if not title:
                            continue

                        source_id = item.get("id", "")
                        if not source_id:
                            continue
                        if source_id in seen_ids:
                            continue
                        seen_ids.add(source_id)

                        # Use the slug as company name, NOT categories.team
                        # (team is the department, e.g. "Engineering", "Finance")
                        company = slug.title()
                        location = item.get("categories", {}).get("location", "")
                        url = item.get("hostedUrl", "")

                        # Parse created_at
                        created = item.get("createdAt")
                        posted_at = None
                        if created:
                            from datetime import datetime, timezone
                            try:
                                posted_at = datetime.fromtimestamp(created / 1000, tz=timezone.utc)
                            except Exception:
                                pass

                        description = ""
                        desc_parts = item.get("descriptionPlain", "")
                        if desc_parts:
                            description = desc_parts[:2000]

                        jobs.append(
                            JobPosting(
                                source=JobSource.LEVER,
                                source_id=f"lever-{source_id}",
                                title=title,
                                company=company,
                                location=location or "",
                                url=url,
                                description=description,
                                posted_at=posted_at,
                            )
                        )

                    logger.info("[Lever] %s: %d jobs", slug, len(raw_jobs))
                except Exception as e:
                    logger.warning("[Lever] %s failed: %s", slug, e)

        return jobs
