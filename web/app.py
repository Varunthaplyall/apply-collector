"""
Flask API + React SPA server for the job collection pipeline.

Usage:
    python -m web.app
    python -m web.app --port 8080 --host 0.0.0.0

Front-end: React SPA served from static/dist/ (client-side routing via React Router)
API:
    GET  /api/stats             Dashboard statistics
    GET  /api/jobs              Filterable job listing (JSON)
    GET  /api/profile           Active candidate profile
    POST /api/profile           Save/update profile
    POST /api/profile/<id>/deactivate  Deactivate a profile
    GET  /api/history           Run history (JSON)
    POST /api/run/collect       Trigger Stage 1 (collection)
    POST /api/run/normalize     Trigger Stage 2 (normalization/dedup)
    GET  /api/run/status        SSE stream for live run progress
"""

import asyncio
import hashlib
import hmac
import json
import logging
import os as _os
import queue
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, Response, jsonify, request, send_from_directory, stream_with_context

# Ensure the project root is on sys.path so data_collection imports work
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from data_collection.auth import get_current_user, optional_auth, require_auth
from data_collection.database import get_connection, init_db
from data_collection.user_profile import (
    CandidateProfile,
    get_active_profile,
    save_profile,
    deactivate_profile,
    score_all_new_jobs,
    dismiss_job,
    save_job,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] web: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("web")

app = Flask(
    __name__,
    template_folder=str(Path(__file__).parent / "templates"),
    static_folder=str(Path(__file__).parent / "static"),
)


# ── Static file discovery (for SPA asset auto-detection) ─────────────────

def _list_static_files() -> list[str]:
    """Walk the static directory and return relative file paths."""
    static_dir = Path(__file__).parent / "static"
    if not static_dir.exists():
        return []
    files = []
    for f in static_dir.rglob("*"):
        if f.is_file():
            files.append(str(f.relative_to(static_dir)))
    return files


app.jinja_env.globals["static_files"] = _list_static_files


# ── Run state (shared between threads) ──────────────────────────────────

_run_lock = threading.Lock()
_run_active: bool = False
_run_events: queue.Queue[dict] = queue.Queue()  # SSE event queue

# Per-source pipeline state — shared between the collection runner thread
# and the polling status endpoint.  Updated by the progress callback.
_pipeline_lock = threading.Lock()
_pipeline_state: dict = {
    "running": False,
    "phase": None,
    "phase_message": "",
    "elapsed_seconds": 0.0,
    "sources": [],
    "total_inserted": 0,
    "total_existing": 0,
    "start_time": None,  # float — time.monotonic() when run started
}

# All possible sources (must stay in sync with run_all_async.py _build_collectors)
_PIPELINE_SOURCES: list[dict] = [
    {"name": "remotive",   "label": "Remotive",   "color": "cyan",     "gradient": "from-cyan-500 to-blue-500"},
    {"name": "greenhouse", "label": "Greenhouse",  "color": "emerald",  "gradient": "from-emerald-500 to-teal-500"},
    {"name": "lever",      "label": "Lever",       "color": "blue",     "gradient": "from-blue-500 to-sky-500"},
    {"name": "remoteok",   "label": "RemoteOK",    "color": "orange",   "gradient": "from-orange-500 to-amber-500"},
    {"name": "arbeitnow",  "label": "Arbeitnow",   "color": "lime",     "gradient": "from-lime-500 to-green-500"},
    {"name": "himalayas",  "label": "Himalayas",   "color": "indigo",   "gradient": "from-indigo-500 to-violet-500"},
    {"name": "yc_jobs",    "label": "YC Jobs",     "color": "pink",     "gradient": "from-pink-500 to-rose-500"},
    {"name": "cutshort",   "label": "Cutshort",    "color": "amber",    "gradient": "from-amber-500 to-orange-500"},
    {"name": "linkedin",   "label": "LinkedIn",    "color": "sky",      "gradient": "from-sky-500 to-cyan-500"},
    {"name": "workday",    "label": "Workday",     "color": "violet",   "gradient": "from-violet-500 to-purple-500"},
]

# Additional sources referenced in SourceBreakdown but not yet in async pipeline
# (shown as pending/not-in-this-run for future compatibility)
_PIPELINE_EXTRA_SOURCES: list[dict] = [
    {"name": "wellfound",  "label": "Wellfound",   "color": "rose",     "gradient": "from-rose-500 to-pink-500"},
    {"name": "adzuna",     "label": "Adzuna",      "color": "teal",     "gradient": "from-teal-500 to-emerald-500"},
    {"name": "iimjobs",    "label": "IIM Jobs",    "color": "fuchsia",  "gradient": "from-fuchsia-500 to-pink-500"},
    {"name": "jsearch",    "label": "JSearch",     "color": "yellow",   "gradient": "from-yellow-500 to-amber-500"},
]


def _init_pipeline_sources() -> list[dict]:
    """Build the initial source list with all sources set to 'pending'."""
    sources = []
    for s in _PIPELINE_SOURCES:
        sources.append({**s, "status": "pending", "jobs_found": 0, "error": None})
    return sources


def _reset_pipeline_state() -> None:
    """Reset pipeline state for a new run."""
    with _pipeline_lock:
        _pipeline_state["running"] = True
        _pipeline_state["phase"] = None
        _pipeline_state["phase_message"] = ""
        _pipeline_state["elapsed_seconds"] = 0.0
        _pipeline_state["sources"] = _init_pipeline_sources()
        _pipeline_state["total_inserted"] = 0
        _pipeline_state["total_existing"] = 0
        _pipeline_state["start_time"] = None


def _pipeline_progress_callback(source_name: str, status: str, jobs_found: int = 0,
                                 error: str | None = None) -> None:
    """Called from the collection runner to update per-source state (thread-safe)."""
    import time as _time_module
    with _pipeline_lock:
        if _pipeline_state["start_time"] is None:
            _pipeline_state["start_time"] = _time_module.monotonic()
        _pipeline_state["elapsed_seconds"] = round(
            _time_module.monotonic() - _pipeline_state["start_time"], 1
        )
        for s in _pipeline_state["sources"]:
            if s["name"] == source_name:
                s["status"] = status
                if jobs_found > 0:
                    s["jobs_found"] = jobs_found
                if error:
                    s["error"] = error
                break


def _pipeline_phase_callback(phase: str, message: str = "") -> None:
    """Update the current pipeline phase (thread-safe)."""
    import time as _time_module
    with _pipeline_lock:
        _pipeline_state["phase"] = phase
        _pipeline_state["phase_message"] = message
        if _pipeline_state["start_time"] is not None:
            _pipeline_state["elapsed_seconds"] = round(
                _time_module.monotonic() - _pipeline_state["start_time"], 1
            )


def _emit(event: str, data: dict) -> None:
    """Push an SSE event onto the queue."""
    _run_events.put({"event": event, "data": data})


# ═══════════════════════════════════════════════════════════════════════════
# Database helpers
# ═══════════════════════════════════════════════════════════════════════════


def _get_db_stats() -> dict:
    """Gather all dashboard statistics from the database.

    Job counts are global (shared pool).  Profile-scoped stats
    (profile_matches, profile_strong) are per-user via profile_job_matches.
    """
    conn = get_connection()

    total = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    unique = conn.execute("SELECT COUNT(DISTINCT dedup_key) FROM jobs").fetchone()[0]
    duplicates = total - unique
    india_count = conn.execute(
        "SELECT COUNT(*) FROM jobs WHERE is_india = 1"
    ).fetchone()[0]

    # Per-source breakdown
    by_source = {}
    for row in conn.execute(
        "SELECT source, COUNT(*) as c FROM jobs GROUP BY source ORDER BY c DESC"
    ):
        by_source[row["source"]] = row["c"]

    # Top companies
    top_companies = []
    for row in conn.execute(
        "SELECT company, COUNT(*) as c FROM jobs GROUP BY company ORDER BY c DESC LIMIT 10"
    ):
        top_companies.append({"company": row["company"], "count": row["c"]})

    # Top locations (India)
    top_india_locations = []
    for row in conn.execute(
        "SELECT location, COUNT(*) as c FROM jobs WHERE is_india = 1 "
        "GROUP BY location ORDER BY c DESC LIMIT 10"
    ):
        top_india_locations.append({"location": row["location"], "count": row["c"]})

    # Recent runs
    recent_runs = []
    for row in conn.execute(
        "SELECT * FROM run_history ORDER BY run_date DESC LIMIT 5"
    ):
        recent_runs.append(dict(row))

    # Newest scrape
    newest = conn.execute(
        "SELECT MAX(scraped_at) FROM jobs"
    ).fetchone()[0]

    # Today's jobs
    today_jobs = 0
    if newest:
        try:
            today_start = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            today_jobs = conn.execute(
                "SELECT COUNT(*) FROM jobs WHERE scraped_at >= ?",
                (today_start,),
            ).fetchone()[0]
        except Exception:
            logger.debug("Failed to count today's jobs", exc_info=True)

    # Classification stats (if available)
    classified = 0
    strong = 0
    good = 0
    try:
        classified = conn.execute(
            "SELECT COUNT(*) FROM classified_jobs"
        ).fetchone()[0]
        strong = conn.execute(
            "SELECT COUNT(*) FROM classified_jobs WHERE role_fit = 'STRONG'"
        ).fetchone()[0]
        good = conn.execute(
            "SELECT COUNT(*) FROM classified_jobs WHERE role_fit = 'GOOD'"
        ).fetchone()[0]
    except Exception:
        logger.debug("Failed to fetch classification stats", exc_info=True)

    # Profile match stats (scoped to the user's active profile)
    profile_matches = 0
    profile_strong = 0
    profile_good = 0
    auth_user_id = get_current_user()
    active_profile = get_active_profile(user_id=auth_user_id)
    if active_profile and active_profile.id:
        profile_id = active_profile.id
        try:
            profile_matches = conn.execute(
                "SELECT COUNT(*) FROM profile_job_matches WHERE profile_id = ?",
                (profile_id,),
            ).fetchone()[0]
            profile_strong = conn.execute(
                "SELECT COUNT(*) FROM profile_job_matches WHERE profile_id = ? AND score >= 80",
                (profile_id,),
            ).fetchone()[0]
            profile_good = conn.execute(
                "SELECT COUNT(*) FROM profile_job_matches WHERE profile_id = ? AND score >= 50 AND score < 80",
                (profile_id,),
            ).fetchone()[0]
        except Exception:
            logger.debug("Failed to fetch profile match stats", exc_info=True)

    conn.close()

    return {
        "total": total,
        "unique": unique,
        "duplicates": duplicates,
        "india_count": india_count,
        "by_source": by_source,
        "top_companies": top_companies,
        "top_india_locations": top_india_locations,
        "recent_runs": recent_runs,
        "newest_scrape": newest,
        "today_jobs": today_jobs,
        "classified": classified,
        "strong": strong,
        "good": good,
        "profile_matches": profile_matches,
        "profile_strong": profile_strong,
        "profile_good": profile_good,
    }


# Whitelist of safe column/table names for _get_distinct_values
_DISTINCT_COLUMNS = {"source", "company", "location"}
_DISTINCT_TABLES = {"jobs"}


def _get_distinct_values(column: str, table: str = "jobs") -> list[str]:
    """Get distinct values for a column (for filter dropdowns).

    Uses a whitelist to prevent SQL injection through column/table names.
    """
    if column not in _DISTINCT_COLUMNS:
        raise ValueError(f"Invalid column: {column}")
    if table not in _DISTINCT_TABLES:
        raise ValueError(f"Invalid table: {table}")
    conn = get_connection()
    rows = conn.execute(
        f'SELECT DISTINCT "{column}" FROM {table} ORDER BY "{column}"'
    ).fetchall()
    conn.close()
    return [r[column] for r in rows if r[column]]


# ═══════════════════════════════════════════════════════════════════════════
# API — Dashboard Stats
# ═══════════════════════════════════════════════════════════════════════════


@app.route("/api/stats")
@optional_auth
def api_stats():
    """JSON stats endpoint — global job pool with per-user profile matches."""
    return jsonify(_get_db_stats())


# ═══════════════════════════════════════════════════════════════════════════
# API — Jobs
# ═══════════════════════════════════════════════════════════════════════════


@app.route("/api/jobs")
@optional_auth
def api_jobs():
    """JSON jobs listing with filters — global job pool with per-user scoring."""
    source_filter = request.args.get("source", "").strip()
    company_filter = request.args.get("company", "").strip()
    location_filter = request.args.get("location", "").strip()
    search_query = request.args.get("search", "").strip()
    india_only = request.args.get("india", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    sort = request.args.get("sort", "newest").strip()
    page = max(1, request.args.get("page", 1, type=int))
    per_page = 50

    conn = get_connection()

    where_clauses: list[str] = []
    params: list = []

    if source_filter:
        where_clauses.append("j.source = ?")
        params.append(source_filter)
    if company_filter:
        where_clauses.append("j.company LIKE ?")
        params.append(f"%{company_filter}%")
    if location_filter:
        where_clauses.append("j.location LIKE ?")
        params.append(f"%{location_filter}%")
    if search_query:
        where_clauses.append(
            "(j.title LIKE ? OR j.company LIKE ? OR j.description LIKE ?)"
        )
        params.extend([f"%{search_query}%"] * 3)
    if india_only == "1":
        where_clauses.append("j.is_india = 1")
    if date_from:
        where_clauses.append("j.scraped_at >= ?")
        params.append(date_from)
    if date_to:
        where_clauses.append("j.scraped_at <= ?")
        params.append(date_to + " 23:59:59")

    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

    user_id = get_current_user()
    active_profile = get_active_profile(user_id=user_id)
    profile_id = active_profile.id if (active_profile and active_profile.id) else None

    sort_map = {
        "newest": "j.scraped_at DESC",
        "oldest": "j.scraped_at ASC",
        "company": "LOWER(j.company) ASC",
        "title": "LOWER(j.title) ASC",
    }
    if profile_id and sort == "match":
        order_by = "pjm.score DESC NULLS LAST, j.scraped_at DESC"
    else:
        order_by = sort_map.get(sort, "j.scraped_at DESC")

    if sort == "match" and not profile_id:
        sort = "newest"
        order_by = "j.scraped_at DESC"

    count = conn.execute(
        f"SELECT COUNT(*) FROM jobs j WHERE {where_sql}", params
    ).fetchone()[0]

    total_pages = max(1, (count + per_page - 1) // per_page)
    page = min(page, total_pages)
    offset = (page - 1) * per_page

    if profile_id:
        rows = conn.execute(
            f"""
            SELECT j.id, j.source, j.source_id, j.title, j.company, j.location,
                   j.url, j.salary_range, j.posted_at, j.scraped_at, j.is_india,
                   c.role_fit, c.match_score,
                   pjm.score as profile_score, pjm.match_reasons as profile_reasons
            FROM jobs j
            LEFT JOIN classified_jobs c ON j.id = c.job_id
            LEFT JOIN profile_job_matches pjm
                ON j.id = pjm.job_id AND pjm.profile_id = ?
            WHERE {where_sql}
            ORDER BY {order_by}
            LIMIT ? OFFSET ?
            """,
            [profile_id] + params + [per_page, offset],
        ).fetchall()
    else:
        rows = conn.execute(
            f"""
            SELECT j.id, j.source, j.source_id, j.title, j.company, j.location,
                   j.url, j.salary_range, j.posted_at, j.scraped_at, j.is_india,
                   c.role_fit, c.match_score,
                   NULL as profile_score, NULL as profile_reasons
            FROM jobs j
            LEFT JOIN classified_jobs c ON j.id = c.job_id
            WHERE {where_sql}
            ORDER BY {order_by}
            LIMIT ? OFFSET ?
            """,
            params + [per_page, offset],
        ).fetchall()

    sources = _get_distinct_values("source")
    companies = [
        r["company"] for r in conn.execute(
            "SELECT company, COUNT(*) as c FROM jobs GROUP BY company ORDER BY c DESC LIMIT 200"
        ).fetchall()
    ]
    conn.close()

    return jsonify({
        "jobs": [dict(r) for r in rows],
        "count": count,
        "page": page,
        "total_pages": total_pages,
        "sources": sources,
        "companies": companies,
    })


# ═══════════════════════════════════════════════════════════════════════════
# API — Profile
# ═══════════════════════════════════════════════════════════════════════════


def _profile_to_dict(profile) -> dict | None:
    """Convert a CandidateProfile to a JSON-serializable dict."""
    if profile is None:
        return None
    return {
        "id": profile.id or None,
        "name": getattr(profile, 'name', ''),
        "email": getattr(profile, 'email', ''),
        "target_roles": getattr(profile, 'target_roles', []),
        "job_title_aliases": getattr(profile, 'job_title_aliases', []),
        "preferred_locations": getattr(profile, 'preferred_locations', []),
        "skills": getattr(profile, 'skills', []),
        "work_types": getattr(profile, 'work_types', []),
        "experience_years": getattr(profile, 'experience_years_min', 0),
        "remote_only": getattr(profile, 'remote_preference', 'ANY') == 'REMOTE',
        "salary_min": getattr(profile, 'min_salary', 0) or 0,
        "preferred_industries": getattr(profile, 'preferred_industries', []),
        "preferred_company_stage": [getattr(profile, 'company_size_preference', 'ANY')],
        "enabled_sources": getattr(profile, 'preferred_sources', []),
        "keywords_include": getattr(profile, 'include_keywords', []),
        "keywords_exclude": getattr(profile, 'exclude_keywords', []),
        "is_active": getattr(profile, 'active', True),
        "weights": {
            "title": getattr(profile, 'weight_title', 0.30),
            "skills": getattr(profile, 'weight_skills', 0.30),
            "location": getattr(profile, 'weight_location', 0.20),
            "seniority": getattr(profile, 'weight_seniority', 0.10),
            "salary": getattr(profile, 'weight_salary', 0.05),
            "work_type": getattr(profile, 'weight_work_type', 0.05),
        },
    }


def _score_jobs_against_profile(user_id: str | None = None) -> None:
    """Score all unscored jobs against the active profile in the background."""
    import threading
    def _run():
        try:
            score_all_new_jobs(user_id=user_id)
        except Exception:
            logger.exception("Background job scoring failed")
    thread = threading.Thread(target=_run, daemon=True)
    thread.start()


@app.route("/api/profile", methods=["GET", "POST"])
@require_auth
def api_profile():
    """Get or update the active candidate profile (auth required)."""
    user_id = get_current_user()

    if request.method == "POST":
        profile = CandidateProfile.from_form(request.form)
        raw_id = request.form.get("id")
        existing_id = int(raw_id) if raw_id and raw_id.strip() else None
        pid = save_profile(profile, user_id=user_id, profile_id=existing_id)
        _score_jobs_against_profile(user_id=user_id)
        return jsonify({"ok": True, "id": pid})

    profile = get_active_profile(user_id=user_id)
    data = _profile_to_dict(profile)
    if data is None:
        return jsonify(None), 404
    return jsonify(data)


@app.route("/api/profile/status")
@require_auth
def api_profile_status():
    """Check if the current user has an active profile with target roles.

    Used by the frontend to determine whether to redirect to onboarding.
    """
    user_id = get_current_user()
    profile = get_active_profile(user_id=user_id)
    has_profile = bool(profile and profile.target_roles)
    return jsonify({
        "has_profile": has_profile,
        "profile_id": profile.id if profile else None,
    })


@app.route("/api/profile/<int:profile_id>/deactivate", methods=["POST"])
@require_auth
def api_profile_deactivate(profile_id: int):
    """Deactivate a profile (auth required)."""
    deactivate_profile(profile_id)
    return jsonify({"ok": True})


@app.route("/api/jobs/<int:job_id>/dismiss", methods=["POST"])
@require_auth
def api_dismiss_job(job_id: int):
    """Dismiss a job so the algorithm learns to penalize similar ones."""
    user_id = get_current_user()
    profile = get_active_profile(user_id=user_id)
    if not profile:
        return jsonify({"ok": False, "error": "No active profile"}), 404
    dismiss_job(profile.id, job_id)
    return jsonify({"ok": True})


@app.route("/api/jobs/<int:job_id>/save", methods=["POST"])
@require_auth
def api_save_job(job_id: int):
    """Save / unsave a job (clears dismiss, positive signal)."""
    user_id = get_current_user()
    profile = get_active_profile(user_id=user_id)
    if not profile:
        return jsonify({"ok": False, "error": "No active profile"}), 404
    save_job(profile.id, job_id)
    return jsonify({"ok": True})


# ═══════════════════════════════════════════════════════════════════════════
# API — Run History
# ═══════════════════════════════════════════════════════════════════════════


@app.route("/api/history")
def api_history():
    """JSON run history."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM run_history ORDER BY run_date DESC"
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


# ═══════════════════════════════════════════════════════════════════════════
# API — Trigger runs
# ═══════════════════════════════════════════════════════════════════════════


def _run_collection_in_thread(cutshort_limit: int) -> None:
    """Run Stage 1 (collection) in a background thread — writes to global job pool."""
    global _run_active
    # Reset per-source pipeline state
    _reset_pipeline_state()

    try:
        _emit("phase", {"phase": "start", "message": "Starting collection run..."})
        _pipeline_phase_callback("start", "Starting collection run...")

        # Use any active profile to scope search queries, but jobs go to global pool
        profile = get_active_profile(user_id=get_current_user())
        if profile:
            search_roles = profile.target_roles + profile.job_title_aliases
            search_locations = profile.preferred_locations
            msg = (f"Scoping search to: {', '.join(search_roles[:3])}"
                   + (f" in {', '.join(search_locations[:3])}" if search_locations else ""))
            _emit("phase", {"phase": "profile", "message": msg})
            _pipeline_phase_callback("profile", msg)
        else:
            search_roles = None
            search_locations = None
            _emit("phase", {
                "phase": "profile",
                "message": "No profile set — collecting all jobs broadly",
            })
            _pipeline_phase_callback("profile", "No profile set — collecting all jobs broadly")

        # Import here to avoid early imports
        from data_collection.run_all_async import run_collection

        # Build progress callback that bridges to the pipeline state
        def on_source_progress(source_name: str, status: str, jobs_found: int = 0,
                                error: str | None = None) -> None:
            _pipeline_progress_callback(source_name, status, jobs_found, error)
            if status == "running":
                label = source_name
                for s in _PIPELINE_SOURCES:
                    if s["name"] == source_name:
                        label = s["label"]
                        break
                _emit("phase", {
                    "phase": "collecting",
                    "message": f"Collecting from {label}...",
                })

        # We need to run async code from a thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            _emit("phase", {"phase": "collecting", "message": "Collecting from sources..."})
            _pipeline_phase_callback("collecting", "Collecting from sources...")
            result = loop.run_until_complete(
                run_collection(
                    cutshort_limit=cutshort_limit,
                    with_browser=False,
                    search_roles=search_roles,
                    search_locations=search_locations,
                    progress_cb=on_source_progress,
                )
            )
        finally:
            loop.close()

        with _pipeline_lock:
            _pipeline_state["total_inserted"] = result.get("inserted", 0)
            _pipeline_state["total_existing"] = result.get("existing", 0)

        _emit("result", {
            "stage": "collect",
            "inserted": result.get("inserted", 0),
            "existing": result.get("existing", 0),
            "elapsed": result.get("elapsed", 0),
            "errors": result.get("errors", []),
        })

        # Score new jobs against ALL active profiles
        _emit("phase", {"phase": "scoring", "message": "Scoring jobs against all active profiles..."})
        _pipeline_phase_callback("scoring", "Scoring jobs against all active profiles...")
        try:
            from data_collection.user_profile import score_all_new_jobs_for_all_profiles
            scored = score_all_new_jobs_for_all_profiles()
            msg = f"Scored {scored} matches across active profiles"
            _emit("phase", {"phase": "scoring_complete", "message": msg})
            _pipeline_phase_callback("scoring_complete", msg)
        except Exception as exc:
            logger.exception("Job scoring failed")
            _emit("error", {"stage": "scoring", "error": str(exc)})

        _emit("phase", {"phase": "complete", "message": "Collection complete."})
        _pipeline_phase_callback("complete", "Collection complete.")
    except Exception as exc:
        logger.exception("Collection failed")
        _emit("error", {"stage": "collect", "error": str(exc)})
        _pipeline_phase_callback("error", str(exc))
    finally:
        _run_active = False
        _emit("done", {})
        with _pipeline_lock:
            _pipeline_state["running"] = False


def _run_normalize_in_thread() -> None:
    """Run Stage 2 (normalization/dedup) in a background thread."""
    global _run_active
    try:
        _emit("phase", {"phase": "start", "message": "Starting normalization..."})

        from normalize.dedup import get_stats as dedup_stats

        stats = dedup_stats()
        total = stats.get("total", 0)
        by_source = stats.get("by_source", {})

        _emit("result", {
            "stage": "normalize",
            "total": total,
            "by_source": by_source,
        })
        _emit("phase", {"phase": "complete", "message": "Normalization complete."})
    except Exception as exc:
        logger.exception("Normalization failed")
        _emit("error", {"stage": "normalize", "error": str(exc)})
    finally:
        _run_active = False
        _emit("done", {})


@app.route("/api/run/collect", methods=["POST"])
@require_auth
def api_trigger_collect():
    """Trigger Stage 1: Collection — writes to global job pool.

    In production, collection runs via Render cron. This endpoint is kept for
    manual triggering during development / debugging.
    """
    global _run_active

    with _run_lock:
        if _run_active:
            return jsonify({"ok": False, "error": "A run is already in progress"}), 409
        _run_active = True

    # Clear stale events
    while not _run_events.empty():
        try:
            _run_events.get_nowait()
        except queue.Empty:
            break

    cutshort_limit = 10000  # effectively no limit — collect everything
    thread = threading.Thread(
        target=_run_collection_in_thread,
        args=(cutshort_limit,),
        daemon=True,
    )
    thread.start()
    return jsonify({"ok": True, "message": "Collection started"})


@app.route("/api/run/normalize", methods=["POST"])
@require_auth
def api_trigger_normalize():
    """Trigger Stage 2: Normalization/dedup stats refresh."""
    global _run_active
    with _run_lock:
        if _run_active:
            return jsonify({"ok": False, "error": "A run is already in progress"}), 409
        _run_active = True

    while not _run_events.empty():
        try:
            _run_events.get_nowait()
        except queue.Empty:
            break

    thread = threading.Thread(target=_run_normalize_in_thread, daemon=True)
    thread.start()
    return jsonify({"ok": True, "message": "Normalization started"})


@app.route("/api/run/status")
def api_run_status():
    """SSE endpoint — streams run progress events."""
    def event_stream():
        # Send initial state
        yield f"data: {json.dumps({'type': 'connected'})}\n\n"

        while True:
            try:
                event = _run_events.get(timeout=1.0)
                yield f"event: {event['event']}\ndata: {json.dumps(event['data'])}\n\n"
                if event["event"] == "done":
                    break
            except queue.Empty:
                # Send keepalive
                yield f": keepalive\n\n"
                if not _run_active:
                    break

    return Response(
        stream_with_context(event_stream()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.route("/api/run/status/pipeline")
def api_pipeline_status():
    """Poll-based endpoint — returns current pipeline state with per-source status.

    Returns a fast JSON snapshot of the shared pipeline state.  Designed for
    500ms polling from the frontend during a run.
    """
    with _pipeline_lock:
        state = {
            "running": _pipeline_state["running"],
            "phase": _pipeline_state["phase"],
            "phase_message": _pipeline_state["phase_message"],
            "elapsed_seconds": _pipeline_state["elapsed_seconds"],
            "sources": list(_pipeline_state["sources"]),  # shallow copy
            "total_inserted": _pipeline_state["total_inserted"],
            "total_existing": _pipeline_state["total_existing"],
        }
    return jsonify(state)


# ═══════════════════════════════════════════════════════════════════════════
# API — Auth
# ═══════════════════════════════════════════════════════════════════════════


@app.route("/api/auth/me")
@require_auth
def api_auth_me():
    """Return the authenticated user's ID. The frontend calls this to validate
    that a stored token is still valid."""
    return jsonify({"user_id": get_current_user()})


# ── Cron collection (called by Render Cron Job or external scheduler) ──────


@app.route("/api/cron/collect", methods=["POST", "GET"])
def api_cron_collect():
    """Called by Render Cron Job or external scheduler to run collection.

    Protected by a shared secret (CRON_SECRET env var) via HMAC signature.
    When called from Render's Cron Job, the cron runs in a separate container
    and executes ``python -m data_collection.run_all_async`` directly — not
    this endpoint.  This endpoint exists as a fallback for non-Render setups.
    """
    # Shared-secret auth: CRON_SECRET must be set in env vars
    cron_secret = _os.getenv("CRON_SECRET", "")
    if cron_secret:
        # HMAC-based: client sends signature = HMAC-SHA256(secret, timestamp)
        sig = request.headers.get("X-Cron-Signature", "")
        ts = request.headers.get("X-Cron-Timestamp", "")
        if not sig or not ts:
            return jsonify({"error": "Missing cron auth headers"}), 401
        expected = hmac.new(
            cron_secret.encode(), ts.encode(), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return jsonify({"error": "Invalid cron signature"}), 401
    else:
        # No secret set — allow local dev (but log a warning)
        logger.warning("CRON_SECRET not set — cron endpoint is unprotected")

    global _run_active
    with _run_lock:
        if _run_active:
            return jsonify({"ok": False, "error": "A run is already in progress"}), 409
        _run_active = True

    thread = threading.Thread(
        target=_run_collection_in_thread,
        args=(10000,),
        daemon=True,
    )
    thread.start()
    return jsonify({"ok": True, "message": "Cron collection started"})


@app.route("/api/collection/status")
def api_collection_status():
    """Show the status of the last collection run and global job pool stats.

    Used by the frontend to show "Last collected X minutes ago" instead
    of the "Run Pipeline" button.
    """
    conn = get_connection()

    last_run = conn.execute(
        "SELECT * FROM run_history ORDER BY run_date DESC LIMIT 1"
    ).fetchone()

    total_jobs = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    new_today = 0
    try:
        today_start = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        new_today = conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE scraped_at >= ?",
            (today_start,),
        ).fetchone()[0]
    except Exception:
        pass

    conn.close()

    return jsonify({
        "last_run": dict(last_run) if last_run else None,
        "total_jobs": total_jobs,
        "new_today": new_today,
        "running": _run_active,
    })


# ═══════════════════════════════════════════════════════════════════════════
# Front-end — React SPA (catch-all for client-side routing)
# ═══════════════════════════════════════════════════════════════════════════

_SPA_ROUTES = ["/", "/profile", "/jobs", "/history", "/login"]


def _serve_spa():
    """Serve the React SPA index.html directly (Vite-built, hashed assets).

    Uses send_from_directory to serve the raw index.html from static/dist/.
    This avoids Jinja template globbing issues — Vite already injects correct
    <script> and <link> tags with content-hashed filenames.
    """
    dist_dir = Path(__file__).parent / "static" / "dist"
    dist_assets = dist_dir / "assets"
    dist_built = dist_assets.exists() and any(dist_assets.glob("index-*.js"))
    if dist_built:
        return send_from_directory(str(dist_dir), "index.html")
    return (
        "<html><body style='padding:2rem;font-family:monospace;text-align:center'>"
        "<h2>Dashboard not built</h2>"
        "<p>Run: <code>cd web/dashboard && npm run build</code></p>"
        "</body></html>"
    ), 200


for route in _SPA_ROUTES:
    app.add_url_rule(route, f"spa_{route.replace('/', '_')}", _serve_spa)


@app.errorhandler(404)
def not_found(_e):
    return jsonify({"error": "Not found"}), 404


# ═══════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Job Collector Web Dashboard")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host")
    parser.add_argument("--port", type=int, default=5000, help="Bind port")
    parser.add_argument("--debug", action="store_true", help="Debug mode")
    args = parser.parse_args()

    # Ensure the DB is initialized
    init_db()

    print(f"\n  Job Collector Dashboard")
    print(f"  http://{args.host}:{args.port}\n")

    app.run(host=args.host, port=args.port, debug=args.debug, threaded=True)


if __name__ == "__main__":
    main()
