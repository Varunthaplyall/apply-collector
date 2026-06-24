# Apply Collector

Job collection and normalization pipeline — **Stage 1 (collection) + Stage 2 (normalization/dedup)**. Collects from 9+ sources, normalizes to a shared schema, deduplicates, and stores in PostgreSQL (Supabase). Features a Flask web backend with React dashboard, Supabase Auth (JWT), and user-scoped candidate profiles with semantic job matching.

## Quick Start

```bash
# Setup
cp .env.template .env          # fill in Supabase URL + anon key
pip install -e .
playwright install             # browsers for Workday scraper

# Collect jobs (async, ~17x faster than sequential)
python -m data_collection.run_all_async
python -m data_collection.run_all_async --with-browser    # + Workday
python -m data_collection.run_all_async --cutshort-limit 500

# View & analyze data
python -m normalize.cli                                    # stats dashboard
python -m normalize.cli list                               # recent 20 jobs
python -m normalize.cli list --source greenhouse            # filter by source
python -m normalize.cli list --company stripe               # filter by company
python -m normalize.cli list --location india               # India-only jobs
python -m normalize.cli search "backend engineer"           # full-text search
python -m normalize.cli export                              # export to JSON

# AI classification
python -m normalize.cli classify                            # heuristic + AI passes
python -m normalize.cli classify --pass1-only               # heuristic only (free)
python -m normalize.cli classify --stats                    # breakdown

# Web dashboard
python -m web.app                                           # http://127.0.0.1:5000
python -m web.app --port 8080 --host 0.0.0.0               # bind all interfaces
```

## Architecture

```
data_collection/           — core collection pipeline
  config.py                — paths, env vars (Supabase, database URL)
  database.py              — PostgreSQL schema, connection pool, insert_job, init_db
  models.py                — Pydantic JobPosting model (shared contract)
  embedding.py             — Semantic embedding model (paraphrase-MiniLM-L3-v2, 384-dim)
  auth.py                  — Supabase JWT auth for Flask
  user_profile.py          — Candidate profile CRUD, job scoring/matching engine
  run_all.py               — sync orchestrator (legacy)
  run_all_async.py         — async orchestrator (primary, concurrent execution)
  collectors/
    base.py                — BaseCollector + AsyncBaseCollector ABCs
    greenhouse_async.py    — Greenhouse ATS API (primary, ~16K jobs, 229+ slugs)
    lever_async.py         — Lever API (primary, ~1.6K jobs, 31+ slugs)
    workday.py             — Workday internal API (~800 jobs, 11 tenants)
    cutshort.py            — Async sitemap + JSON-LD scraper (India-focused)
    yc_jobs.py             — HN "Who is hiring?" via Algolia API (~1.4K jobs)
    remoteok.py            — RemoteOK REST API
    remotive_async.py      — Remotive REST API (primary)
    arbeitnow.py           — Arbeitnow REST API (EU/Germany-focused)
    himalayas.py           — Himalayas REST API (remote, salary data)
    linkedin.py            — LinkedIn guest jobs API (~150+ jobs, India-focused)
    adzuna.py              — Adzuna API (needs APP_ID + API_KEY)
    jsearch.py             — JSearch RapidAPI (needs RAPIDAPI_KEY)
    slug_discovery.py      — Greenhouse/Lever slug discovery
    bulk_discover.py       — Bulk slug discovery

normalize/                 — dedup and CLI dashboard
  dedup.py                 — exact + fuzzy dedup, reject filter, stats
  cli.py                   — CLI dashboard (stats, list, search, export, classify)
  benchmark.py             — dedup performance benchmarks

web/                       — Flask backend + React frontend
  app.py                   — Flask API server, SSE-based run progress, Supabase auth
  dashboard/               — React + TypeScript SPA (Vite + Tailwind CSS)
    src/pages/             — DashboardPage, ProfilePage, JobsPage, HistoryPage, LoginPage
    src/components/        — StatCard, SourceBreakdown, PipelineControls, TopCompanies,
                             SparkChart, RecentActivity, SourceGlowGrid, SourceStatusTicker,
                             NavHeader, ErrorBoundary, ProtectedRoute, Skeleton, PageTransition
    src/lib/               — api.ts, AuthContext.tsx, supabase.ts, ToastContext.tsx, utils.ts, sourceMeta.ts
  templates/               — Jinja2 fallback (dashboard_react.html)

scripts/                   — utility scripts
  backfill_embeddings.py   — one-time embedding backfill for existing jobs
```

## Sources

| Source | Method | Avg Jobs | Auth |
| ------ | ------ | -------- | ---- |
| **Greenhouse** | Direct API | ~16,000 | None — 229+ slugs (Stripe, Airbnb, Figma, Notion, Linear, Indian unicorns) |
| **YC Jobs** | HN Algolia API | ~1,426 | None — "Who is hiring?" threads, 3 months rolling |
| **Lever** | Direct API | ~1,674 | None — 31+ slugs (CRED, Meesho, Paytm, Spotify) |
| **Workday** | Internal API | ~800 | None — 11 tenants (Adobe, Nvidia, Salesforce, Intel) |
| **Cutshort** | Sitemap + JSON-LD | ~150+ | None — India-focused, rate-limited |
| **LinkedIn** | Guest jobs API | ~150+ | None — 17 keyword+location combos, India-focused |
| **RemoteOK** | REST API | ~100 | None — remote-focused |
| **Arbeitnow** | REST API | ~100 | None — EU/Germany-focused |
| **Remotive** | REST API | ~60 | None — remote-focused |
| **Himalayas** | REST API | ~20 | None — remote, salary data |
| **Adzuna** | REST API | — | API key (free tier: 250 req/day) |
| **JSearch** | RapidAPI | — | API key |

### Dead / Blocked Sources

| Source | Reason |
| ------ | ------ |
| Indeed RSS | 404 — endpoint dead |
| Wellfound (AngelList) | 403 — Cloudflare blocks |
| Hirist | 404 — endpoint dead |
| Instahyre | 403 — Cloudflare blocks |
| iimjobs | Next.js SPA, no public API |
| Naukri | 406 "recaptcha required" |
| TCS, Infosys, Cognizant, Wipro | 403 — Indian IT portals block |

## Key Design Decisions

- **All collectors produce the same schema** (`JobPosting` pydantic model) — normalization is automatic
- **Async collectors** for concurrent execution — ~17x faster than sequential
- **PostgreSQL via Supabase** for zero-infra hosted DB — connection pool (2-20, psycopg2 ThreadedConnectionPool)
- **Fuzzy dedup** with normalized title+company+location as secondary pass
- **Reject filter** strips non-engineering jobs (driver, cashier, data entry, etc.) and known staffing agencies
- **Semantic embedding matching (Level 1)** — `paraphrase-MiniLM-L3-v2` (384-dim, 17MB) vectors replace hardcoded synonym/taxonomy maps. Embeddings computed at collection time, stored as PostgreSQL `DOUBLE PRECISION[]`. Scoring uses `cosine_similarity` for 80% of the match score. Falls back to legacy string-matching when embeddings unavailable.
- **`is_india` column** for fast India-based job filtering
- **Location normalization** — consolidates city variants (Bangalore/Bengaluru → "Bengaluru, India", Mumbai/Bombay → "Mumbai, India", etc. for 9 major Indian cities)
- **Supabase Auth** — JWT validation server-side with PyJWT (HS256, no network call needed)
- **User-scoped profiles** — candidate_profiles keyed by Supabase user UUID, with job scoring/matching engine and configurable weights
- **Multi-tenant jobs** — same job collected by different users gets separate rows via `UNIQUE(source, source_id, user_id)`

## Database Schema (Supabase PostgreSQL)

```sql
-- Core job storage (multi-tenant)
jobs (id SERIAL PK, source, source_id, title, company, location, url, description,
      salary_range, posted_at, scraped_at, dedup_key, is_india, user_id UUID)
      UNIQUE(source, source_id, user_id)

-- AI classification
classified_jobs (id SERIAL PK, job_id FK→jobs, seniority, role_fit, red_flags,
                 company_score, match_score, reasoning)
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
profile_job_matches (profile_id FK, job_id FK, score, match_reasons,
                     viewed, dismissed, created_at)

-- Run metadata
run_history (id SERIAL PK, run_date, total_jobs, unique_jobs, india_jobs,
             gh_jobs, workday_jobs, lever_jobs, cutshort_jobs,
             remotive_jobs, remoteok_jobs, arbeitnow_jobs, himalayas_jobs,
             linkedin_jobs, run_time_s, notes)
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
- `persist_jobs()` writes to PostgreSQL via `insert_job()`, skipping duplicates by `ON CONFLICT DO NOTHING`

## Code Quality

```bash
ruff check .                    # lint
pytest                          # run tests
```

## Requirements

- Python >= 3.12
- PostgreSQL (via Supabase)
- Dependencies: httpx, pydantic, beautifulsoup4, lxml, python-dotenv, playwright, psycopg2, sentence-transformers, flask, flask-cors, pyjwt
- Node.js 18+ (for web dashboard)
