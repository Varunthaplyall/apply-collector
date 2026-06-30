"""
Orchestrator — runs all configured collectors and writes results to the database.

Usage:
    python -m data_collection.run_all                        # no-auth collectors
    python -m data_collection.run_all --with-keys            # + Adzuna, JSearch
    python -m data_collection.run_all --with-browser         # + Workday
    python -m data_collection.run_all --with-linkedin        # + LinkedIn guest API (rate-limited)
    python -m data_collection.run_all --all                  # everything
"""

import logging
import os
import sys
import time

from dotenv import load_dotenv

from data_collection.collectors.remotive import RemotiveCollector
from data_collection.collectors.greenhouse import GreenhouseCollector
from data_collection.collectors.workday import WorkdayScraper
from data_collection.collectors.lever import LeverCollector
from data_collection.collectors.cutshort import CutshortCollector
from data_collection.collectors.base import BaseCollector
from data_collection.database import persist_jobs
from data_collection.models import JobPosting

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("run_all")


# --- No-auth collectors (always run) ---
REST_COLLECTORS: list[BaseCollector] = [
    RemotiveCollector(),
    GreenhouseCollector(),
    LeverCollector(),
    CutshortCollector(max_jobs=100),  # Sample 100 recent jobs from Cutshort
]

# --- API-key collectors (--with-keys or --all) ---
def _get_keyed_collectors() -> list[BaseCollector]:
    enabled: list[BaseCollector] = []
    adzuna_id = os.getenv("ADZUNA_APP_ID")
    adzuna_key = os.getenv("ADZUNA_API_KEY")
    if adzuna_id and adzuna_key:
        from data_collection.collectors.adzuna import AdzunaCollector
        enabled.append(AdzunaCollector(app_id=adzuna_id, app_key=adzuna_key))
    jsearch_key = os.getenv("RAPIDAPI_KEY")
    if jsearch_key:
        from data_collection.collectors.jsearch import JSearchCollector
        enabled.append(JSearchCollector(api_key=jsearch_key))
    return enabled


# --- Browser-based collectors (--with-browser or --all) ---
BROWSER_COLLECTORS: list[BaseCollector] = [
    WorkdayScraper(),
]

# --- LinkedIn collector (--with-linkedin or --all) ---
# Uses LinkedIn's guest job search API (rate-limited, no auth)
def _get_linkedin_collector() -> list[BaseCollector]:
    from data_collection.collectors.linkedin import LinkedInCollector
    return [LinkedInCollector(time_filter="week", max_jobs_per_query=75)]


def run_collectors(collectors: list[BaseCollector]) -> list[JobPosting]:
    """Run a list of collectors and return all collected jobs."""
    all_jobs: list[JobPosting] = []
    for collector in collectors:
        try:
            results = collector.run()
            all_jobs.extend(results)
            logger.info(
                "  %s: %d jobs (total: %d)",
                collector.source_name,
                len(results),
                len(all_jobs),
            )
        except Exception:
            logger.exception("Collector %s failed, skipping", collector.source_name)
    return all_jobs



def main() -> None:
    start = time.time()
    flags = set(sys.argv[1:])
    logger.info("=" * 50)
    logger.info("Starting full job collection run")
    logger.info("=" * 50)

    # Phase 1: No-auth collectors
    logger.info("Phase 1: No-auth collectors ...")
    api_jobs = run_collectors(REST_COLLECTORS)
    inserted, existing = persist_jobs(api_jobs)
    logger.info(
        "Phase 1 done: %d collected, %d new, %d duplicate",
        len(api_jobs), inserted, existing,
    )

    # Phase 2: API-key collectors
    if "--with-keys" in flags or "--all" in flags:
        keyed = _get_keyed_collectors()
        if keyed:
            logger.info("Phase 2: API-key collectors ...")
            keyed_jobs = run_collectors(keyed)
            i2, e2 = persist_jobs(keyed_jobs)
            logger.info("Phase 2 done: %d collected, %d new, %d duplicate", len(keyed_jobs), i2, e2)
            inserted += i2
            existing += e2

    # Phase 3: Browser-based collectors
    if "--with-browser" in flags or "--all" in flags:
        logger.info("Phase 3: Browser-based collectors ...")
        browser_jobs = run_collectors(BROWSER_COLLECTORS)
        i3, e3 = persist_jobs(browser_jobs)
        logger.info("Phase 3 done: %d collected, %d new, %d duplicate", len(browser_jobs), i3, e3)
        inserted += i3
        existing += e3

    # Phase 4: LinkedIn guest API (rate-limited)
    if "--with-linkedin" in flags or "--all" in flags:
        logger.info("Phase 4: LinkedIn guest API ...")
        linkedin_jobs = run_collectors(_get_linkedin_collector())
        i4, e4 = persist_jobs(linkedin_jobs)
        logger.info("Phase 4 done: %d collected, %d new, %d duplicate", len(linkedin_jobs), i4, e4)
        inserted += i4
        existing += e4

    elapsed = time.time() - start
    logger.info("=" * 50)
    logger.info("Collection complete: %d new jobs in %.1fs", inserted, elapsed)
    logger.info("=" * 50)


if __name__ == "__main__":
    main()
