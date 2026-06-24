"""
Remotive API collector — free, no auth, remote-focused job listings.

API: https://remotive.com/api/remote-jobs
Returns paginated JSON — no API key required.
"""

from typing import Sequence

import httpx

from data_collection.collectors.base import BaseCollector
from data_collection.models import JobPosting, JobSource


class RemotiveCollector(BaseCollector):
    """Collect remote jobs from the free Remotive API."""

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
        timeout: float = 30.0,
    ):
        self.categories = categories or self.CATEGORIES
        self.max_pages = max_pages
        self.timeout = timeout

    def _fetch_page(self, category: str, page: int) -> dict:
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(self.API_URL, params={"category": category, "page": page})
            resp.raise_for_status()
            return resp.json()

    def _parse_jobs(self, raw: dict) -> list[JobPosting]:
        jobs: list[JobPosting] = []
        for item in raw.get("jobs", []):
            job_id = item.get("id", "")
            if not job_id:
                continue
            jobs.append(
                JobPosting(
                    source=JobSource.REMOTIVE,
                    source_id=str(job_id),
                    title=item.get("title", ""),
                    company=item.get("company_name", ""),
                    location=item.get("candidate_required_location", ""),
                    url=item.get("url", ""),
                    description=item.get("description", ""),
                    salary_range=item.get("salary", ""),
                    posted_at=None,
                )
            )
        return jobs

    def collect(self) -> Sequence[JobPosting]:
        all_jobs: list[JobPosting] = []
        for category in self.categories:
            for page in range(1, self.max_pages + 1):
                try:
                    data = self._fetch_page(category, page)
                    jobs = self._parse_jobs(data)
                    all_jobs.extend(jobs)
                    if not data.get("jobs") or page >= data.get(
                        "total_pages", self.max_pages
                    ):
                        break
                except Exception:
                    self.logger.exception(
                        "Failed fetching Remotive: cat=%s page=%d", category, page
                    )
                    break
        return all_jobs
