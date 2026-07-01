"""
PostgreSQL (Supabase) database setup and helpers for the job pipeline.

Schema:
  jobs (id, source, source_id, title, company, location, url, description,
       salary_range, posted_at, scraped_at, dedup_key)
  classified_jobs (job_id, seniority, role_fit, red_flags, company_score,
                   match_score, reasoning)
  applications (job_id, status, applied_at, cv_path, letter_path, notes)
"""

import logging
import re
import threading
from typing import Optional

from psycopg2 import pool
from psycopg2.extras import RealDictCursor

from data_collection.config import DATABASE_URL
from data_collection.models import JobPosting

logger = logging.getLogger(__name__)


class Row(dict):
    """A dict subclass that also supports positional index access (row[0]).

    This mimics sqlite3.Row behaviour so existing code using both
    ``row["col"]`` and ``row[0]`` continues to work.
    """

    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


# ── Global connection pool ──────────────────────────────────────────────────

_pool: Optional[pool.ThreadedConnectionPool] = None
_pool_lock = threading.Lock()


def _get_pool() -> pool.ThreadedConnectionPool:
    """Create or return the global connection pool (thread-safe)."""
    global _pool
    if _pool is not None:
        return _pool

    with _pool_lock:
        if _pool is not None:
            return _pool
        if not DATABASE_URL:
            raise RuntimeError(
                "DATABASE_URL is not set. Copy .env.template to .env and fill in "
                "your Supabase PostgreSQL credentials."
            )
        _pool = pool.ThreadedConnectionPool(
            minconn=2,
            maxconn=20,
            dsn=DATABASE_URL,
            cursor_factory=RealDictCursor,
        )
        logger.info("Database pool created (min=2, max=20)")
        return _pool


class DatabaseConnection:
    """Thin wrapper around a psycopg2 connection that mimics sqlite3.Connection.

    Features:
      - Auto-converts SQLite-style ``?`` placeholders to psycopg2 ``%s``.
      - RealDictCursor ensures rows are dict-accessible: ``row["col"]``.
      - ``fetchone()`` / ``fetchall()`` / ``commit()`` / ``close()``
      - ``close()`` returns the connection to the pool instead of closing it.
      - ``executescript()`` splits multi-statement SQL and runs each.
    """

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def __init__(self, conn):
        self._conn = conn
        self._cur = conn.cursor()
        self._lastrowid: Optional[int] = None

    def execute(self, sql: str, params=None):
        """Execute SQL, automatically converting ? → %s placeholders."""
        # Convert SQLite-style ? placeholders to psycopg2 %s
        sql = sql.replace("?", "%s")
        if params is None:
            self._cur.execute(sql)
        elif isinstance(params, (list, tuple)):
            self._cur.execute(sql, params)
        else:
            self._cur.execute(sql, (params,))
        return self

    def executescript(self, sql: str):
        """Execute multi-statement DDL (e.g. for schema creation)."""
        for statement in _split_sql_statements(sql):
            if statement.strip():
                self._cur.execute(statement)
        return self

    def __iter__(self):
        """Iterate over rows from the last executed query as Row dicts."""
        return self

    def __next__(self):
        """Return the next row as a Row (dict subclass), or raise StopIteration."""
        row = self._cur.fetchone()
        if row is None:
            raise StopIteration
        return Row(row)

    def fetchone(self):
        """Fetch next row as a Row (dict subclass, or None)."""
        row = self._cur.fetchone()
        return Row(row) if row else None

    def fetchall(self):
        """Fetch all remaining rows as a list of Rows (dict subclass)."""
        return [Row(row) for row in self._cur.fetchall()]

    def commit(self):
        """Commit the current transaction."""
        self._conn.commit()

    def rollback(self):
        """Rollback the current transaction."""
        self._conn.rollback()

    def ping(self) -> bool:
        """Check if the connection is alive by executing a lightweight query.

        Returns True if the connection is healthy, False otherwise.
        """
        try:
            self._cur.execute("SELECT 1")
            self._cur.fetchone()
            return True
        except Exception:
            return False

    def close(self):
        """Return the connection to the pool."""
        try:
            self._cur.close()
        except Exception:
            pass
        try:
            _get_pool().putconn(self._conn)
        except Exception:
            pass


def _split_sql_statements(sql: str) -> list[str]:
    """Split multi-statement SQL on semicolons, preserving string literals and
    PostgreSQL dollar-quoted blocks ($$ ... $$)."""
    statements = []
    current = []
    in_string = False
    string_char = None
    in_dollar = False
    dollar_tag = ""
    i = 0
    while i < len(sql):
        ch = sql[i]

        # Handle dollar-quoted blocks: $tag$ ... $tag$
        if not in_string and ch == "$":
            # Look ahead: is this a dollar quote start?
            j = i + 1
            while j < len(sql) and sql[j] != "$":
                j += 1
            if j < len(sql) and sql[j] == "$":
                # Found $...$ pattern
                tag = sql[i:j + 1]
                if not in_dollar:
                    # Start of dollar-quoted block
                    in_dollar = True
                    dollar_tag = tag
                    current.append(tag)
                    i = j + 1
                    continue
                elif tag == dollar_tag:
                    # End of dollar-quoted block
                    in_dollar = False
                    dollar_tag = ""
                    current.append(tag)
                    i = j + 1
                    continue
                # else: $ inside dollar block but not matching — keep as is

        if in_dollar:
            current.append(ch)
            i += 1
            continue

        if in_string:
            current.append(ch)
            if ch == string_char:
                # Check for escaped quote ''
                if i + 1 < len(sql) and sql[i + 1] == string_char:
                    current.append(sql[i + 1])
                    i += 1
                else:
                    in_string = False
        elif ch == "'":
            in_string = True
            string_char = "'"
            current.append(ch)
        elif ch == ";":
            statements.append("".join(current))
            current = []
        else:
            current.append(ch)
        i += 1

    remainder = "".join(current).strip()
    if remainder:
        statements.append(remainder)
    return statements


def get_connection() -> DatabaseConnection:
    """Get a database connection from the connection pool."""
    conn = _get_pool().getconn()
    return DatabaseConnection(conn)


def check_pool_health() -> dict:
    """Validate the connection pool is healthy.

    Acquires a test connection, pings it, and returns it to the pool.
    Returns a dict with status and diagnostics suitable for a health-check endpoint.
    """
    result = {
        "healthy": False,
        "pool_initialized": _pool is not None,
        "ping_ms": None,
        "error": None,
    }
    if _pool is None:
        result["error"] = "Connection pool not initialized"
        return result

    try:
        conn = get_connection()
        try:
            start = __import__("time").monotonic()
            alive = conn.ping()
            elapsed = __import__("time").monotonic() - start
            result["healthy"] = alive
            result["ping_ms"] = round(elapsed * 1000, 2)
            if not alive:
                result["error"] = "Ping returned False"
        finally:
            conn.close()
    except Exception:
        logger.exception("Database health check failed")
        result["error"] = "Database health check failed"

    return result


def get_pool_stats() -> dict:
    """Return connection pool statistics for monitoring.

    Returns a dict with minconn, maxconn, and whether the pool is initialized.
    Note: psycopg2 ThreadedConnectionPool does not expose used/idle counts.
    """
    if _pool is None:
        return {"initialized": False, "minconn": None, "maxconn": None}
    return {
        "initialized": True,
        "minconn": _pool.minconn,
        "maxconn": _pool.maxconn,
    }


def normalize_location(location: str) -> str:
    """Normalize location strings to canonical forms.

    Handles whitespace, casing, and variant names for Indian cities:
      - Bengaluru/Bangalore variants → "Bengaluru, India"
      - Mumbai/Bombay variants      → "Mumbai, India"
      - Gurugram/Gurgaon variants   → "Gurugram, India"
      - Noida variants              → "Noida, India"
      - Hyderabad variants          → "Hyderabad, India"
      - Chennai/Madras variants     → "Chennai, India"
      - Pune variants               → "Pune, India"
      - Kolkata/Calcutta variants   → "Kolkata, India"
      - Delhi variants              → "Delhi, India"

    Multi-city locations (e.g. "Bengaluru, Mumbai, Chennai") get the first
    city normalized; the rest are preserved.
    """
    if not location:
        return location

    loc = location.strip()
    loc_lower = loc.lower()

    # ── City alias maps ──────────────────────────────────────────────
    # Each key is a set of substrings; the value is the canonical city.
    # The longest match wins (checked in order).
    _CITY_ALIASES: list[tuple[str, list[str]]] = [
        ("Bengaluru, India", [
            "bengaluru/bangalore", "bangalore/bengaluru",
            "bengaluru (bangalore)", "bangalore (bengaluru)",
            "bangalore, india", "bangalore, india office",
            "bangalore, karnataka", "office - bangalore, india",
            "office - india (bangalore", "india, bangalore",
            "india - bangalore", "hybrid - bangalore",
            "apac - india, hybrid - bangalore",
            "bangalore - ec", "bangalore - wf", "bangalore - blr",
            "bengaluru-vtp", "bengaluru, hybrid",
            "ind - bengaluru", "bengaluru-blr",
            "bengaluru, karnataka",
            "bangalore", "bengaluru",
        ]),
        ("Mumbai, India", [
            "mumbai, india", "office - india (mumbai",
            "bombay", "mumbai, maharashtra",
            "india - mumbai", "mumbai-lower parel",
            "mumbai-owc", "mumbai (remote friendly)",
            "mumbai",  # bare city name
        ]),
        ("Gurugram, India", [
            "gurugram, india", "gurgaon, india",
            "gurgaon, haryana", "gurugram, haryana",
            "office - india (gurgaon", "office - india (gurugram",
            "gurgaon", "gurugram",  # bare city names
        ]),
        ("Noida, India", [
            "noida, uttar pradesh", "noida, up",
            "noida, india", "office - india (noida",
            "noida",  # bare city name
        ]),
        ("Hyderabad, India", [
            "hyderabad, india", "hyderabad, telangana",
            "office - india (hyderabad", "india - hyderabad",
            "hyderabad, in", "hyderabad",  # bare city name
        ]),
        ("Chennai, India", [
            "chennai, india", "chennai, tamil nadu",
            "madras", "office - india (chennai",
            "chennai",  # bare city name
        ]),
        ("Pune, India", [
            "pune, india", "pune, maharashtra",
            "office - india (pune",
            "pune",  # bare city name
        ]),
        ("Kolkata, India", [
            "kolkata, india", "calcutta", "kolkata, west bengal",
            "kolkata",  # bare city name
        ]),
        ("Delhi, India", [
            "new delhi", "delhi, india", "delhi ncr",
            "delhi-ncr", "delhi ncr, india",
            "delhi",  # bare city name
        ]),
    ]

    # ── Try multi-city splitting ─────────────────────────────────────
    # Locations like "Bengaluru, Mumbai, Chennai" or
    # "Office - Bangalore, India, Office - Mohali, India"
    # should normalize the first recognizable city.
    # But if the whole string matches a single alias, do that first.
    for canonical, aliases in _CITY_ALIASES:
        for alias in aliases:
            if alias in loc_lower:
                # Verify it's not a false-positive substring from another city
                # by checking the alias is reasonably specific
                return canonical

    # ── Strip trailing comma-only whitespace artifacts ────────────────
    loc = loc.rstrip(",").strip()
    # Collapse multiple spaces
    loc = " ".join(loc.split())

    return loc


def is_india_location(location: str) -> bool:
    """Detect if a location string refers to an Indian location.

    Uses word-boundary matching for 'india' to avoid false positives from
    'Indonesia', 'Indianapolis', etc.  City names are substring-matched
    (they are unambiguous).
    """
    if not location:
        return False

    location_lower = location.lower()

    # Indian cities (major tech hubs) — substring match is safe for these
    indian_cities = [
        "bangalore", "bengaluru", "hyderabad", "pune", "chennai", "mumbai",
        "delhi", "gurgaon", "gurugram", "noida", "kolkata", "ahmedabad",
        "jaipur", "lucknow", "nagpur", "indore", "bhopal", "visakhapatnam",
        "kochi", "cochin", "trivandrum", "thiruvananthapuram", "coimbatore",
        "mysore", "mysuru", "hubli", "madurai", "patna", "vadodara",
        "surat", "rajkot", "rajahmundry", "vijayawada", "warangal",
        "chandigarh", "udaipur", "jodhpur",
    ]

    for city in indian_cities:
        if city in location_lower:
            return True

    # Country: match 'india' as a whole word via regex, then exclude
    # known false-positive superstrings (Indonesia, Indianapolis, etc.)
    if re.search(r'\bindia\b', location_lower):
        # Reject if it's actually "indonesia" or "indianapolis"
        if "indonesia" in location_lower or "indianapolis" in location_lower:
            return False
        return True

    return False


_db_initialized: bool = False
_db_init_lock = threading.Lock()


def ensure_db() -> None:
    """Call init_db() once per process lifetime. Safe to call from any thread."""
    global _db_initialized
    if _db_initialized:
        return
    with _db_init_lock:
        if _db_initialized:
            return
        init_db()
        _db_initialized = True


def init_db(conn=None) -> None:
    """Create tables if they do not exist (PostgreSQL syntax).

    Prefer calling ensure_db() instead — it gates redundant calls behind a
    process-level flag.  Call init_db() directly only when you need a fresh
    connection to ensure the schema (e.g. from the CLI entry points).
    """
    close = conn is None
    conn = conn or get_connection()

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS jobs (
            id          SERIAL PRIMARY KEY,
            source      TEXT NOT NULL,
            source_id   TEXT NOT NULL,
            title       TEXT NOT NULL,
            company     TEXT NOT NULL,
            location    TEXT NOT NULL DEFAULT '',
            url         TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            salary_range TEXT,
            posted_at   TEXT,
            scraped_at  TEXT NOT NULL,
            dedup_key   TEXT NOT NULL,
            is_india    INTEGER NOT NULL DEFAULT 0,
            embedding   DOUBLE PRECISION[],
            UNIQUE(source, source_id)
        );

        CREATE INDEX IF NOT EXISTS idx_jobs_dedup ON jobs(dedup_key);
        CREATE INDEX IF NOT EXISTS idx_jobs_scraped ON jobs(scraped_at);
        CREATE INDEX IF NOT EXISTS idx_jobs_source ON jobs(source);
        CREATE INDEX IF NOT EXISTS idx_jobs_india ON jobs(is_india);
        CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company);
        CREATE INDEX IF NOT EXISTS idx_jobs_source_scraped ON jobs(source, scraped_at DESC);
        CREATE INDEX IF NOT EXISTS idx_jobs_india_scraped ON jobs(is_india, scraped_at DESC);

        -- Migration: add embedding column (384-dim double precision[]) for semantic matching
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'jobs' AND column_name = 'embedding'
            ) THEN
                ALTER TABLE jobs ADD COLUMN embedding DOUBLE PRECISION[];
            END IF;
        END $$;

        -- Migration: drop old user_id-based unique constraint, create global one.
        -- Use explicit constraint names (DROP IF EXISTS) instead of LIKE patterns
        -- to avoid accidentally matching the new constraint on re-runs.
        DO $$
        BEGIN
            ALTER TABLE jobs DROP CONSTRAINT IF EXISTS jobs_source_source_id_user_id_key;
        EXCEPTION WHEN undefined_table THEN
            -- jobs table does not exist yet (first run)
            NULL;
        END $$;
        DO $$
        BEGIN
            ALTER TABLE jobs ADD CONSTRAINT jobs_source_source_id_key
                UNIQUE (source, source_id);
        EXCEPTION WHEN duplicate_table THEN
            -- constraint already exists
            NULL;
        END $$;

        -- Migration: drop user_id column and its index from legacy schema
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'jobs' AND column_name = 'user_id'
            ) THEN
                ALTER TABLE jobs DROP COLUMN IF EXISTS user_id;
            END IF;
        END $$;

        DROP INDEX IF EXISTS idx_jobs_user;

        CREATE TABLE IF NOT EXISTS classified_jobs (
            id              SERIAL PRIMARY KEY,
            job_id          INTEGER NOT NULL REFERENCES jobs(id),
            seniority       TEXT,
            role_fit        TEXT,
            red_flags       TEXT,
            company_score   INTEGER,
            match_score     INTEGER,
            reasoning       TEXT,
            UNIQUE(job_id)
        );

        CREATE TABLE IF NOT EXISTS heuristic_results (
            job_id        INTEGER PRIMARY KEY REFERENCES jobs(id),
            result        TEXT NOT NULL,
            reason        TEXT NOT NULL,
            classified_at TEXT NOT NULL,
            function_tags TEXT NOT NULL DEFAULT ''
        );

        CREATE INDEX IF NOT EXISTS idx_heuristic_result
        ON heuristic_results(result);

        -- Classified jobs role_fit index — used by stats queries
        CREATE INDEX IF NOT EXISTS idx_classified_role_fit
        ON classified_jobs(role_fit);

        CREATE TABLE IF NOT EXISTS applications (
            id          SERIAL PRIMARY KEY,
            job_id      INTEGER NOT NULL REFERENCES jobs(id),
            status      TEXT NOT NULL DEFAULT 'new',
            applied_at  TEXT,
            cv_path     TEXT,
            letter_path TEXT,
            notes       TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_applications_job ON applications(job_id);

        CREATE TABLE IF NOT EXISTS generated_assets (
            job_id       INTEGER PRIMARY KEY REFERENCES jobs(id),
            cv_path      TEXT,
            letter_path  TEXT,
            generated_at TEXT DEFAULT (NOW()::TEXT)
        );

        CREATE TABLE IF NOT EXISTS candidate_profiles (
            id                      SERIAL PRIMARY KEY,
            user_id                 UUID,
            name                    TEXT NOT NULL,
            email                   TEXT,
            phone                   TEXT,
            target_roles            TEXT NOT NULL DEFAULT '[]',
            skills                  TEXT NOT NULL DEFAULT '[]',
            experience_level        TEXT NOT NULL DEFAULT 'MID',
            experience_years_min    INTEGER NOT NULL DEFAULT 0,
            experience_years_max    INTEGER NOT NULL DEFAULT 15,
            work_types              TEXT NOT NULL DEFAULT '[]',
            remote_preference       TEXT NOT NULL DEFAULT 'ANY',
            preferred_locations     TEXT NOT NULL DEFAULT '[]',
            min_salary              INTEGER,
            salary_currency         TEXT DEFAULT 'USD',
            preferred_industries    TEXT NOT NULL DEFAULT '[]',
            include_keywords        TEXT NOT NULL DEFAULT '[]',
            exclude_keywords        TEXT NOT NULL DEFAULT '[]',
            preferred_sources       TEXT NOT NULL DEFAULT '[]',
            education_level         TEXT NOT NULL DEFAULT 'ANY',
            visa_sponsorship_needed INTEGER NOT NULL DEFAULT 0,
            company_size_preference TEXT NOT NULL DEFAULT 'ANY',
            job_title_aliases       TEXT NOT NULL DEFAULT '[]',
            minimum_match_score     INTEGER NOT NULL DEFAULT 50,
            notes                   TEXT NOT NULL DEFAULT '',
            active                  INTEGER NOT NULL DEFAULT 1,
            created_at              TEXT NOT NULL DEFAULT (NOW()::TEXT),
            updated_at              TEXT NOT NULL DEFAULT (NOW()::TEXT)
        );

        CREATE INDEX IF NOT EXISTS idx_candidate_profiles_user
            ON candidate_profiles(user_id);

        -- Add weight columns if they don't exist (migration-safe)
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'candidate_profiles' AND column_name = 'weight_title'
            ) THEN
                ALTER TABLE candidate_profiles
                    ADD COLUMN weight_title DOUBLE PRECISION NOT NULL DEFAULT 0.30,
                    ADD COLUMN weight_skills DOUBLE PRECISION NOT NULL DEFAULT 0.30,
                    ADD COLUMN weight_location DOUBLE PRECISION NOT NULL DEFAULT 0.20,
                    ADD COLUMN weight_seniority DOUBLE PRECISION NOT NULL DEFAULT 0.10,
                    ADD COLUMN weight_salary DOUBLE PRECISION NOT NULL DEFAULT 0.05,
                    ADD COLUMN weight_work_type DOUBLE PRECISION NOT NULL DEFAULT 0.05;
            END IF;
        END $$;

        CREATE TABLE IF NOT EXISTS profile_job_matches (
            profile_id              INTEGER NOT NULL REFERENCES candidate_profiles(id),
            job_id                  INTEGER NOT NULL REFERENCES jobs(id),
            score                   REAL NOT NULL DEFAULT 0,
            match_reasons           TEXT NOT NULL DEFAULT '[]',
            viewed                  INTEGER NOT NULL DEFAULT 0,
            dismissed               INTEGER NOT NULL DEFAULT 0,
            created_at              TEXT NOT NULL DEFAULT (NOW()::TEXT),
            PRIMARY KEY (profile_id, job_id)
        );

        CREATE INDEX IF NOT EXISTS idx_profile_matches_profile
            ON profile_job_matches(profile_id);
        CREATE INDEX IF NOT EXISTS idx_profile_matches_job
            ON profile_job_matches(job_id);
        CREATE INDEX IF NOT EXISTS idx_profile_matches_score
            ON profile_job_matches(profile_id, score DESC);
        CREATE INDEX IF NOT EXISTS idx_profile_matches_dismissed
            ON profile_job_matches(profile_id, dismissed)
            WHERE dismissed = 1;

        CREATE TABLE IF NOT EXISTS run_history (
            id             SERIAL PRIMARY KEY,
            run_date       TEXT NOT NULL,
            total_jobs     INTEGER NOT NULL,
            unique_jobs    INTEGER NOT NULL,
            india_jobs     INTEGER NOT NULL,
            gh_jobs        INTEGER NOT NULL DEFAULT 0,
            workday_jobs   INTEGER NOT NULL DEFAULT 0,
            lever_jobs     INTEGER NOT NULL DEFAULT 0,
            cutshort_jobs  INTEGER NOT NULL DEFAULT 0,
            remotive_jobs  INTEGER NOT NULL DEFAULT 0,
            remoteok_jobs  INTEGER NOT NULL DEFAULT 0,
            arbeitnow_jobs INTEGER NOT NULL DEFAULT 0,
            himalayas_jobs INTEGER NOT NULL DEFAULT 0,
            linkedin_jobs  INTEGER NOT NULL DEFAULT 0,
            run_time_s     REAL NOT NULL DEFAULT 0,
            notes          TEXT DEFAULT ''
        );
    """)

    conn.commit()
    if close:
        conn.close()


def insert_run_history(conn, stats: dict) -> None:
    """Insert a run history row."""
    conn.execute("""
        INSERT INTO run_history (
            run_date, total_jobs, unique_jobs, india_jobs,
            gh_jobs, workday_jobs, lever_jobs, cutshort_jobs,
            remotive_jobs, remoteok_jobs, arbeitnow_jobs, himalayas_jobs,
            linkedin_jobs, run_time_s, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        stats.get("run_date", ""),
        stats.get("total_jobs", 0),
        stats.get("unique_jobs", 0),
        stats.get("india_jobs", 0),
        stats.get("gh_jobs", 0),
        stats.get("workday_jobs", 0),
        stats.get("lever_jobs", 0),
        stats.get("cutshort_jobs", 0),
        stats.get("remotive_jobs", 0),
        stats.get("remoteok_jobs", 0),
        stats.get("arbeitnow_jobs", 0),
        stats.get("himalayas_jobs", 0),
        stats.get("linkedin_jobs", 0),
        stats.get("run_time_s", 0),
        stats.get("notes", ""),
    ))
    conn.commit()


def insert_job(conn, job: JobPosting) -> int | None:
    """Insert a job posting into the global pool. Returns the row id (existing or new).

    Uses ON CONFLICT (source, source_id) DO NOTHING — deduplicates globally.
    All users share the same job pool; personalization happens in profile_job_matches.

    Also applies quality reject filters (non-engineering roles, staffing agencies)
    and computes a semantic embedding for the job if not already present.
    Caller is responsible for conn.commit().
    """
    # ── Quality reject filter ──
    # Skip clearly non-engineering jobs and staffing agencies.
    # These are quality gates, not profile-specific filters.
    from normalize.dedup import is_reject_job
    if is_reject_job(job.title, job.company):
        logger.debug("Reject filter skipped: %s @ %s", job.title, job.company)
        return None

    norm_location = normalize_location(job.location)
    india_flag = 1 if is_india_location(norm_location) else 0

    # Compute embedding for semantic matching (Level 1 personalization)
    from data_collection.embedding import embed_job
    embedding = None
    try:
        embedding = embed_job(job.title, job.company, norm_location, job.description or "")
    except Exception:
        logger.debug("Failed to compute embedding for job: %s at %s", job.title, job.company)

    row = conn.execute(
        """
        INSERT INTO jobs (source, source_id, title, company, location, url,
                          description, salary_range, posted_at, scraped_at,
                          dedup_key, is_india, embedding)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (source, source_id) DO NOTHING
        RETURNING id
        """,
        (
            job.source.value,
            job.source_id,
            job.title,
            job.company,
            norm_location,
            job.url,
            job.description,
            job.salary_range,
            job.posted_at.isoformat() if job.posted_at else None,
            job.scraped_at.isoformat(),
            job.dedup_key,
            india_flag,
            embedding,
        ),
    ).fetchone()
    return row["id"] if row else None


def update_job_embedding(conn, job_id: int, embedding: list[float]) -> None:
    """Store an embedding vector for a job row.

    Args:
        conn: Database connection.
        job_id: The jobs.id primary key.
        embedding: A list of floats (e.g., 384-dim from paraphrase-MiniLM-L3-v2).
            Passed as a Python list — psycopg2 auto-converts to PostgreSQL ARRAY.
    """
    conn.execute(
        "UPDATE jobs SET embedding = ? WHERE id = ?",
        (embedding, job_id),
    )


def get_jobs_without_embeddings(conn, limit: int = 1000) -> list[dict]:
    """Return jobs that have no embedding yet."""
    rows = conn.execute(
        """SELECT id, title, company, location, description
           FROM jobs WHERE embedding IS NULL
           ORDER BY id LIMIT ?""",
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def persist_jobs(jobs: list) -> tuple[int, int]:
    """Write jobs to the database. Returns (inserted, existing).

    Opens its own connection and commits. This is the single shared
    implementation used by both the sync and async orchestrators.
    """
    if not jobs:
        return 0, 0

    conn = get_connection()
    init_db(conn)
    inserted = 0
    existing = 0

    for job in jobs:
        try:
            rid = insert_job(conn, job)
            if rid is not None:
                inserted += 1
            else:
                existing += 1
        except Exception:
            logger.exception("Failed inserting job: %s", job.title[:60])

    conn.commit()
    conn.close()
    return inserted, existing
