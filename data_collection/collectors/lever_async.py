"""
Async Lever ATS collector.
Loads slugs from target_companies.json when available.
"""

from typing import Sequence
import asyncio
import json
import logging

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from data_collection.collectors.base import AsyncBaseCollector
from data_collection.config import CONFIG_PATH
from data_collection.models import JobPosting, JobSource

logger = logging.getLogger(__name__)


def _load_lever_slugs() -> list[str]:
    """Load Lever slugs from target_companies.json, falling back to defaults."""
    defaults = ["cred", "meesho", "freshworks"]
    try:
        with open(CONFIG_PATH) as f:
            config = json.load(f)
        config_slugs = [
            c["slug"] for c in config["companies"]
            if c.get("ats") == "lever" and c.get("slug")
        ]
        if config_slugs:
            all_slugs = list(dict.fromkeys(config_slugs + defaults))
            logger.info("Loaded %d Lever slugs (%d from config, %d defaults merged)",
                        len(all_slugs), len(config_slugs), len(defaults))
            return all_slugs
    except Exception:
        pass
    return defaults


class AsyncLeverCollector(AsyncBaseCollector):
    """Async version of LeverCollector."""

    source_name = JobSource.LEVER.value

    DEFAULT_SLUGS = ["cred", "meesho", "freshworks"]

    def __init__(self, slugs: list[str] | None = None, timeout: float = 15.0):
        self.slugs = slugs or _load_lever_slugs()
        self.timeout = timeout

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    async def _fetch_postings(self, client: httpx.AsyncClient, slug: str) -> list[dict]:
        """Fetch all postings for a company slug."""
        url = f"https://api.lever.co/v0/postings/{slug}"
        resp = await client.get(url, params={"mode": "json"}, timeout=self.timeout)
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else []

    async def collect(self) -> Sequence[JobPosting]:
        """Fetch jobs from all companies concurrently."""
        jobs: list[JobPosting] = []
        seen_ids: set[str] = set()

        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; JobAggregator/1.0)",
            "Accept": "application/json",
        }

        async with httpx.AsyncClient(headers=headers) as client:
            tasks = [self._fetch_postings(client, slug) for slug in self.slugs]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        for slug, result in zip(self.slugs, results):
            if isinstance(result, Exception):
                self.logger.warning("[Lever] %s failed: %s", slug, result)
                continue

            raw_jobs = result
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

            self.logger.info("[Lever] %s: %d jobs", slug, len(raw_jobs))

        return jobs
