# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

## Project Overview

Job collection and normalization pipeline — **Stage 1 (collection) + Stage 2 (normalization/dedup)**. Collects from 9+ sources, normalizes to a shared schema, deduplicates, and stores in PostgreSQL (Supabase). Features a Flask web backend with React dashboard, Supabase Auth (JWT), and user-scoped candidate profiles with job matching.

## Architecture

```
data_collection/           — core collection pipeline
  config.py                — paths, env vars (Supabase, database URL)
  database.py              — PostgreSQL schema, connection pool, insert_job, init_db, normalize_location(), is_india_location()
  models.py                — Pydantic JobPosting model (shared contract between all collectors)
  embedding.py             — Semantic embedding model (paraphrase-MiniLM-L3-v2, 384-dim, 17MB), embed_job(), embed_profile(), cosine_similarity()
  auth.py                  — Supabase JWT auth for Flask (require_auth, optional_auth decorators)
  user_profile.py          — Candidate profile model, CRUD, job scoring/matching engine (Level 1 embedding-based)
  run_all.py               — sync orchestrator (sequential, legacy; defines persist_jobs)
  run_all_async.py         — async orchestrator (concurrent, ~17x faster, primary; defines persist_jobs)
  collectors/
    base.py                — BaseCollector + AsyncBaseCollector ABCs
    greenhouse.py          — Greenhouse ATS API (sync, reference impl)
    greenhouse_async.py    — Async Greenhouse (primary, ~16K jobs from 229+ slugs)
    lever.py               — Lever API (sync)
    lever_async.py         — Async Lever (primary, ~1.6K jobs from 31+ slugs)
    workday.py             — Workday internal API (~800 jobs, 11 tenants)
    cutshort.py            — Async sitemap + JSON-LD scraper (India-focused, rate-limited)
    yc_jobs.py             — HN "Who is hiring?" via Algolia API (~1.4K jobs)
    remoteok.py            — RemoteOK REST API
    remotive.py            — Remotive REST API (sync)
    remotive_async.py      — Async Remotive (primary)
    arbeitnow.py           — Arbeitnow REST API (EU/Germany-focused)
    himalayas.py           — Himalayas REST API (remote, salary data)
    linkedin.py            — LinkedIn guest jobs API (~150+ jobs, India-focused queries)
    adzuna.py              — Adzuna API (needs APP_ID + API_KEY)
    jsearch.py             — JSearch RapidAPI (needs RAPIDAPI_KEY)
    slug_discovery.py      — Greenhouse/Lever slug discovery helper
    bulk_discover.py       — Bulk slug discovery
    wellfound.py           — (dead: 403 Cloudflare)
    iimjobs.py             — (dead: Next.js SPA, no public API)

normalize/                 — dedup and CLI dashboard
  dedup.py                 — exact + fuzzy dedup, reject filter, stats
  cli.py                   — CLI dashboard (stats, list, search, export, classify)
  benchmark.py             — dedup performance benchmarks

web/                       — Flask backend + React frontend
  app.py                   — Flask API server, SSE-based run progress, Supabase auth integration
  dashboard/               — React + TypeScript SPA (Vite + Tailwind CSS)
    src/pages/             — DashboardPage, ProfilePage, JobsPage, HistoryPage, LoginPage
    src/components/        — StatCard, SourceBreakdown, PipelineControls, TopCompanies,
                             SparkChart, RecentActivity, SourceGlowGrid, SourceStatusTicker,
                             NavHeader, ErrorBoundary, ProtectedRoute, Skeleton, PageTransition
    src/lib/               — api.ts, AuthContext.tsx, supabase.ts, ToastContext.tsx, utils.ts, sourceMeta.ts
    start.sh               — Vite dev server launcher
    package.json, vite.config.ts, tailwind.config.js, tsconfig.json
  templates/               — Jinja2 fallback (dashboard_react.html)
  static/dist/             — Vite build output (gitignored)

scripts/                   — utility scripts
  backfill_embeddings.py   — one-time embedding backfill for existing jobs

PERSONALIZATION.md          — architecture plan: 7-level personalization roadmap

start.sh                   — top-level convenience: launches web backend + frontend
```

## Key Design Decisions

- **All collectors produce the same schema** (`JobPosting` pydantic model) — normalization is automatic
- **No Selenium anywhere** — Playwright only for Workday; prefer direct API discovery
- **PostgreSQL via Supabase** for zero-infra hosted DB — connection pool (2-20, psycopg2 ThreadedConnectionPool), RealDictCursor
- **Async collectors** for concurrent execution — ~17x faster than sequential
- **Fuzzy dedup** with normalized title+company+location as secondary pass
- **Semantic embedding matching (Level 1)** — `paraphrase-MiniLM-L3-v2` (384-dim, 17MB) vectors replace hardcoded synonym/taxonomy maps. Embeddings computed at collection time via `insert_job()`, stored as PostgreSQL `DOUBLE PRECISION[]`. Scoring uses `cosine_similarity(job_embedding, profile_embedding)` for 80% of the match score. Falls back to legacy string-matching when embeddings unavailable.
- **`is_india` column** for fast India-based job filtering
- **Location normalization** — `normalize_location()` runs before insert to consolidate city variants (Bangalore/Bengaluru→ "Bengaluru, India", Mumbai/Bombay→ "Mumbai, India", etc. for 9 major Indian cities)
- **Reject filter** strips non-engineering jobs (driver, cashier, data entry, etc.) and known staffing agencies
- **Supabase Auth** — JWT validation server-side with PyJWT (HS256, no network call needed)
- **User-scoped profiles** — candidate_profiles keyed by Supabase user UUID, with job scoring/matching engine and configurable weights
- **user_id on jobs** — multi-tenant: same job collected by different users gets separate rows via `UNIQUE(source, source_id, user_id)`

## Database Schema

```sql
-- Core job storage (multi-tenant: user_id scoping)
jobs (id SERIAL PK, source, source_id, title, company, location, url, description,
      salary_range, posted_at, scraped_at, dedup_key, is_india, user_id UUID)
      UNIQUE(source, source_id, user_id)

-- AI classification results
classified_jobs (id SERIAL PK, job_id FK→jobs, seniority, role_fit, red_flags, company_score, match_score, reasoning)
heuristic_results (job_id PK FK→jobs, result, reason, classified_at, function_tags)

-- Application tracking
applications (id SERIAL PK, job_id FK→jobs, status, applied_at, cv_path, letter_path, notes)
generated_assets (job_id PK FK→jobs, cv_path, letter_path, generated_at)

-- User-scoped candidate profiles (25+ columns)
candidate_profiles (id SERIAL PK, user_id UUID, name, email, phone,
                    target_roles, skills, experience_level,
                    experience_years_min, experience_years_max,
                    work_types, remote_preference,
                    preferred_locations, min_salary, salary_currency,
                    preferred_industries, education_level,
                    visa_sponsorship_needed, company_size_preference,
                    job_title_aliases, include_keywords, exclude_keywords,
                    preferred_sources, minimum_match_score, notes,
                    weight_title, weight_skills, weight_location,
                    weight_seniority, weight_salary, weight_work_type,
                    active, created_at, updated_at)

-- Profile-to-job match scores
profile_job_matches (profile_id FK, job_id FK, score, match_reasons, viewed, dismissed, created_at)

-- Run metadata
run_history (id SERIAL PK, run_date, total_jobs, unique_jobs, india_jobs,
             gh_jobs, workday_jobs, lever_jobs, cutshort_jobs,
             remotive_jobs, remoteok_jobs, arbeitnow_jobs, himalayas_jobs,
             linkedin_jobs, run_time_s, notes)
```

## Common Commands

### Setup

```bash
pip install -e .                   # editable install
cp .env.template .env              # fill in API keys for Adzuna/JSearch
playwright install                 # browsers for Workday scraper
```

### Run collection

```bash
python -m data_collection.run_all_async                   # all no-auth sources concurrently
python -m data_collection.run_all_async --with-browser    # + Workday (sequential)
python -m data_collection.run_all_async --cutshort-limit 500   # cap Cutshort
python -m data_collection.run_all                         # sync (legacy)
python -m data_collection.run_all --all                   # sync, everything incl. keys
```

### View & analyze data

```bash
python -m normalize.cli                                   # stats dashboard
python -m normalize.cli list                              # recent 20 jobs
python -m normalize.cli list --source greenhouse          # filter by source
python -m normalize.cli list --company stripe             # filter by company
python -m normalize.cli list --location india             # India-only jobs
python -m normalize.cli list --rating STRONG              # AI-classified roles
python -m normalize.cli search "machine learning"         # search titles/descriptions
python -m normalize.cli export                            # export all jobs to JSON
python -m normalize.cli history                           # run history
```

### AI classification

```bash
python -m normalize.cli classify                          # both heuristic + AI passes
python -m normalize.cli classify --pass1-only             # heuristic only (free)
python -m normalize.cli classify --stats                  # classification breakdown
python -m normalize.cli classify --limit 100              # test on 100 jobs
python -m normalize.cli classify --dry-run --limit 20     # preview without saving
```

### Web dashboard

```bash
python -m web.app                                         # http://127.0.0.1:5000
python -m web.app --port 8080 --host 0.0.0.0             # bind all interfaces
```

### Code quality

```bash
ruff check .                                              # lint
pytest                                                    # run tests (see pyproject.toml for config)
```

## Collector Architecture

All collectors follow the same pattern:

```python
from data_collection.collectors.base import AsyncBaseCollector
from data_collection.models import JobPosting, JobSource

class MyCollector(AsyncBaseCollector):
    source_name = JobSource.MY_SOURCE.value

    async def collect(self) -> Sequence[JobPosting]:
        # fetch, parse, yield JobPosting instances
        ...
```

- **Sync collectors** inherit `BaseCollector` and implement `collect()` (sync)
- **Async collectors** inherit `AsyncBaseCollector` and implement `async collect()`
- The orchestrator (`run_all_async.py`) runs async collectors concurrently via `asyncio.gather`
- `persist_jobs()` (defined in both `run_all.py` and `run_all_async.py`) writes to PostgreSQL via `insert_job()`, skipping duplicates by `(source, source_id, user_id)` ON CONFLICT DO NOTHING

## Working Collectors

| Source | Method | Avg Jobs | Notes |
| --- | --- | --- | --- |
| **Greenhouse** | Direct API (no auth) | ~16,000 | 229+ slugs. Stripe, Airbnb, Figma, Notion, Linear, Indian unicorns |
| **YC Jobs** | HN Algolia API (no auth) | ~1,426 | "Who is hiring?" threads, 3 months rolling |
| **Lever** | Direct API (no auth) | ~1,674 | 31+ slugs. CRED, Meesho, Paytm, Spotify, Fi Money |
| **Workday** | Internal API | ~800 | 11 tenants: Adobe, Nvidia, Salesforce, Intel, etc. |
| **Cutshort** | Sitemap + JSON-LD | ~150+ | India-focused, rate-limited |
| **LinkedIn** | Guest jobs API (no auth) | ~150+ | 17 keyword+location combos, India-focused |
| **RemoteOK** | REST API (no auth) | ~100 | Remote-focused, free JSON API |
| **Arbeitnow** | REST API (no auth) | ~100 | EU/Germany-focused, free |
| **Remotive** | REST API (no auth) | ~60 | Remote-focused, no auth needed |
| **Himalayas** | REST API (no auth) | ~20 | Remote, salary data, free |

## Dead / Blocked Sources

| Source | Reason |
| --- | --- |
| **Indeed RSS** | 404 — endpoint dead |
| **Wellfound (AngelList)** | 403 — Cloudflare blocks |
| **Hirist** | 404 — endpoint dead |
| **Instahyre** | 403 — Cloudflare blocks |
| **iimjobs** | Next.js SPA, no public API |
| **Naukri** | 406 "recaptcha required" |
| **TCS, Infosys, Cognizant, Wipro** | 403 — Indian IT portals block |
| **Adzuna** | Needs API key (free tier: 250 req/day) |
| **JSearch** | Needs RapidAPI key |
