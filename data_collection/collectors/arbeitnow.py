"""
Async Arbeitnow API collector.
Free, no auth, JSON API at https://www.arbeitnow.com/api/job-board-api
"""

import re
from typing import Sequence
from datetime import datetime

import httpx

from data_collection.collectors.base import AsyncBaseCollector
from data_collection.models import JobPosting, JobSource


class AsyncArbeitnowCollector(AsyncBaseCollector):
    """Collect jobs from Arbeitnow API."""

    source_name = JobSource.ARBEITNOW.value

    API_URL = "https://www.arbeitnow.com/api/job-board-api"

    def __init__(self, timeout: float = 20.0):
        self.timeout = timeout

    async def collect(self) -> Sequence[JobPosting]:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; JobAggregator/1.0)"}
        async with httpx.AsyncClient(headers=headers, timeout=self.timeout) as client:
            resp = await client.get(self.API_URL)
            resp.raise_for_status()
            data = resp.json()

        items = data.get("data", []) if isinstance(data, dict) else data
        jobs: list[JobPosting] = []

        for item in items:
            title = (item.get("title") or "").strip()
            if not title:
                continue

            company = (item.get("company_name") or "").strip()
            slug = item.get("slug", "")
            if not slug:
                continue

            location = (item.get("location") or "").strip()
            url = item.get("url") or ""

            desc = (item.get("description") or "").strip()
            desc = re.sub(r'<[^>]+>', ' ', desc)
            desc = re.sub(r'\s+', ' ', desc)[:2000]

            posted_at = None
            created = item.get("created_at")
            if created:
                try:
                    posted_at = datetime.fromtimestamp(created)
                except Exception:
                    pass

            jobs.append(
                JobPosting(
                    source=JobSource.ARBEITNOW,
                    source_id=f"arbeitnow-{slug}",
                    title=title,
                    company=company,
                    location=location,
                    url=url,
                    description=desc,
                    posted_at=posted_at,
                )
            )

        self.logger.info("[Arbeitnow] Collected %d jobs", len(jobs))
        return jobs
