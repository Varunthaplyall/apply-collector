# Project Improvements

**Started**: 2026-06-30
**Last session**: 2026-06-30 (3 commits)
**Approach**: Full-stack parallel, frontend-first via iterative refinement

## Session 1 Summary — 2026-06-30

### Commits on `master` (ahead of origin by 5)

```
870baa0 fix: Remotive async parity, JSearch source label, database context manager
b551c6a feat: MainPage redesign — unified SPA with Dashboard + Jobs tabs
6b6152a feat: frontend modernization Phase 1 — design tokens, UI component library, TanStack Query
```

### What Got Done

**Frontend:**
- Installed `@tanstack/react-query`, `@tanstack/react-virtual`
- Design tokens: CSS custom properties in `index.css` (palette, spacing, typography, radii, shadows)
- UI component library in `src/components/ui/`: Button (6 variants x 4 sizes + loading), Card (header/title/desc/content/footer compound), Input (label/error/hint/icon slots), Badge (5 colors x 2 sizes), EmptyState, ErrorState, Dialog (focus trap, escape-close, keyboard nav), Tabs (animated spring indicator)
- Updated Skeleton: removed Framer Motion dependency, respects `prefers-reduced-motion`
- TanStack Query provider in `App.tsx`, 7 query hooks + 5 mutations in `src/lib/queries.ts`
- `fetchJobs` accepts `AbortSignal` for request cancellation
- `ToastType` exported from `ToastContext.tsx`
- **MainPage redesigned**: Dashboard tab (4 stat cards, pipeline controls, source breakdown, spark chart, top companies, recent activity, India locations grid) + Jobs tab (filter bar with 300ms debounced search, source/location/India/sort selectors, always-visible job card actions). Settings drawer extracted to `SettingsDrawer.tsx`.
- **Removed 4 dead page components**: `DashboardPage.tsx`, `JobsPage.tsx`, `ProfilePage.tsx`, `HistoryPage.tsx`
- Build: TypeScript clean, Vite ~181KB gzipped (615KB JS + 53KB CSS)

**Backend:**
- Removed dead collectors: `wellfound.py`, `iimjobs.py`
- Removed unused dependencies from `pyproject.toml`: `pgvector`, `feedparser`
- Removed wellfound/iimjobs references from `web/app.py` `_PIPELINE_EXTRA_SOURCES`
- **Remotive async collector fixed**: Now matches sync version (6 categories x up to 3 pages, concurrent via `asyncio.gather`). Previously did a single uncategorized API call
- **JSearch source label fixed**: Was `JobSource.LINKEDIN` - now correctly `JobSource.JSEARCH`
- Added `JSEARCH`, `WELLFOUND`, `IIMJOBS` to `JobSource` enum in `models.py`
- **Database context manager**: `DatabaseConnection` now supports `with get_connection() as conn:`
- **Security**: Redacted production database password from `.env.template`

### Files Changed

```
New:
  web/dashboard/src/components/ui/Button.tsx
  web/dashboard/src/components/ui/Card.tsx
  web/dashboard/src/components/ui/Input.tsx
  web/dashboard/src/components/ui/Badge.tsx
  web/dashboard/src/components/ui/EmptyState.tsx
  web/dashboard/src/components/ui/ErrorState.tsx
  web/dashboard/src/components/ui/Dialog.tsx
  web/dashboard/src/components/ui/Tabs.tsx
  web/dashboard/src/components/ui/index.ts
  web/dashboard/src/components/SettingsDrawer.tsx
  web/dashboard/src/lib/queries.ts
  docs/superpowers/specs/2026-06-30-frontend-modernization-design.md

Modified:
  web/dashboard/src/index.css
  web/dashboard/src/App.tsx
  web/dashboard/src/components/Skeleton.tsx
  web/dashboard/src/lib/api.ts
  web/dashboard/src/lib/ToastContext.tsx
  web/dashboard/src/pages/MainPage.tsx
  web/dashboard/package.json
  data_collection/models.py
  data_collection/collectors/remotive_async.py
  data_collection/collectors/jsearch.py
  data_collection/database.py
  pyproject.toml
  web/app.py
  .env.template

Deleted:
  web/dashboard/src/pages/DashboardPage.tsx
  web/dashboard/src/pages/JobsPage.tsx
  web/dashboard/src/pages/ProfilePage.tsx
  web/dashboard/src/pages/HistoryPage.tsx
  data_collection/collectors/wellfound.py
  data_collection/collectors/iimjobs.py
```

---

## CRITICAL: Action Required Immediately

**Rotate the database password.** The password `qGNEnleOKKwfYfri` was in `.env.template` committed to git history. Go to Supabase Dashboard > Project Settings > Database > Reset password. Update your `.env` file afterward.

---

## What's Left

### Priority 1: Security & Reliability

- [ ] **Rotate Supabase database password** (see above)
- [ ] **No test suite** - add pytest for Python, Vitest + React Testing Library for frontend. Zero coverage currently. Start with: `test_database.py` (normalize_location, is_india_location), `test_models.py` (JobPosting validation, dedup_key), `test_collectors/` (mock HTTP responses), `test_api.py` (Flask test client)
- [ ] **No CI/CD** - add `.github/workflows/ci.yml`: ruff lint > mypy type-check > pytest > Vite build
- [ ] **No proper migrations** - `init_db()` uses `DO $$ ... EXCEPTION` blocks. Install Alembic, generate initial migration from current schema, convert ad-hoc blocks to versioned migrations
- [ ] **Database connection pool has no health checks** - add `test_connection()` / `ping()` to `_get_pool()`, or use `psycopg2.extras.wait_select`

### Priority 2: Backend Architecture

- [ ] **Replace thread-based pipeline** - `web/app.py` spawns threads with `asyncio.new_event_loop()`. Replace with proper job queue (Redis + ARQ, or RQ). Benefits: persistence, retries, monitoring, cancellation
- [ ] **Remove sync collector duplicates** - `greenhouse.py` and `lever.py` duplicate parsing logic with their async counterparts. Extract shared `_parse_jobs` into a module or delete sync versions
- [ ] **Standardize collector error handling** - create shared retry/timeout config in base class. Currently inconsistent across collectors
- [ ] **Cutshort dead import**: `from tenacity import retry, ...` on line 24 but never used
- [ ] **LinkedIn sync wrapper bug**: `LinkedInCollector.collect()` calls `asyncio.run(super().collect())` which crashes if event loop is already running
- [ ] **Split `user_profile.py`** (1350 lines) - extract synonym maps, scoring logic, and CRUD into separate modules
- [ ] **Remove feedparser from requirements.txt** - removed from pyproject.toml but still in requirements.txt line 13

### Priority 3: Database

- [ ] **Enable pgvector extension** - currently `embedding` is `DOUBLE PRECISION[]`. Migrate to `vector(384)` for in-database cosine similarity via `<=>` operator. Add IVFFlat or HNSW index
- [ ] **Migrate TEXT timestamps to TIMESTAMPTZ** - across all tables
- [ ] **Normalize `run_history`** - add `run_source_stats(run_id FK, source_name TEXT, job_count INT)` child table. Remove per-source columns from `run_history`
- [ ] **Add pg_trgm indexes** - for `LIKE '%query%'` filters on jobs.company, jobs.title, jobs.location
- [ ] **Keyset pagination** - replace `OFFSET`/`LIMIT` in `api_jobs()` with `WHERE id > ? ORDER BY id LIMIT ?`
- [ ] **Add CHECK constraints** - e.g. `applications.status`, profile weight columns 0.0-1.0

### Priority 4: Frontend Polish

- [ ] **Code splitting** - `React.lazy(() => import('./components/SettingsDrawer'))` for settings panel (~270 lines, rarely opened)
- [ ] **Virtualized job list** - TanStack Virtual is installed but not used. Replace flat `.map()` in JobsTab with `useVirtualizer`
- [ ] **Responsive testing** - test 375px/768px/1440px. Settings drawer should be bottom sheet on mobile. Filter bar should collapse
- [ ] **Respect `prefers-reduced-motion`** - add `motion-safe:`/`motion-reduce:` prefixes to Tailwind animations and Framer Motion components
- [ ] **Better empty states** - first-time user after signup sees empty dashboard. Add onboarding hints
- [ ] **Offline detection** - `navigator.onLine` + banner when disconnected
- [ ] **Error boundary per section** - individual sections (stats, jobs, settings) should fail independently

### Priority 5: Features

- [ ] **Application tracker** - the `applications` table exists but has no UI. Add status pipeline: Saved > Applied > Interviewing > Offer > Rejected
- [ ] **Email alerts** - when new jobs match a profile, send email digest (Resend, SendGrid, or Supabase email)
- [ ] **Job detail panel** - clicking a job card opens slide-in with full description, match reasons, apply/save/dismiss
- [ ] **AI job scoring UI** - surface classifications from `classified_jobs` table in the UI

### Priority 6: Infrastructure

- [ ] **Docker image optimization** - ~400MB currently (includes PyTorch). Consider ONNX runtime or smaller embedding model
- [ ] **Dependency lock file** - `pip freeze > requirements-lock.txt` or switch to Poetry/uv
- [ ] **Sentry / error monitoring** - zero observability. Flask: `sentry-sdk[flask]`. Frontend: `@sentry/react`
- [ ] **Render cold start mitigation** - free tier spins down after 15 min. Add uptime monitor or upgrade tier
- [ ] **Supabase connection pooler** - enable built-in pooler (port 6543) to avoid pool exhaustion

---

## Architecture Notes (for next session)

### Key files to read first
| File | Why |
|------|-----|
| `web/app.py` | Flask routes, pipeline orchestration |
| `data_collection/database.py` | Connection pool, schema, insert_job |
| `data_collection/run_all_async.py` | Collection orchestrator |
| `data_collection/user_profile.py` | Profile model, scoring engine |
| `web/dashboard/src/pages/MainPage.tsx` | New SPA layout |

### Dev commands
```bash
# Frontend (from web/dashboard/)
npm run dev              # Vite dev server on :3000
npx tsc --noEmit         # TypeScript check
npx vite build           # Production build -> ../static/dist/

# Backend (from project root)
python -m web.app                              # Flask on :5000
python -m data_collection.run_all_async         # Collect all sources
python -m normalize.cli                        # Stats dashboard

# Both
./start.sh               # Starts Flask + Vite concurrently

# Code quality
ruff check .             # Python lint
```

### .env setup
```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
DATABASE_URL=postgresql://postgres.your-ref:your-password@db.your-project.supabase.co:5432/postgres
SUPABASE_JWT_SECRET=your-jwt-secret
CRON_SECRET=optional-cron-hmac-secret
```

### Git state
- `master`: 5 commits ahead of `origin/master`
- Working tree: clean, no uncommitted changes

### Design spec
See `docs/superpowers/specs/2026-06-30-frontend-modernization-design.md` for approved frontend architecture decisions.
