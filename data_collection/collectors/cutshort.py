"""
Cutshort.io collector — India-focused tech job board.

Async version with rate limiting, India filtering, and configurable limits.
Uses sitemap to discover job URLs, then scrapes JSON-LD for details.

Key changes from v1:
  - AsyncBaseCollector (concurrent HTTP with semaphore)
  - India-only filtering: checks JSON-LD addressRegion or location string
  - Rate limiting: configurable delay between requests
  - --cutshort-limit N flag in run_all_async.py
"""

import asyncio
import hashlib
import json
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from typing import Sequence

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from data_collection.collectors.base import AsyncBaseCollector
from data_collection.database import is_india_location
from data_collection.models import JobPosting, JobSource

logger = logging.getLogger(__name__)


class AsyncCutshortCollector(AsyncBaseCollector):
    """Async collector for Cutshort.io — India-focused tech job board."""

    source_name = JobSource.CUTSHORT.value

    SITEMAP_URL = "https://cutshort-data.s3.amazonaws.com/cloudfront/public/jobs-sitemap.xml"

    # India location indicators (substring match, lowercased)
    _INDIA_KEYWORDS = [
        "india", "bengaluru", "bangalore", "mumbai", "bombay",
        "delhi", "gurugram", "gurgaon", "noida", "hyderabad",
        "pune", "chennai", "kolkata", "calcutta", "ahmedabad",
        "jaipur", "kochi", "cochin", "coimbatore", "mysore",
        "trivandrum", "thiruvananthapuram", "indore", "nagpur",
        "chandigarh", "lucknow", "visakhapatnam", "patna",
        "vadodara", "surat", "rajkot", "warangal",
        "remote india", "remote - india",
    ]

    def __init__(
        self,
        max_jobs: int = 1000,
        max_concurrency: int = 10,
        delay_between_requests: float = 0.5,
        timeout: float = 15.0,
    ):
        self.max_jobs = max_jobs
        self.max_concurrency = max_concurrency
        self.delay = delay_between_requests
        self.timeout = timeout

    def _is_india_job(self, location: str, json_ld: dict | None = None) -> bool:
        """Check if a job is India-based using location string and JSON-LD."""
        # 1. Check JSON-LD addressRegion if available
        if json_ld:
            addr = json_ld.get("jobLocation", {})
            if isinstance(addr, dict):
                addr = addr.get("address", {})
            if isinstance(addr, dict):
                region = (addr.get("addressRegion") or "").upper()
                country = (addr.get("addressCountry") or "").upper()
                if region == "IN" or country == "IN" or country == "INDIA":
                    return True

        # 2. Fallback: substring match on location string
        loc_lower = location.lower()
        return any(kw in loc_lower for kw in self._INDIA_KEYWORDS)

    def _extract_json_ld(self, html: str) -> dict | None:
        """Extract JSON-LD structured data from HTML."""
        match = re.search(
            r'<script type="application/ld\+json">(.*?)</script>',
            html, re.DOTALL,
        )
        if match:
            try:
                return json.loads(match.group(1))
            except Exception:
                pass
        return None

    def _parse_job_from_html(self, html: str, url: str) -> dict | None:
        """Parse job details from HTML page using JSON-LD."""
        json_ld = self._extract_json_ld(html)
        if not json_ld:
            return None

        name = json_ld.get("name", "")
        desc = json_ld.get("description", "")

        title = ""
        company = ""
        location = ""

        # Pattern 1: "Company is hiring Title job in Location"
        match1 = re.search(
            r'(.+?)\s+is\s+hiring\s+(.+?)\s+job\s+in\s+(.+?)(?:\s*\||$)', name
        )
        if match1:
            company = match1.group(1).strip()
            title = match1.group(2).strip()
            location = match1.group(3).strip()
        else:
            # Pattern 2: "Title job in Location"
            match2 = re.search(r'(.+?)\s+job\s+in\s+(.+?)(?:\s*\||$)', name)
            if match2:
                title = match2.group(1).strip()
                location = match2.group(2).strip()
            else:
                title = name.split(" | ")[0].strip()

        # Try to extract company from description if not found
        if not company:
            company_match = re.search(r'at\s+(.+?)\s+in', desc)
            if company_match:
                company = company_match.group(1).strip()

        # Clean up title
        title = re.sub(r'\s*\(.*?\)\s*$', '', title).strip()

        return {
            "title": title,
            "company": company,
            "location": location,
            "url": url,
            "description": desc[:2000],
            "json_ld": json_ld,
        }

    async def _fetch_sitemap(self, client: httpx.AsyncClient) -> list[dict]:
        """Fetch and parse sitemap for ALL job URLs (not just recent)."""
        resp = await client.get(self.SITEMAP_URL, timeout=30.0)
        resp.raise_for_status()

        root = ET.fromstring(resp.text)
        ns = {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"}

        all_jobs = []
        for url_elem in root.findall("ns:url", ns):
            loc = url_elem.find("ns:loc", ns)
            lastmod = url_elem.find("ns:lastmod", ns)
            if loc is not None:
                mod_date = None
                if lastmod is not None:
                    try:
                        mod_date = datetime.fromisoformat(
                            lastmod.text.replace("Z", "+00:00")
                        )
                    except Exception:
                        pass
                all_jobs.append({
                    "url": loc.text,
                    "lastmod": mod_date,
                })

        # Sort by most recent first
        all_jobs.sort(
            key=lambda x: x["lastmod"] or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        return all_jobs

    async def _fetch_job_page(
        self, client: httpx.AsyncClient, url: str
    ) -> str | None:
        """Fetch a single job page with retry."""
        try:
            resp = await client.get(url, timeout=self.timeout, follow_redirects=True)
            if resp.status_code == 200:
                return resp.text
        except Exception:
            pass
        return None

    async def _process_job(
        self,
        client: httpx.AsyncClient,
        semaphore: asyncio.Semaphore,
        url: str,
        lastmod: datetime | None,
    ) -> JobPosting | None:
        """Fetch, parse, and filter a single Cutshort job page."""
        job_id = url.split("-")[-1] if "-" in url else ""
        if not job_id:
            return None

        async with semaphore:
            # Rate limiting delay
            await asyncio.sleep(self.delay)

            html = await self._fetch_job_page(client, url)
            if not html:
                return None

            job_data = self._parse_job_from_html(html, url)
            if not job_data:
                return None

            # India-only filter
            if not self._is_india_job(job_data["location"], job_data.get("json_ld")):
                return None

            return JobPosting(
                source=JobSource.CUTSHORT,
                source_id=f"cutshort-{job_id}",
                title=job_data["title"],
                company=job_data["company"],
                location=job_data["location"],
                url=job_data["url"],
                description=job_data["description"],
                posted_at=lastmod,
            )

    async def collect(self) -> Sequence[JobPosting]:
        """Collect India jobs from Cutshort sitemap (async, rate-limited)."""
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

        async with httpx.AsyncClient(headers=headers) as client:
            # Step 1: Fetch sitemap
            self.logger.info("[Cutshort] Fetching sitemap ...")
            all_urls = await self._fetch_sitemap(client)
            self.logger.info("[Cutshort] Found %d total job URLs in sitemap", len(all_urls))

            # Step 2: Process jobs concurrently with semaphore (rate-limited)
            semaphore = asyncio.Semaphore(self.max_concurrency)
            jobs: list[JobPosting] = []

            # Process in batches to allow early stopping at max_jobs
            batch_size = 100
            for i in range(0, len(all_urls), batch_size):
                if len(jobs) >= self.max_jobs:
                    break

                batch = all_urls[i:i + batch_size]
                tasks = [
                    self._process_job(client, semaphore, item["url"], item["lastmod"])
                    for item in batch
                ]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                for result in results:
                    if isinstance(result, Exception):
                        continue
                    if result is not None:
                        jobs.append(result)

                self.logger.info(
                    "[Cutshort] Processed %d/%d URLs, %d India jobs so far",
                    min(i + batch_size, len(all_urls)),
                    len(all_urls),
                    len(jobs),
                )

                if len(jobs) >= self.max_jobs:
                    break

        jobs = jobs[:self.max_jobs]
        self.logger.info("[Cutshort] Total: %d India jobs collected", len(jobs))
        return jobs
