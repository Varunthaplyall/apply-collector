"""
Async Remotive collector.
"""

from typing import Sequence

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from data_collection.collectors.base import AsyncBaseCollector
from data_collection.models import JobPosting, JobSource


class AsyncRemotiveCollector(AsyncBaseCollector):
    """Async version of RemotiveCollector."""

    source_name = JobSource.REMOTIVE.value

    API_URL = "https://remotive.com/api/remote-jobs"

    def __init__(self, timeout: float = 20.0):
        self.timeout = timeout

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    async def collect(self) -> Sequence[JobPosting]:
        """Fetch jobs from Remotive API."""
        jobs: list[JobPosting] = []

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(self.API_URL)
            resp.raise_for_status()
            data = resp.json()

            for item in data.get("jobs", []):
                job_id = item.get("id", "")
                if not job_id:
                    continue

                salary = ""
                if item.get("salary"):
                    salary = item["salary"]

                from datetime import datetime
                posted_at = None
                if item.get("publication_date"):
                    try:
                        posted_at = datetime.fromisoformat(item["publication_date"].replace("Z", "+00:00"))
                    except Exception:
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
                        salary_range=salary or None,
                        posted_at=posted_at,
                    )
                )

        return jobs
