"""
Async orchestrator — runs all configured collectors concurrently.

Usage:
    python -m data_collection.run_all_async                          # all no-auth collectors (incl. LinkedIn)
    python -m data_collection.run_all_async --with-browser           # + Workday (sequential)
    python -m data_collection.run_all_async --cutshort-limit 500     # cap Cutshort at 500
    python -m data_collection.run_all_async --cutshort-limit 1000    # full Cutshort scrape
"""

import asyncio
import logging
import sys
import time
from typing import Callable

from data_collection.collectors.base import BaseCollector, AsyncBaseCollector
from data_collection.collectors.remotive_async import AsyncRemotiveCollector
from data_collection.collectors.greenhouse_async import AsyncGreenhouseCollector
from data_collection.collectors.lever_async import AsyncLeverCollector
from data_collection.collectors.remoteok import AsyncRemoteOKCollector
from data_collection.collectors.arbeitnow import AsyncArbeitnowCollector
from data_collection.collectors.himalayas import AsyncHimalayasCollector
from data_collection.collectors.yc_jobs import AsyncYCCollector
from data_collection.collectors.cutshort import AsyncCutshortCollector
from data_collection.collectors.linkedin import AsyncLinkedInCollector
from data_collection.collectors.workday import WorkdayScraper
from data_collection.database import get_connection, init_db, insert_run_history, persist_jobs
from data_collection.models import JobPosting
from datetime import datetime, timezone

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("run_all_async")


def _parse_cutshort_limit(flags: set[str]) -> int:
    """Parse --cutshort-limit N from command-line flags."""
    args = sys.argv[1:]
    for i, arg in enumerate(args):
        if arg == "--cutshort-limit" and i + 1 < len(args):
            try:
                return int(args[i + 1])
            except ValueError:
                pass
    return 1000  # default: up to 1000 India jobs


# Async collectors (run concurrently)
def _build_async_collectors() -> list[AsyncBaseCollector]:
    """Build the list of async collectors based on CLI flags."""
    flags = set(sys.argv[1:])
    cutshort_limit = _parse_cutshort_limit(flags)

    collectors: list[AsyncBaseCollector] = [
        AsyncRemotiveCollector(),
        AsyncGreenhouseCollector(),
        AsyncLeverCollector(),
        AsyncRemoteOKCollector(),
        AsyncArbeitnowCollector(),
        AsyncHimalayasCollector(),
        AsyncYCCollector(months_back=3),       # HN "Who is hiring?" — last 3 months
        AsyncCutshortCollector(
            max_jobs=cutshort_limit,
            max_concurrency=10,
            delay_between_requests=0.5,
        ),
        AsyncLinkedInCollector(
            time_filter="week",
            max_jobs_per_query=75,
            concurrency=2,
            delay_between_requests=3.0,
        ),
    ]

    return collectors


# Sync collectors (run sequentially, only with --with-browser)
SYNC_COLLECTORS: list[BaseCollector] = [
    WorkdayScraper(),
]


async def run_async_collectors(
    collectors: list[AsyncBaseCollector],
    progress_cb: Callable | None = None,
) -> list[JobPosting]:
    """Run async collectors concurrently, with optional per-source progress callback.

    The callback signature: cb(source_name: str, status: str, jobs_found: int = 0,
                              error: str | None = None)
    Status values: "running" (started), "completed", "error".
    """
    all_jobs: list[JobPosting] = []

    async def _run_one(collector: AsyncBaseCollector) -> list[JobPosting]:
        sn = collector.source_name
        if progress_cb:
            progress_cb(sn, "running")
        try:
            jobs = await collector.run()
            if progress_cb:
                progress_cb(sn, "completed", len(jobs))
            return jobs
        except Exception as exc:
            if progress_cb:
                progress_cb(sn, "error", 0, str(exc))
            raise

    results = await asyncio.gather(
        *[_run_one(c) for c in collectors],
        return_exceptions=True,
    )

    for collector, result in zip(collectors, results):
        if isinstance(result, Exception):
            logger.error("Collector %s failed: %s", collector.source_name, result)
        else:
            all_jobs.extend(result)
            logger.info("  %s: %d jobs", collector.source_name, len(result))

    return all_jobs


def run_sync_collectors(collectors: list[BaseCollector]) -> list[JobPosting]:
    """Run sync collectors sequentially."""
    all_jobs: list[JobPosting] = []
    for collector in collectors:
        try:
            results = collector.run()
            all_jobs.extend(results)
            logger.info("  %s: %d jobs", collector.source_name, len(results))
        except Exception:
            logger.exception("Collector %s failed, skipping", collector.source_name)
    return all_jobs



async def main_async() -> None:
    start = time.time()
    flags = set(sys.argv[1:])
    logger.info("=" * 50)
    logger.info("Starting async job collection run")
    logger.info("=" * 50)

    # Phase 1: Async collectors (concurrent)
    logger.info("Phase 1: Async collectors (concurrent) ...")
    async_collectors = _build_async_collectors()
    async_jobs = await run_async_collectors(async_collectors)
    inserted, existing = persist_jobs(async_jobs)
    logger.info(
        "Phase 1 done: %d collected, %d new, %d duplicate",
        len(async_jobs), inserted, existing,
    )

    # Phase 2: Sync collectors (sequential) — only with --with-browser or --all
    if "--with-browser" in flags or "--all" in flags:
        logger.info("Phase 2: Sync collectors (sequential) ...")
        sync_jobs = run_sync_collectors(SYNC_COLLECTORS)
        i2, e2 = persist_jobs(sync_jobs)
        logger.info("Phase 2 done: %d collected, %d new, %d duplicate", len(sync_jobs), i2, e2)
        inserted += i2
        existing += e2

    elapsed = time.time() - start

    # ── Always score new jobs against active profiles ──
    try:
        from data_collection.user_profile import score_all_new_jobs_for_all_profiles
        scored = score_all_new_jobs_for_all_profiles()
        if scored:
            logger.info("Scored %d new jobs across active profiles", scored)
    except Exception:
        logger.exception("Post-collection scoring failed")

    logger.info("=" * 50)
    logger.info("Collection complete: %d new jobs in %.1fs", inserted, elapsed)
    logger.info("=" * 50)

    # Record run history
    _record_run_history(elapsed)


def _record_run_history(elapsed: float) -> None:
    """Record this run's stats to the run_history table."""
    try:
        conn = get_connection()
        init_db(conn)

        total = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        unique = conn.execute("SELECT COUNT(DISTINCT dedup_key) FROM jobs").fetchone()[0]
        india = conn.execute("SELECT COUNT(*) FROM jobs WHERE is_india = 1").fetchone()[0]

        # Per-source counts
        source_counts = {}
        for row in conn.execute("SELECT source, COUNT(*) as c FROM jobs GROUP BY source"):
            source_counts[row["source"]] = row["c"]

        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        stats = {
            "run_date": now,
            "total_jobs": total,
            "unique_jobs": unique,
            "india_jobs": india,
            "gh_jobs": source_counts.get("greenhouse", 0),
            "workday_jobs": source_counts.get("workday", 0),
            "lever_jobs": source_counts.get("lever", 0),
            "cutshort_jobs": source_counts.get("cutshort", 0),
            "remotive_jobs": source_counts.get("remotive", 0),
            "remoteok_jobs": source_counts.get("remoteok", 0),
            "arbeitnow_jobs": source_counts.get("arbeitnow", 0),
            "himalayas_jobs": source_counts.get("himalayas", 0),
            "linkedin_jobs": source_counts.get("linkedin", 0),
            "run_time_s": elapsed,
            "notes": f"yc_jobs={source_counts.get('yc_jobs', 0)}",
        }

        insert_run_history(conn, stats)
        conn.close()
        logger.info("Run history recorded")
    except Exception:
        logger.exception("Failed to record run history")


def main() -> None:
    asyncio.run(main_async())


# ── Programmatic entry point (for dashboard trigger) ────────────────────

def _build_collectors(
    cutshort_limit: int = 1000,
    search_roles: list[str] | None = None,
    search_locations: list[str] | None = None,
) -> list[AsyncBaseCollector]:
    """Build async collectors with explicit parameters.

    Args:
        cutshort_limit: Max Cutshort jobs to scrape.
        search_roles: Job titles from the profile to use as search queries
                      (for sources that support search: LinkedIn, Adzuna, JSearch).
        search_locations: Preferred locations from the profile.
    """
    roles = search_roles or []
    locations = search_locations or []

    # ── Build search queries for parameterizable sources ──
    linkedin_queries = _build_search_queries(roles, locations, default_roles=LINKEDIN_DEFAULT_ROLES)

    return [
        AsyncRemotiveCollector(),
        AsyncGreenhouseCollector(),
        AsyncLeverCollector(),
        AsyncRemoteOKCollector(),
        AsyncArbeitnowCollector(),
        AsyncHimalayasCollector(),
        AsyncYCCollector(months_back=3),
        AsyncCutshortCollector(
            max_jobs=cutshort_limit,
            max_concurrency=10,
            delay_between_requests=0.5,
        ),
        AsyncLinkedInCollector(
            queries=linkedin_queries if linkedin_queries else None,
            time_filter="week",
            max_jobs_per_query=75,
            concurrency=2,
            delay_between_requests=3.0,
        ),
    ]


# Default fallback terms (used when no profile is set)
LINKEDIN_DEFAULT_ROLES = [
    "software engineer", "backend engineer", "frontend engineer",
    "full stack engineer", "machine learning engineer", "data engineer",
    "devops engineer", "platform engineer", "engineering manager",
    "site reliability engineer",
]
JSEARCH_DEFAULT_QUERIES = [
    "python developer", "software engineer", "backend engineer",
    "full stack developer", "data engineer", "devops engineer",
    "site reliability engineer", "frontend engineer",
    "machine learning engineer",
]
JSEARCH_DEFAULT_LOCATIONS = [
    "remote", "bangalore, india", "mumbai, india", "delhi, india",
    "pune, india", "hyderabad, india", "chennai, india",
]


def _build_search_queries(
    roles: list[str],
    locations: list[str],
    default_roles: list[str] | None = None,
) -> list[dict]:
    """Build LinkedIn-style search queries: (role × location) pairs.

    If no roles given, fallback to default_roles with broad India locations.
    """
    if not roles and default_roles:
        roles = default_roles

    if not locations:
        locations = ["India"]

    queries: list[dict] = []
    seen = set()
    for role in roles:
        for loc in locations[:6]:  # cap locations to avoid explosion
            key = f"{role}|{loc}"
            if key not in seen:
                seen.add(key)
                queries.append({"keywords": role, "location": loc})
    return queries


async def run_collection(
    cutshort_limit: int = 500,
    with_browser: bool = False,
    search_roles: list[str] | None = None,
    search_locations: list[str] | None = None,
    progress_cb: Callable | None = None,
) -> dict:
    """Run all collectors. Returns result dict.

    Args:
        cutshort_limit: Max Cutshort jobs to scrape (lower = faster).
        with_browser: If True, also run Workday scraper (slower).
        search_roles: Profile target roles — used to focus search collectors.
        search_locations: Profile preferred locations — used to focus searches.
        progress_cb: Optional callback for per-source progress:
                     cb(source_name, status, jobs_found=0, error=None)
                     status ∈ {"running", "completed", "error"}

    Returns:
        {
            "inserted": int,     # new jobs added to global pool
            "existing": int,     # duplicates skipped
            "elapsed": float,    # seconds
            "errors": [str],     # collector error messages
        }
    """
    start = time.time()
    errors: list[str] = []
    total_inserted = 0
    total_existing = 0

    # Phase 1: Async collectors (scoped to profile preferences)
    collectors = _build_collectors(
        cutshort_limit=cutshort_limit,
        search_roles=search_roles,
        search_locations=search_locations,
    )
    try:
        async_jobs = await run_async_collectors(collectors, progress_cb=progress_cb)
    except Exception as exc:
        errors.append(f"async phase: {exc}")
        async_jobs = []

    # Phase 2: Sync collectors (Workday)
    if with_browser:
        try:
            sync_jobs = run_sync_collectors(SYNC_COLLECTORS)
        except Exception as exc:
            errors.append(f"sync phase: {exc}")
            sync_jobs = []
        async_jobs.extend(sync_jobs)

    # ── Post-collection filtering ──
    # Apply profile-based filters to prune irrelevant jobs from sources that
    # don't support query-based search (Remotive, Greenhouse, Lever, etc.)
    before_filter = len(async_jobs)
    if search_roles or search_locations:
        async_jobs = _post_filter_jobs(async_jobs, search_roles, search_locations)
        filtered_out = before_filter - len(async_jobs)
        if filtered_out:
            logger.info(
                "Post-filter: kept %d/%d jobs (filtered %d irrelevant)",
                len(async_jobs), before_filter, filtered_out,
            )

    inserted, existing = persist_jobs(async_jobs)
    total_inserted += inserted
    total_existing += existing

    # ── Always score new jobs against active profiles ──
    scored_count = 0
    try:
        from data_collection.user_profile import score_all_new_jobs_for_all_profiles
        scored_count = score_all_new_jobs_for_all_profiles()
        if scored_count:
            logger.info("Scored %d new jobs across active profiles", scored_count)
    except Exception as exc:
        errors.append(f"scoring: {exc}")
        logger.exception("Post-collection scoring failed")

    elapsed = time.time() - start

    # Record run history
    _record_run_history(elapsed)

    return {
        "inserted": total_inserted,
        "existing": total_existing,
        "elapsed": round(elapsed, 1),
        "errors": errors,
        "scored": scored_count,
    }


def _post_filter_jobs(
    jobs: list,
    search_roles: list[str],
    search_locations: list[str],
) -> list:
    """Post-collection filter: keep only jobs that match profile preferences.

    This is a loose filter — it keeps jobs where the title or description
    mentions any target role keyword, and the location overlaps. We don't
    want to be too aggressive since the scoring engine will rank them later.
    """
    if not search_roles and not search_locations:
        return jobs

    role_keywords: set[str] = set()
    for role in search_roles:
        for word in role.lower().split():
            if len(word) > 2:  # skip short words like "in", "of"
                role_keywords.add(word)

    loc_keywords: set[str] = set()
    for loc in search_locations:
        for word in loc.lower().split(","):
            word = word.strip()
            if len(word) > 1:
                loc_keywords.add(word)

    # Special: "remote" should match in location
    has_remote = "remote" in {l.lower() for l in search_locations}

    keep = []
    for job in jobs:
        title_lower = (job.title or "").lower()
        desc_lower = (job.description or "")[:2000].lower()
        loc_lower = (job.location or "").lower()
        combined = f"{title_lower} {desc_lower}"

        # Title/role match: at least one role keyword in title or description
        role_match = False
        if role_keywords:
            for kw in role_keywords:
                if kw in title_lower:
                    role_match = True
                    break
            if not role_match:
                # Check if any full role phrase appears
                for role in search_roles:
                    if role.lower() in combined:
                        role_match = True
                        break
        else:
            role_match = True  # no role filter

        # Location match
        loc_match = False
        if loc_keywords:
            for kw in loc_keywords:
                if kw in loc_lower:
                    loc_match = True
                    break
            if not loc_match and has_remote and "remote" in loc_lower:
                loc_match = True
        else:
            loc_match = True

        if role_match and loc_match:
            keep.append(job)

    return keep


if __name__ == "__main__":
    main()
