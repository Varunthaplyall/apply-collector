"""
Async RemoteOK API collector.
Free, no auth, JSON API at https://remoteok.com/api
"""

import re
from typing import Sequence
from datetime import datetime

import httpx

from data_collection.collectors.base import AsyncBaseCollector
from data_collection.models import JobPosting, JobSource


class AsyncRemoteOKCollector(AsyncBaseCollector):
    """Collect jobs from RemoteOK API."""

    source_name = JobSource.REMOTEOK.value

    API_URL = "https://remoteok.com/api"

    def __init__(self, timeout: float = 20.0):
        self.timeout = timeout

    async def collect(self) -> Sequence[JobPosting]:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; JobAggregator/1.0)"}
        async with httpx.AsyncClient(headers=headers, timeout=self.timeout) as client:
            resp = await client.get(self.API_URL)
            resp.raise_for_status()
            data = resp.json()

        jobs: list[JobPosting] = []
        # First item is legal/metadata, skip it
        items = data[1:] if isinstance(data, list) and len(data) > 1 else data

        for item in items:
            if not isinstance(item, dict):
                continue

            title = (item.get("position") or "").strip()
            if not title:
                continue

            company = (item.get("company") or "").strip()
            source_id = str(item.get("id") or item.get("slug", ""))
            if not source_id:
                continue

            location = (item.get("location") or "").strip()
            url = item.get("apply_url") or item.get("url") or ""

            desc = (item.get("description") or "").strip()
            desc = re.sub(r'<[^>]+>', ' ', desc)
            desc = re.sub(r'\s+', ' ', desc)[:2000]

            posted_at = None
            date_str = item.get("date")
            if date_str:
                try:
                    posted_at = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                except Exception:
                    pass

            salary = ""
            smin = item.get("salary_min", 0)
            smax = item.get("salary_max", 0)
            if smin or smax:
                salary = f"{smin}-{smax}" if smax else str(smin)

            jobs.append(
                JobPosting(
                    source=JobSource.REMOTEOK,
                    source_id=f"remoteok-{source_id}",
                    title=title,
                    company=company,
                    location=location,
                    url=url,
                    description=desc,
                    salary_range=salary or None,
                    posted_at=posted_at,
                )
            )

        self.logger.info("[RemoteOK] Collected %d jobs", len(jobs))
        return jobs
