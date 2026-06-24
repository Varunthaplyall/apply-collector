"""
Adzuna API collector — free tier (250 req/day).

Register at https://developer.adzuna.com to get APP_ID and APP_KEY.
Covers India, UK, US, AU, and more.
"""

from typing import Sequence

import httpx

from data_collection.collectors.base import BaseCollector
from data_collection.models import JobPosting, JobSource


class AdzunaCollector(BaseCollector):
    """Collect jobs from Adzuna API."""

    source_name = JobSource.ADZUNA.value

    API_BASE = "https://api.adzuna.com/v1/api/jobs"

    # Countries Adzuna covers
    COUNTRIES = {
        "in": "India",
        "gb": "UK",
        "us": "US",
        "au": "Australia",
        "ca": "Canada",
        "de": "Germany",
        "fr": "France",
        "nl": "Netherlands",
        "sg": "Singapore",
        "nz": "New Zealand",
    }

    WHAT = [
        "python developer",
        "software engineer",
        "backend engineer",
        "full stack developer",
        "data engineer",
        "devops engineer",
        "site reliability engineer",
    ]

    def __init__(
        self,
        app_id: str,
        app_key: str,
        countries: list[str] | None = None,
        what_terms: list[str] | None = None,
        max_per_term: int = 30,
        timeout: float = 15.0,
    ):
        self.app_id = app_id
        self.app_key = app_key
        self.countries = countries or list(self.COUNTRIES.keys())
        self.what_terms = what_terms or self.WHAT
        self.max_per_term = max_per_term
        self.timeout = timeout

    def _search(self, country: str, what: str) -> list[JobPosting]:
        """Search Adzuna for a term in a country."""
        url = f"{self.API_BASE}/{country}/search/1"
        params = {
            "app_id": self.app_id,
            "app_key": self.app_key,
            "what": what,
            "results_per_page": self.max_per_term,
            "content_type": "application/json",
        }

        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(url, params=params)
            if resp.status_code == 403:
                self.logger.warning("Adzuna auth failed for %s (bad keys)", country)
                return []
            resp.raise_for_status()
            data = resp.json()

        jobs: list[JobPosting] = []
        for item in data.get("results", []):
            job_id = item.get("id", "")
            if not job_id:
                continue

            description = item.get("description", "") or ""
            # Adzuna returns HTML in description
            import re
            description = re.sub(r"<[^>]+>", " ", description)
            description = re.sub(r"\s+", " ", description).strip()

            salary_min = item.get("salary_min")
            salary_max = item.get("salary_max")
            salary_range = None
            if salary_min and salary_max:
                salary_range = f"{salary_min:.0f}-{salary_max:.0f} {item.get('salary_currency', '')}"

            company_name = ""
            if item.get("company"):
                company_name = item["company"].get("display_name", "")

            location_str = item.get("location", {}).get("display_name", "")
            if not location_str and item.get("address"):
                parts = [item["address"].get(p, "") for p in ("city", "state", "country")]
                location_str = ", ".join(p for p in parts if p)

            jobs.append(
                JobPosting(
                    source=JobSource.ADZUNA,
                    source_id=f"adz-{job_id}",
                    title=item.get("title", ""),
                    company=company_name,
                    location=location_str,
                    url=item.get("redirect_url", ""),
                    description=description,
                    salary_range=salary_range,
                )
            )

        return jobs

    def collect(self) -> Sequence[JobPosting]:
        all_jobs: list[JobPosting] = []
        for country in self.countries:
            for what in self.what_terms:
                try:
                    jobs = self._search(country, what)
                    all_jobs.extend(jobs)
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 403:
                        self.logger.warning(
                            "Adzuna 403 for %s/%s — check API keys", country, what
                        )
                        return all_jobs
                    self.logger.warning(
                        "Adzuna error for %s/%s: %d",
                        country, what, e.response.status_code,
                    )
                except Exception:
                    self.logger.exception(
                        "Adzuna failed: country=%s what=%s", country, what
                    )
        return all_jobs
