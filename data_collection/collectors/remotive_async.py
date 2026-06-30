"""
Async Remotive collector — free, no auth, remote-focused job listings.

API: https://remotive.com/api/remote-jobs
Returns paginated JSON — no API key required.
"""

import asyncio
from datetime import datetime
from typing import Sequence

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from data_collection.collectors.base import AsyncBaseCollector
from data_collection.models import JobPosting, JobSource


class AsyncRemotiveCollector(AsyncBaseCollector):
    """Collect remote jobs from the free Remotive API (async)."""

    source_name = JobSource.REMOTIVE.value

    API_URL = "https://remotive.com/api/remote-jobs"

    CATEGORIES = [
        "software-dev",
        "devops",
        "data",
        "product",
        "design",
        "customer-support",
    ]

    def __init__(
        self,
        categories: list[str] | None = None,
        max_pages: int = 3,
        timeout: float = 20.0,
    ):
        self.categories = categories or self.CATEGORIES
        self.max_pages = max_pages
        self.timeout = timeout

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    async def _fetch_page(self, client: httpx.AsyncClient, category: str, page: int) -> dict:
        resp = await client.get(self.API_URL, params={"category": category, "page": page})
        resp.raise_for_status()
        return resp.json()

    def _parse_jobs(self, raw: dict) -> list[JobPosting]:
        jobs: list[JobPosting] = []
        for item in raw.get("jobs", []):
            job_id = item.get("id", "")
            if not job_id:
                continue

            posted_at = None
            pub_date = item.get("publication_date")
            if pub_date:
                try:
                    posted_at = datetime.fromisoformat(pub_date.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    pass

            jobs.append(
                JobPosting(
                    source=JobSource.REMOTIVE,
                    source_id=f"remotive-{job_id}",
                    title=item.get("title", ""),
                    company=item.get("company_name", ""),
                    location=item.get("candidate_required_location", ""),
                    url=item.get("url", ""),
                    description=item.get("description", "")[:2000],
                    salary_range=item.get("salary") or None,
                    posted_at=posted_at,
                )
            )
        return jobs

    async def _collect_category(
        self, client: httpx.AsyncClient, category: str
    ) -> list[JobPosting]:
        """Fetch all pages for a single category, respecting max_pages and total_pages."""
        jobs: list[JobPosting] = []

        for page in range(1, self.max_pages + 1):
            try:
                data = await self._fetch_page(client, category, page)
                page_jobs = self._parse_jobs(data)
                jobs.extend(page_jobs)

                total_pages = data.get("total_pages", 0)
                if not data.get("jobs") or page >= total_pages:
                    break
            except Exception:
                self.logger.warning(
                    "Remotive category=%s page=%d failed", category, page
                )
                break

        return jobs

    async def collect(self) -> Sequence[JobPosting]:
        """Fetch jobs from all Remotive categories with pagination, concurrently per category."""
        all_jobs: list[JobPosting] = []

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            tasks = [
                self._collect_category(client, category)
                for category in self.categories
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for i, result in enumerate(results):
                category = self.categories[i]
                if isinstance(result, Exception):
                    self.logger.warning(
                        "Remotive category=%s failed: %s", category, result
                    )
                else:
                    cat_jobs: list[JobPosting] = result
                    all_jobs.extend(cat_jobs)
                    self.logger.info("Remotive category=%s: %d jobs", category, len(cat_jobs))

        self.logger.info(
            "Remotive total: %d jobs across %d categories",
            len(all_jobs),
            len(self.categories),
        )
        return all_jobs
