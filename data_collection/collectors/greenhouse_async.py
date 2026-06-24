"""
Async Greenhouse Direct ATS API collector.
Loads company slugs from target_companies.json when available.
"""

from typing import Sequence
import asyncio
import json
import logging

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from data_collection.collectors.base import AsyncBaseCollector
from data_collection.collectors.greenhouse import GreenhouseCollector
from data_collection.config import CONFIG_PATH
from data_collection.models import JobPosting, JobSource

logger = logging.getLogger(__name__)


def _load_greenhouse_slugs() -> list[str]:
    """Load Greenhouse slugs from target_companies.json, falling back to defaults."""
    try:
        with open(CONFIG_PATH) as f:
            config = json.load(f)
        config_slugs = [
            c["slug"] for c in config["companies"]
            if c.get("ats") == "greenhouse" and c.get("slug")
        ]
        if config_slugs:
            # Merge with defaults, config takes precedence (dedup preserving order)
            defaults = GreenhouseCollector.DEFAULT_COMPANIES
            all_slugs = list(dict.fromkeys(config_slugs + defaults))
            logger.info("Loaded %d Greenhouse slugs (%d from config, %d defaults merged)",
                        len(all_slugs), len(config_slugs), len(defaults))
            return all_slugs
    except Exception:
        pass
    return GreenhouseCollector.DEFAULT_COMPANIES


class AsyncGreenhouseCollector(AsyncBaseCollector):
    """Async version of GreenhouseCollector for concurrent execution."""

    source_name = JobSource.GREENHOUSE.value

    def __init__(
        self,
        companies: list[str] | None = None,
        content: str = "true",
        timeout: float = 30.0,
        concurrency: int = 10,
    ):
        self.companies = companies or _load_greenhouse_slugs()
        self.content = content
        self.timeout = timeout
        self.concurrency = concurrency

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    async def _fetch_company_jobs(self, client: httpx.AsyncClient, slug: str) -> list[dict]:
        """Fetch all jobs for a single company."""
        url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
        all_jobs: list[dict] = []
        page = 1

        while True:
            resp = await client.get(url, params={"content": self.content, "page": page})
            if resp.status_code == 404:
                break
            resp.raise_for_status()
            data = resp.json()
            all_jobs.extend(data.get("jobs", []))
            if not data.get("meta", {}).get("next"):
                break
            page += 1

        return all_jobs

    def _parse_jobs(self, slug: str, raw_jobs: list[dict]) -> list[JobPosting]:
        """Parse raw jobs into JobPosting objects."""
        jobs: list[JobPosting] = []
        for item in raw_jobs:
            job_id = item.get("id", "")
            if not job_id:
                continue

            content = item.get("content", {})
            description = ""
            if isinstance(content, dict):
                desc_parts: list[str] = []
                for section in content.get("sections", []):
                    if isinstance(section, dict):
                        text = (section.get("plain_text_content", "") or "").strip()
                        if text:
                            desc_parts.append(text)
                description = "\n\n".join(desc_parts)
            elif isinstance(content, str):
                description = content

            offices = item.get("offices", [{}])
            location = ", ".join(
                o.get("name", o.get("location", "")) for o in offices if o
            )

            jobs.append(
                JobPosting(
                    source=JobSource.GREENHOUSE,
                    source_id=f"{slug}-{job_id}",
                    title=item.get("title", ""),
                    company=slug.title(),
                    location=location,
                    url=item.get("absolute_url", ""),
                    description=description,
                )
            )
        return jobs

    async def collect(self) -> Sequence[JobPosting]:
        """Fetch jobs from all companies concurrently."""
        semaphore = asyncio.Semaphore(self.concurrency)
        all_jobs: list[JobPosting] = []

        async def _fetch_with_semaphore(client: httpx.AsyncClient, slug: str) -> tuple[str, list[dict]]:
            async with semaphore:
                raw = await self._fetch_company_jobs(client, slug)
                return slug, raw

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            tasks = [_fetch_with_semaphore(client, slug) for slug in self.companies]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                self.logger.warning("Greenhouse fetch failed: %s", result)
                continue
            slug, raw_jobs = result
            jobs = self._parse_jobs(slug, raw_jobs)
            all_jobs.extend(jobs)
            self.logger.info("[Greenhouse] %s: %d jobs", slug, len(jobs))

        return all_jobs
