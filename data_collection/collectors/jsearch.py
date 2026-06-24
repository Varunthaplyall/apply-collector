"""
JSearch (RapidAPI) collector — aggregates Indeed, LinkedIn, Glassdoor, etc.

Requires a RapidAPI key. Free tier available.
Register: https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch
"""

from typing import Sequence

import httpx

from data_collection.collectors.base import BaseCollector
from data_collection.models import JobPosting, JobSource


class JSearchCollector(BaseCollector):
    """Collect jobs via JSearch RapidAPI (aggregates Indeed/LinkedIn/Glassdoor)."""

    source_name = "jsearch"

    API_URL = "https://jsearch.p.rapidapi.com/search"

    QUERIES = [
        "python developer",
        "software engineer",
        "backend engineer",
        "full stack developer",
        "data engineer",
        "devops engineer",
        "site reliability engineer",
        "frontend engineer",
        "machine learning engineer",
        "product manager",
    ]

    LOCATIONS = [
        "remote",
        "bangalore, india",
        "mumbai, india",
        "delhi, india",
        "pune, india",
        "hyderabad, india",
        "chennai, india",
        "san francisco, us",
        "new york, us",
        "london, uk",
        "berlin, germany",
        "singapore",
        "dubai, uae",
    ]

    def __init__(
        self,
        api_key: str,
        queries: list[str] | None = None,
        locations: list[str] | None = None,
        max_per_query: int = 20,
        timeout: float = 15.0,
    ):
        self.api_key = api_key
        self.queries = queries or self.QUERIES
        self.locations = locations or self.LOCATIONS
        self.max_per_query = max_per_query
        self.timeout = timeout

        self.headers = {
            "x-rapidapi-key": self.api_key,
            "x-rapidapi-host": "jsearch.p.rapidapi.com",
        }

    def _search(self, query: str, location: str) -> list[JobPosting]:
        params = {
            "query": f"{query} in {location}",
            "page": "1",
            "num_pages": "1",
            "date_posted": "week",
            "remote_jobs_only": "true" if "remote" in location.lower() else "false",
        }

        with httpx.Client(timeout=self.timeout, headers=self.headers) as client:
            resp = client.get(self.API_URL, params=params)
            if resp.status_code == 429:
                self.logger.warning("JSearch rate limited")
                return []
            resp.raise_for_status()
            data = resp.json()

        jobs: list[JobPosting] = []
        for item in data.get("data", []):
            job_id = item.get("job_id", "")
            if not job_id:
                continue

            desc = (item.get("job_description", "") or "")
            desc = desc[:5000]  # cap description length

            salary_range = None
            if item.get("job_min_salary") or item.get("job_max_salary"):
                mn = item.get("job_min_salary") or ""
                mx = item.get("job_max_salary") or ""
                currency = item.get("job_salary_currency", "")
                period = item.get("job_salary_period", "")
                salary_range = f"{mn}-{mx} {currency}/{period}".strip()

            jobs.append(
                JobPosting(
                    source=JobSource.LINKEDIN,  # JSearch aggregates LinkedIn/Indeed
                    source_id=f"js-{job_id}",
                    title=item.get("job_title", ""),
                    company=item.get("employer_name", ""),
                    location=item.get("job_city", "")
                    or item.get("job_country", location),
                    url=item.get("job_apply_link", ""),
                    description=desc,
                    salary_range=salary_range,
                )
            )

        return jobs[: self.max_per_query]

    def collect(self) -> Sequence[JobPosting]:
        all_jobs: list[JobPosting] = []
        for query in self.queries:
            for location in self.locations:
                try:
                    jobs = self._search(query, location)
                    all_jobs.extend(jobs)
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 429:
                        self.logger.warning("JSearch rate limit hit, stopping")
                        return all_jobs
                    self.logger.warning(
                        "JSearch error for '%s in %s': %d",
                        query, location, e.response.status_code,
                    )
                except Exception:
                    self.logger.exception(
                        "JSearch failed: q=%s l=%s", query, location
                    )
        return all_jobs
