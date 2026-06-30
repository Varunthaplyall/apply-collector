"""
CLI dashboard for viewing, filtering, and classifying job listings.

Usage:
    python -m normalize.cli                              # show stats
    python -m normalize.cli list                         # list recent jobs
    python -m normalize.cli list --source greenhouse
    python -m normalize.cli list --company stripe
    python -m normalize.cli list --location india
    python -m normalize.cli list --rating STRONG
    python -m normalize.cli list --rating STRONG --location india
    python -m normalize.cli search "python"              # search titles
    python -m normalize.cli export                       # export to JSON
    python -m normalize.cli history                      # run history

    # Classification (Stage 3)
    python -m normalize.cli classify                     # run both passes
    python -m normalize.cli classify --pass1-only        # heuristic only (free)
    python -m normalize.cli classify --ai-only           # AI only (on heuristic results)
    python -m normalize.cli classify --stats             # classification breakdown
    python -m normalize.cli classify --limit 100         # test on 100 jobs
    python -m normalize.cli classify --dry-run --limit 20
"""

import json
import logging
import sys

from typing import Optional

from data_collection.database import get_connection
from normalize.dedup import print_stats

# Logger for classify operations
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("cli")


# ═══════════════════════════════════════════════════════════════════════
# Listing helpers
# ═══════════════════════════════════════════════════════════════════════


def list_jobs(
    source: Optional[str] = None,
    company: Optional[str] = None,
    search: Optional[str] = None,
    location: Optional[str] = None,
    rating: Optional[str] = None,
    limit: int = 20,
) -> None:
    """List jobs with optional filters including AI rating."""
    conn = get_connection()

    query_parts = [
        "SELECT j.id, j.source, j.title, j.company, j.location, j.url, j.is_india"
    ]
    rating_display = ""
    if rating:
        query_parts.append(", c.role_fit, c.match_score, c.reasoning")
        rating_display = f" [{rating}]"
        query_parts.append("FROM jobs j")
        query_parts.append("INNER JOIN classified_jobs c ON j.id = c.job_id")
        query_parts.append("WHERE c.role_fit = ?")
    else:
        query_parts.append("FROM jobs j WHERE 1=1")

    params: list = []
    if rating:
        params.append(rating.upper())

    if source:
        query_parts.append(" AND j.source = ?")
        params.append(source)
    if company:
        query_parts.append(" AND j.company = ?")
        params.append(company)
    if search:
        query_parts.append(" AND (j.title LIKE ? OR j.company LIKE ? OR j.description LIKE ?)")
        params.extend([f"%{search}%"] * 3)
    if location and location.lower() == "india":
        query_parts.append(" AND j.is_india = 1")
    elif location:
        query_parts.append(" AND j.location LIKE ?")
        params.append(f"%{location}%")

    query_parts.append(" ORDER BY j.scraped_at DESC LIMIT ?")
    params.append(limit)

    query = "\n".join(query_parts)
    rows = conn.execute(query, params).fetchall()
    conn.close()

    if not rows:
        has_filters = bool(source or company or search or location or rating)
        filter_desc = f" matching filters{rating_display}" if has_filters else ""
        print(f"No jobs found{filter_desc}.")
        return

    rating_label = f" • Rating: {rating}" if rating else ""
    print(f"\nFound {len(rows)} job(s){rating_label}:\n")
    for row in rows:
        india_tag = " 🇮🇳" if row["is_india"] else ""
        rating_info = ""
        if rating:
            score = row["match_score"]
            reason = row["reasoning"] or ""
            rating_info = f"  [{score}] {reason[:80]}"
        print(f"  [{row['id']:>5}] [{row['source']}] {row['title']}{india_tag}{rating_info}")
        print(f"        {row['company']} — {row['location']}")
        if row["url"]:
            print(f"        {row['url']}")
        print()


def export_json(output_file: str = "jobs_export.json", limit: int = 1000) -> None:
    """Export jobs to JSON."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, source, title, company, location, url, description, "
        "salary_range, posted_at, scraped_at FROM jobs ORDER BY scraped_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()

    jobs = [dict(row) for row in rows]
    with open(output_file, "w") as f:
        json.dump(jobs, f, indent=2, default=str)

    print(f"Exported {len(jobs)} jobs to {output_file}")


def show_counts() -> None:
    """Show summary counts per source/company."""
    conn = get_connection()

    total = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    dedup_keys = conn.execute(
        "SELECT COUNT(DISTINCT dedup_key) FROM jobs"
    ).fetchone()[0]
    duplicates = total - dedup_keys
    india_count = conn.execute(
        "SELECT COUNT(*) FROM jobs WHERE is_india = 1"
    ).fetchone()[0]

    print(f"\nTotal jobs:    {total}")
    print(f"Unique jobs:   {dedup_keys}")
    print(f"Duplicates:    {duplicates}")
    print(f"India jobs:    {india_count}")

    print_stats(conn)
    conn.close()


def show_run_history() -> None:
    """Show run history growth over time."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM run_history ORDER BY run_date DESC"
        ).fetchall()
    except Exception:
        print("No run history found. Run a collection first.")
        conn.close()
        return

    if not rows:
        print("No run history entries yet.")
        conn.close()
        return

    print(f"\n{'='*120}")
    print(f"  Run History ({len(rows)} entries)")
    print(f"{'='*120}")
    print(
        f"\n{'Date':<20} {'Total':>7} {'Unique':>7} {'India':>6} "
        f"{'GH':>6} {'WD':>5} {'Lever':>6} {'Cut':>5} {'Remot':>6} "
        f"{'ROK':>5} {'AN':>5} {'Him':>5} {'Time':>6}"
    )
    print("-" * 120)

    for row in rows:
        print(
            f"{row['run_date']:<20} "
            f"{row['total_jobs']:>7} "
            f"{row['unique_jobs']:>7} "
            f"{row['india_jobs']:>6} "
            f"{row['gh_jobs']:>6} "
            f"{row['workday_jobs']:>5} "
            f"{row['lever_jobs']:>6} "
            f"{row['cutshort_jobs']:>5} "
            f"{row['remotive_jobs']:>6} "
            f"{row['remoteok_jobs']:>5} "
            f"{row['arbeitnow_jobs']:>5} "
            f"{row['himalayas_jobs']:>5} "
            f"{row['run_time_s']:>5.1f}s"
        )

    print()
    conn.close()


# ═══════════════════════════════════════════════════════════════════════
# Classification
# ═══════════════════════════════════════════════════════════════════════


def show_classification_stats() -> None:
    """Display classification breakdown across both passes."""
    conn = get_connection()

    total = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    unique = conn.execute(
        "SELECT COUNT(DISTINCT dedup_key) FROM jobs"
    ).fetchone()[0]

    # Pass 1 stats
    heur_done = conn.execute(
        "SELECT COUNT(*) FROM heuristic_results"
    ).fetchone()[0]
    unclassified = total - heur_done

    heur_keep = conn.execute(
        "SELECT COUNT(*) FROM heuristic_results WHERE result = 'KEEP'"
    ).fetchone()[0]
    heur_skip = conn.execute(
        "SELECT COUNT(*) FROM heuristic_results WHERE result = 'SKIP'"
    ).fetchone()[0]
    heur_maybe = conn.execute(
        "SELECT COUNT(*) FROM heuristic_results WHERE result = 'MAYBE'"
    ).fetchone()[0]

    # AI queue = KEEP + MAYBE
    ai_queue = heur_keep + heur_maybe

    # Pass 2 stats
    ai_done = conn.execute(
        "SELECT COUNT(*) FROM classified_jobs"
    ).fetchone()[0]
    ai_pending = ai_queue - ai_done

    strong = conn.execute(
        "SELECT COUNT(*) FROM classified_jobs WHERE role_fit = 'STRONG'"
    ).fetchone()[0]
    good = conn.execute(
        "SELECT COUNT(*) FROM classified_jobs WHERE role_fit = 'GOOD'"
    ).fetchone()[0]
    weak = conn.execute(
        "SELECT COUNT(*) FROM classified_jobs WHERE role_fit = 'WEAK'"
    ).fetchone()[0]
    ai_skip = conn.execute(
        "SELECT COUNT(*) FROM classified_jobs WHERE role_fit = 'SKIP'"
    ).fetchone()[0]

    conn.close()

    def pct(n: int, d: int) -> str:
        if d == 0:
            return "  0.0%"
        return f"{n / d * 100:5.1f}%"

    print(f"\n{'='*58}")
    print("  Classification Summary")
    print(f"{'='*58}")
    print(f"  Total jobs:        {total:>6}")
    print(f"  Unique (deduped):  {unique:>6}")
    print()

    # ── Pass 1 ──
    print(f"  ── Pass 1 (Heuristic) ──")
    if heur_done == 0:
        print("    No heuristic results yet. Run: classify --pass1-only")
    else:
        print(f"    Classified:       {heur_done:>6}")
        print(f"    Unclassified:     {unclassified:>6}")
        print()
        print(f"    SKIP   (dropped): {heur_skip:>6}  ({pct(heur_skip, heur_done)})")
        print(f"    KEEP   → AI:      {heur_keep:>6}  ({pct(heur_keep, heur_done)})")
        print(f"    MAYBE  → AI:      {heur_maybe:>6}  ({pct(heur_maybe, heur_done)})")
        print(f"    AI queue:         {ai_queue:>6}")

    # ── Pass 2 ──
    print()
    print(f"  ── Pass 2 (AI — DeepSeek) ──")
    if ai_done == 0:
        print("    No AI results yet. Run: classify --ai-only")
    else:
        print(f"    Classified:       {ai_done:>6}")
        print(f"    Pending:          {ai_pending:>6}")
        print()
        print(f"    STRONG:           {strong:>6}  ({pct(strong, ai_done)})")
        print(f"    GOOD:             {good:>6}  ({pct(good, ai_done)})")
        print(f"    WEAK:             {weak:>6}  ({pct(weak, ai_done)})")
        print(f"    SKIP:             {ai_skip:>6}  ({pct(ai_skip, ai_done)})")

        actionable = strong + good
        print(f"\n    Actionable (STRONG + GOOD): {actionable:>6} jobs")

    print()


def run_classify(args: list[str]) -> None:
    """Handle the 'classify' subcommand."""
    pass1_only = "--pass1-only" in args
    ai_only = "--ai-only" in args
    show_stats = "--stats" in args
    dry_run = "--dry-run" in args

    # Extract --limit N
    limit: Optional[int] = None
    batch_size: int = 20
    for i, arg in enumerate(args):
        if arg == "--limit" and i + 1 < len(args):
            try:
                limit = int(args[i + 1])
            except ValueError:
                print(f"Invalid --limit value: {args[i + 1]}")
                return
        if arg == "--batch-size" and i + 1 < len(args):
            try:
                batch_size = int(args[i + 1])
            except ValueError:
                print(f"Invalid --batch-size value: {args[i + 1]}")
                return

    if show_stats:
        show_classification_stats()
        return

    # ── Run Pass 1 (heuristic) ──
    if not ai_only:
        from data_collection.database import init_db
        from classify.heuristic_filter import (
            HeuristicFilter,
            ensure_heuristic_table,
            run_heuristic_pass,
        )

        conn = get_connection()
        init_db(conn)
        ensure_heuristic_table(conn)

        pending = conn.execute("""
            SELECT COUNT(*) FROM jobs j
            LEFT JOIN heuristic_results h ON j.id = h.job_id
            WHERE h.job_id IS NULL
        """).fetchone()[0]

        if pending == 0:
            logger.info("Heuristic pass: 0 pending (all jobs already classified)")
        else:
            logger.info(f"Heuristic pass: {pending} pending jobs")
            counts = run_heuristic_pass(conn, limit=limit)
            logger.info(
                "Heuristic results: %d KEEP, %d SKIP, %d MAYBE",
                counts["keep"], counts["skip"], counts["maybe"],
            )

        conn.close()

    if pass1_only:
        # Show summary after Pass 1
        show_classification_stats()
        return

    # ── Run Pass 2 (AI) ──
    from data_collection.database import init_db
    from classify.ai_classifier import init_deepseek, run_ai_pass, BATCH_SIZE

    conn = get_connection()
    init_db(conn)

    # Check if we have heuristic results to work from
    ai_pending = conn.execute("""
        SELECT COUNT(*) FROM jobs j
        INNER JOIN heuristic_results h ON j.id = h.job_id
        LEFT JOIN classified_jobs c ON j.id = c.job_id
        WHERE h.result IN ('KEEP', 'MAYBE') AND c.job_id IS NULL
    """).fetchone()[0]

    if ai_pending == 0:
        logger.info("AI pass: 0 pending jobs.")
        logger.info(
            "Run 'classify --pass1-only' first if heuristic pass hasn't run yet."
        )
        conn.close()
        return

    if limit and ai_only:
        effective_limit = limit
    elif limit:
        effective_limit = limit
    else:
        effective_limit = None

    logger.info(f"AI pass: {ai_pending} pending jobs (KEEP + MAYBE from heuristic)")
    logger.info(f"Model: claude-haiku-4-5-20251001, batch_size={batch_size}")

    client = init_deepseek()

    import time as _time
    start = _time.time()
    counts = run_ai_pass(
        client, conn,
        batch_size=batch_size,
        limit=effective_limit,
        dry_run=dry_run,
    )
    elapsed = _time.time() - start

    if not dry_run:
        logger.info(
            "AI pass done in %.1fs: %d STRONG, %d GOOD, %d WEAK, %d SKIP (%d errors)",
            elapsed,
            counts["strong"], counts["good"], counts["weak"],
            counts["skip"], counts["errors"],
        )

    conn.close()
    print()
    show_classification_stats()


# ═══════════════════════════════════════════════════════════════════════
# Command dispatcher
# ═══════════════════════════════════════════════════════════════════════


def print_usage() -> None:
    print(__doc__)


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "stats"):
        show_counts()
        return

    cmd = sys.argv[1]
    rest = sys.argv[2:]

    if cmd == "classify":
        run_classify(rest)
        return

    if cmd == "list":
        kwargs: dict = {}
        i = 0
        while i < len(rest):
            if i + 1 < len(rest):
                key = rest[i].lstrip("--").replace("-", "_")
                kwargs[key] = rest[i + 1]
                i += 2
            else:
                i += 1
        list_jobs(**kwargs)

    elif cmd == "search":
        query = rest[0] if rest else ""
        list_jobs(search=query, limit=30)

    elif cmd == "history":
        show_run_history()

    elif cmd == "export":
        output = rest[0] if len(rest) > 0 else "jobs_export.json"
        limit = int(rest[1]) if len(rest) > 1 else 1000
        export_json(output, limit)

    else:
        print(f"Unknown command: {cmd}")
        print_usage()


if __name__ == "__main__":
    main()
