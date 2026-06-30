"""
LinkedIn job collector — uses LinkedIn's guest jobs search API.

No API key required. Fetches job cards from LinkedIn's public guest search,
parses the HTML, and extracts structured job data.

LinkedIn's guest API returns ~25 jobs per page (pagination via start= offset).
We search by keyword + location combinations and aggregate results.

Usage (standalone):
    python -m data_collection.collectors.linkedin
"""

import asyncio
import hashlib
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Sequence
from urllib.parse import urlencode

import httpx
from bs4 import BeautifulSoup

from data_collection.collectors.base import AsyncBaseCollector
from data_collection.models import JobPosting, JobSource

logger = logging.getLogger(__name__)

# ── LinkedIn Guest API ──────────────────────────────────────────────────
GUEST_SEARCH_URL = (
    "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
)

# Search configurations: (keywords, location) pairs to query
SEARCH_QUERIES: list[dict] = [
    # India — general tech roles
    {"keywords": "software engineer", "location": "India"},
    {"keywords": "backend engineer", "location": "India"},
    {"keywords": "frontend engineer", "location": "India"},
    {"keywords": "full stack engineer", "location": "India"},
    {"keywords": "machine learning engineer", "location": "India"},
    {"keywords": "data engineer", "location": "India"},
    {"keywords": "devops engineer", "location": "India"},
    {"keywords": "platform engineer", "location": "India"},
    {"keywords": "engineering manager", "location": "India"},
    {"keywords": "site reliability engineer", "location": "India"},
    # India — specific cities
    {"keywords": "software engineer", "location": "Bengaluru, Karnataka, India"},
    {"keywords": "software engineer", "location": "Hyderabad, Telangana, India"},
    {"keywords": "software engineer", "location": "Mumbai, Maharashtra, India"},
    {"keywords": "software engineer", "location": "Pune, Maharashtra, India"},
    {"keywords": "software engineer", "location": "Delhi, India"},
    {"keywords": "software engineer", "location": "Chennai, Tamil Nadu, India"},
    # Remote India
    {"keywords": "software engineer", "location": "India (Remote)"},
]

# Time filter values for f_TPR param
TIME_FILTERS = {
    "day": "r86400",
    "week": "r604800",
    "month": "r2592000",
}


def _parse_relative_date(date_text: str) -> datetime | None:
    """Parse LinkedIn relative date strings like '3 weeks ago' into datetime."""
    if not date_text:
        return None

    now = datetime.now(timezone.utc)
    text = date_text.strip().lower()

    # Pattern: "X days ago", "3 weeks ago", "1 month ago", etc.
    match = re.match(
        r"(\d+)\+?\s*(second|minute|hour|day|week|month|year)s?\s+ago", text
    )
    if match:
        amount = int(match.group(1))
        unit = match.group(2)
    else:
        # Short forms: "3d", "2w", "1mo"
        match = re.match(r"(\d+)\+?\s*(d|h|w|mo|y)\b", text)
        if match:
            amount = int(match.group(1))
            short = match.group(2)
            unit_map = {"d": "day", "h": "hour", "w": "week", "mo": "month", "y": "year"}
            unit = unit_map.get(short, "day")
        elif "just now" in text or "today" in text:
            return now
        else:
            return None

    delta_map = {
        "second": 1,
        "minute": 60,
        "hour": 3600,
        "day": 86400,
        "week": 604800,
        "month": 2592000,
        "year": 31536000,
    }
    seconds = amount * delta_map.get(unit, 0)
    if seconds == 0:
        return None

    return now - timedelta(seconds=seconds)


def _parse_linkedin_job_id(url: str) -> str:
    """Extract LinkedIn job ID from URL.

    URL formats:
      - /jobs/view/1234567890/              (old format)
      - /jobs/view/title-slug-1234567890    (current format — ID is the last numeric segment)
    """
    # Try old format first: /view/{digits}/
    match = re.search(r"/view/(\d+)", url)
    if match:
        return match.group(1)

    # Current format: last numeric segment in the URL path
    # e.g. /jobs/view/software-engineer-at-company-4401065375
    match = re.search(r"-(\d{9,12})\b", url)
    if match:
        return match.group(1)

    # Fallback: hash the URL
    return hashlib.md5(url.encode()).hexdigest()[:12]



class AsyncLinkedInCollector(AsyncBaseCollector):
    """Collect jobs from LinkedIn's guest job search API.

    Searches across multiple keyword+location combos, paginates results,
    and deduplicates by LinkedIn job ID.

    NOTE: LinkedIn's guest API is rate-limited. Use conservative concurrency
    and respect delays to avoid temporary IP blocks.
    """

    source_name = JobSource.LINKEDIN.value

    def __init__(
        self,
        queries: list[dict] | None = None,
        time_filter: str = "week",
        max_jobs_per_query: int = 75,
        concurrency: int = 3,
        delay_between_requests: float = 2.0,
        timeout: float = 20.0,
    ):
        self.queries = queries or SEARCH_QUERIES
        self.time_filter = TIME_FILTERS.get(time_filter, TIME_FILTERS["week"])
        self.max_jobs_per_query = max_jobs_per_query
        self.concurrency = concurrency
        self.delay = delay_between_requests
        self.timeout = timeout

        self._seen_ids: set[str] = set()

    def _build_url(self, keywords: str, location: str, start: int = 0) -> str:
        """Build the guest API search URL."""
        params = {
            "keywords": keywords,
            "location": location,
            "start": str(start),
            "f_TPR": self.time_filter,
            "sortBy": "DD",  # Most recent first
        }
        return f"{GUEST_SEARCH_URL}?{urlencode(params)}"

    def _parse_job_card(self, card_html: str) -> JobPosting | None:
        """Parse a single job card from the guest API HTML response."""
        soup = BeautifulSoup(card_html, "html.parser")

        # Find the job link
        link_el = soup.find("a", class_="base-card__full-link")
        if not link_el:
            link_el = soup.find("a", href=re.compile(r"/jobs/view/"))
        if not link_el:
            return None

        url = link_el.get("href", "")
        if url and url.startswith("/"):
            url = f"https://www.linkedin.com{url.split('?')[0]}"
        # Strip query/tracking params for clean URLs
        if url:
            url = url.split("?")[0]
        if not url:
            return None

        job_id = _parse_linkedin_job_id(url)

        # Title
        title_el = soup.find("h3", class_="base-search-card__title")
        if not title_el:
            title_el = soup.find("span", class_=re.compile(r"sr-only"))
        title = title_el.get_text(strip=True) if title_el else ""
        if not title:
            return None

        # Company
        company_el = soup.find("h4", class_="base-search-card__subtitle")
        if not company_el:
            company_el = soup.find("a", class_="hidden-nested-link")
        company = company_el.get_text(strip=True) if company_el else ""

        # Location
        location_el = soup.find("span", class_="job-search-card__location")
        location = location_el.get_text(strip=True) if location_el else ""

        # Posted date
        time_el = soup.find("time", class_="job-search-card__listdate")
        if not time_el:
            time_el = soup.find("time")
        date_str = ""
        if time_el:
            date_str = time_el.get("datetime", "") or time_el.get_text(strip=True)
        posted_at = _parse_relative_date(date_str)

        # Salary (rarely in card, but check)
        salary = None
        salary_el = soup.find("span", class_=re.compile(r"salary|compensation"))
        if salary_el:
            salary = salary_el.get_text(strip=True)

        return JobPosting(
            source=JobSource.LINKEDIN,
            source_id=f"li-{job_id}",
            title=title,
            company=company,
            location=location,
            url=url,
            description="",
            salary_range=salary,
            posted_at=posted_at,
        )

    def _parse_search_results(self, html: str) -> list[JobPosting]:
        """Parse all job cards from a single search results page."""
        soup = BeautifulSoup(html, "html.parser")
        jobs: list[JobPosting] = []

        # LinkedIn guest API returns <li> elements for each job
        cards = soup.find_all("li")
        for card in cards:
            if not card.find("a", href=re.compile(r"/jobs/view/")):
                continue
            try:
                job = self._parse_job_card(str(card))
                if job and job.source_id not in self._seen_ids:
                    self._seen_ids.add(job.source_id)
                    jobs.append(job)
            except Exception:
                logger.debug("Failed to parse card", exc_info=True)

        return jobs

    async def _fetch_page(
        self, client: httpx.AsyncClient, url: str
    ) -> str | None:
        """Fetch a single search results page."""
        try:
            resp = await client.get(url, timeout=self.timeout)
            if resp.status_code == 429:
                logger.warning("LinkedIn rate-limited (429). Waiting 30s...")
                await asyncio.sleep(30)
                return None
            if resp.status_code != 200:
                logger.debug("LinkedIn returned HTTP %d", resp.status_code)
                return None
            return resp.text
        except httpx.TimeoutException:
            logger.debug("LinkedIn timeout: %s", url[:80])
            return None
        except Exception as e:
            logger.debug("LinkedIn fetch error: %s", e)
            return None

    async def _search_query(
        self,
        client: httpx.AsyncClient,
        semaphore: asyncio.Semaphore,
        query: dict,
    ) -> list[JobPosting]:
        """Search LinkedIn for one keyword+location combo, with pagination."""
        keywords = query["keywords"]
        location = query["location"]
        query_label = f"{keywords} in {location}"

        all_jobs: list[JobPosting] = []
        page_size = 25

        for start in range(0, self.max_jobs_per_query, page_size):
            if len(all_jobs) >= self.max_jobs_per_query:
                break

            url = self._build_url(keywords, location, start)

            async with semaphore:
                await asyncio.sleep(self.delay)
                html = await self._fetch_page(client, url)

            if not html:
                break

            jobs = self._parse_search_results(html)
            if not jobs:
                break

            all_jobs.extend(jobs)
            logger.debug(
                "[LinkedIn] %s: page %d → %d jobs (total: %d)",
                query_label,
                start // page_size + 1,
                len(jobs),
                len(all_jobs),
            )

        logger.info("[LinkedIn] %s: %d jobs collected", query_label, len(all_jobs))
        return all_jobs

    async def collect(self) -> Sequence[JobPosting]:
        """Search LinkedIn across all configured queries concurrently."""
        all_jobs: list[JobPosting] = []

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
        }

        semaphore = asyncio.Semaphore(self.concurrency)

        async with httpx.AsyncClient(
            headers=headers,
            follow_redirects=True,
            timeout=self.timeout,
        ) as client:
            tasks = [
                self._search_query(client, semaphore, query)
                for query in self.queries
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                logger.warning("LinkedIn query failed: %s", result)
            else:
                all_jobs.extend(result)

        self.logger.info(
            "[LinkedIn] Total: %d unique jobs across %d queries",
            len(all_jobs),
            len(self.queries),
        )
        return all_jobs


# ── Sync wrapper (for run_all.py) ───────────────────────────────────────
class LinkedInCollector(AsyncLinkedInCollector):
    """Synchronous wrapper for async LinkedIn collector."""

    def collect(self) -> Sequence[JobPosting]:
        return asyncio.run(super().collect())


# ── Standalone test ─────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    async def test():
        collector = AsyncLinkedInCollector(
            time_filter="week",
            max_jobs_per_query=25,
            concurrency=2,
            delay_between_requests=3.0,
        )
        jobs = await collector.collect()
        print(f"\nTotal LinkedIn jobs: {len(jobs)}")
        for j in jobs[:10]:
            print(f"  {j.title} @ {j.company} — {j.location} | {j.url}")

    asyncio.run(test())
