"""
Async Himalayas Jobs API collector.
Free, no auth, JSON API at https://himalayas.app/jobs/api
Remote-focused job board.
"""

import re
import hashlib
from typing import Sequence

import httpx

from data_collection.collectors.base import AsyncBaseCollector
from data_collection.models import JobPosting, JobSource


class AsyncHimalayasCollector(AsyncBaseCollector):
    """Collect jobs from Himalayas API."""

    source_name = JobSource.HIMALAYAS.value

    API_URL = "https://himalayas.app/jobs/api"

    def __init__(self, timeout: float = 20.0):
        self.timeout = timeout

    async def collect(self) -> Sequence[JobPosting]:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; JobAggregator/1.0)"}
        async with httpx.AsyncClient(headers=headers, timeout=self.timeout) as client:
            resp = await client.get(self.API_URL)
            resp.raise_for_status()
            data = resp.json()

        items = data.get("jobs", []) if isinstance(data, dict) else data
        jobs: list[JobPosting] = []

        for item in items:
            title = (item.get("title") or "").strip()
            if not title:
                continue

            company = (item.get("companyName") or "").strip()
            guid = item.get("guid") or ""
            url = item.get("applicationLink") or guid or ""

            # Build a stable source_id from the guid
            if guid:
                source_id = guid.split("/")[-1] if "/" in guid else hashlib.md5(guid.encode()).hexdigest()[:12]
            else:
                source_id = hashlib.md5((title + company).encode()).hexdigest()[:12]

            # Build location from restrictions
            locs = item.get("locationRestrictions") or []
            location = ", ".join(locs[:3]) if locs else "Remote"

            desc = (item.get("excerpt") or "").strip()[:2000]

            salary = ""
            smin = item.get("minSalary", 0)
            smax = item.get("maxSalary", 0)
            currency = item.get("currency", "USD")
            if smin or smax:
                salary = f"{currency} {smin:,}-{smax:,}" if smax else f"{currency} {smin:,}"

            jobs.append(
                JobPosting(
                    source=JobSource.HIMALAYAS,
                    source_id=f"himalayas-{source_id}",
                    title=title,
                    company=company,
                    location=location,
                    url=url,
                    description=desc,
                    salary_range=salary or None,
                )
            )

        self.logger.info("[Himalayas] Collected %d jobs", len(jobs))
        return jobs
