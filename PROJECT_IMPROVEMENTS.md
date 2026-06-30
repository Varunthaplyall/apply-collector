# Project Improvements

**Started**: 2026-06-30
**Approach**: Full-stack parallel, frontend-first via iterative refinement

## Current Architecture

- **Backend**: Flask 3.x with sync workers, asyncio.new_event_loop() for collection threads, SSE for pipeline status
- **Frontend**: React 18 SPA (Vite 5, Tailwind CSS 3, Framer Motion), custom fetch-based API layer, URL-driven filters
- **Database**: PostgreSQL via Supabase, psycopg2 ThreadedConnectionPool, 7 tables, ad-hoc DO $$ migrations
- **Infrastructure**: Render (Docker) + Vercel (serverless fallback), cron every 4 hours
- **Collectors**: 9 active sources (3 sync/async pairs), mixed retry/rate-limiting strategies

## Identified Issues

See detailed audits in exploration phase. Key themes:

### Critical
- No tests (zero coverage)
- No proper migration system (DO $$ blocks in init_db())
- .env.template contains live database credentials
- No CI/CD pipeline
- No CSRF protection on auth-bearing endpoints
- Thread-based pipeline with no timeout/cancellation

### High
- Dead frontend pages (DashboardPage, JobsPage, ProfilePage, HistoryPage) not routed
- No state management library (manual fetch in every component)
- No accessibility (hover-only interactions, missing ARIA labels, no focus trap)
- Sync/async collector code duplication
- Hardcoded synonym maps (1350 lines in user_profile.py)
- Remotive async regression (fewer features than sync version)

### Medium
- TEXT timestamps throughout schema (should be TIMESTAMPTZ)
- No pgvector usage despite dependency (embedding stored as DOUBLE PRECISION[])
- run_history table denormalized (per-source columns)
- OFFSET pagination (should be keyset)
- No connection pool health checks
- No request timeouts in frontend API layer

### Low
- Inline embedding computation at insert time
- Multiple deployment targets with different dependency sets
- Dead collector files (wellfound.py, iimjobs.py)
- feedparser dependency unused
- pgvector dependency unused

## Completed Improvements

### 2026-06-30 — Phase 2: MainPage Redesign
- [x] New MainPage layout: Dashboard tab + Jobs tab with TabList navigation
- [x] Dashboard section: stat cards, pipeline controls, source breakdown, spark chart, top companies, recent activity, India locations
- [x] Jobs section: filter bar with debounced search, source/location/India/sort selectors, always-visible job card actions
- [x] Settings drawer: slide-over panel with target roles, locations, skills, experience/salary sliders, work types, exclude keywords
- [x] Job cards: always-visible actions (not hover-revealed), proper ARIA labels, score badge, inline badges for India/strong match
- [x] Removed 4 dead page components (DashboardPage, JobsPage, ProfilePage, HistoryPage)
- [x] Exported ToastType from ToastContext for type-safe usage
- [x] TypeScript compiles clean, Vite build: 615KB JS + 53KB CSS (181KB gzipped)

### 2026-06-30 — Phase 1: Frontend Foundation
- [x] Installed @tanstack/react-query, @tanstack/react-virtual
- [x] Design tokens in index.css (semantic colors, spacing, typography, radii, shadows)
- [x] Accessibility improvements: focus-visible ring, skip-to-content link, prefers-reduced-motion support, Firefox scrollbar
- [x] Glass utility class, consolidated gradient text utilities
- [x] Shared UI components: Button (6 variants, 4 sizes, loading state), Card (header/title/desc/content/footer), Input (label/error/hint/icons), Badge (5 colors, 2 sizes), EmptyState, ErrorState, Dialog (focus trap, escape-close), Tabs (animated indicator)
- [x] Updated Skeleton component: removed Framer Motion wrapper, respects reduced-motion
- [x] TanStack Query provider in App.tsx
- [x] Query hooks: useStats, useJobs, useProfile, usePipelineStatus, useCollectionStatus, useProfileStatus, useRunHistory
- [x] Mutations: useSaveProfile, useDeactivateProfile, useDismissJob, useSaveJob, useTriggerCollect
- [x] fetchJobs accepts AbortSignal for request cancellation
- [x] TypeScript compiles clean, Vite build passes

## Remaining Roadmap

### Phase 2: MainPage Redesign (in progress)
- [ ] New MainPage layout shell with sections
- [ ] Dashboard section (stats, pipeline controls, charts)
- [ ] Jobs section (filters + virtualized list)
- [ ] Settings as slide-over drawer
- [ ] Remove dead page components

### Phase 3: Polish
- [ ] Accessibility audit and fixes
- [ ] Animation polish (micro-interactions)
- [ ] Responsive testing
- [ ] Error/empty state coverage

### Phase 4: Backend Foundation
- [ ] Replace thread-based pipeline with proper job queue
- [ ] Alembic migration system
- [ ] Connection pool health checks + context managers
- [ ] Standardize error handling across collectors
- [ ] Fix Remotive async regression
- [ ] Dead code removal (wellfound, iimjobs, sync collectors)

### Phase 5: Database Modernization
- [ ] Enable pgvector extension, migrate embedding column to vector(384)
- [ ] Migrate TEXT timestamps to TIMESTAMPTZ
- [ ] Normalize run_history into run_source_stats child table
- [ ] Add pg_trgm indexes for LIKE searches
- [ ] Keyset pagination for jobs API

### Phase 6: Infrastructure
- [ ] CI/CD with GitHub Actions (lint, type-check, test, build)
- [ ] Test suite (pytest + React Testing Library)
- [ ] Sentry error reporting
- [ ] Docker image optimization
- [ ] Dependency lock file

## New Feature Ideas
- AI-powered job matching (leveraging existing embeddings)
- Email alerts for matching jobs
- Application tracker with status pipeline
- Premium: Auto-generated cover letters
- Premium: Salary insights and negotiation data
- Job market trends dashboard
- Chrome extension for one-click job saving
- Team/org accounts with shared job pools

## UI/UX Redesign Ideas
- Unified MainPage with tabs: Dashboard, Jobs, Profile (no multi-page nav)
- Virtualized job list with infinite scroll
- Job detail peek panel (slide-in from right)
- Dark-only premium theme with glass morphism
- Real-time pipeline visualization with animated source grid
- Onboarding wizard for new users
- Mobile-first filter bar with chips
- Always-visible actions (no hover dependency)
