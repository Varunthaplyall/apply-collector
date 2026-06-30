# Frontend Modernization Design

**Date**: 2026-06-30
**Status**: Approved
**Approach**: A — Iterative Refinement of existing React + Vite + Tailwind stack

## Architecture

- **Stack**: React 18, Vite 5, Tailwind CSS 3, Framer Motion (unchanged)
- **New dependencies**: `@tanstack/react-query` (server state), `@tanstack/react-virtual` (windowed job list)
- **SPA model**: Single MainPage with sections, panels, drawers — no multi-route navigation beyond `/login`
- **Dead code removal**: DashboardPage, JobsPage, ProfilePage, HistoryPage (functionality folded into MainPage)

## Component System

### Design Tokens
CSS custom properties in `index.css`:
- `--space-*` (4, 8, 12, 16, 24, 32, 48, 64)
- `--font-size-*` (xs, sm, base, lg, xl, 2xl, 3xl)
- `--color-*` (brand, success, warning, danger, info + foreground/muted variants)
- `--radius-*` (sm, md, lg, xl, full)
- `--shadow-*` (sm, md, lg, xl)

### Shared Components
All in `src/components/ui/`:
- **Button** — variants: primary, secondary, ghost, danger; sizes: sm, md, lg; states: loading, disabled
- **Card** — padding variants, hoverable, interactive
- **Input** — with label, error, hint, icon slots
- **Select** — native select styled consistently
- **Badge** — variants: default, success, warning, danger, info
- **Chip** — removable tags for filters/skills
- **Skeleton** — text, heading, circle, card, block variants; respects reduced-motion
- **Dialog/Modal** — focus trap, escape-to-close, overlay backdrop
- **Sheet/Drawer** — slide-in panel from right/bottom, focus trap
- **Tabs** — horizontal tab bar with animated indicator
- **EmptyState** — icon, title, description, optional action button
- **ErrorState** — error message, retry button, optional details
- **Toast** — success, error, warning, info variants; pause-on-hover; max 5 visible

### Layout Shell
```
┌──────────────────────────────────────┐
│ NavHeader (fixed, h-12)              │
├──────────────────────────────────────┤
│                                      │
│ Main Content Area (flex-1, overflow) │
│ ┌────────────────────────────────────┤
│ │ Dashboard Section                  │
│ │ (Stats, Charts, Pipeline)          │
│ ├────────────────────────────────────┤
│ │ Jobs Section                       │
│ │ (Filters + Virtual List)           │
│ └────────────────────────────────────┘
│                                      │
│ Settings Panel (slide-over, right)   │
│                                      │
└──────────────────────────────────────┘
```

## State Management

### TanStack Query (`src/lib/queries.ts`)
- `useStats()` — dashboard stats, staleTime: 5min
- `useJobs(filters)` — paginated job list, staleTime: 2min
- `useProfile()` — user profile, staleTime: 10min
- `usePipelineStatus()` — collection status, refetchInterval: 2s when active
- `useRunHistory()` — historical runs, staleTime: 10min
- `useCollectionStatus()` — current collection state, refetchInterval: 5s when active
- Mutations: `useSaveProfile()`, `useDismissJob()`, `useSaveJob()`, `useTriggerCollect()`

### URL State (unchanged)
Filters in URL search params: source, company, location, search, india, sort, page

## Key UX Improvements

### Accessibility
- Skip-to-content link (first focusable element)
- All interactive elements have visible focus rings (`focus-visible:ring-2`)
- Job card actions always visible (not hover-revealed)
- Settings panel traps focus when open
- All form inputs have programmatic `<label>` associations
- Toast notifications have `role="status"` and `aria-live`
- `prefers-reduced-motion` respected globally via Tailwind `motion-safe:` / `motion-reduce:` prefixes

### Responsive Design
- Mobile: filter bar collapses to expandable search + filter chips
- Mobile: settings opens as bottom sheet (not side drawer)
- Tablet: 2-column stat grid, single-column job list
- Desktop: 4-column stat grid, job list with detail peek
- Job actions always visible on touch devices (no hover dependency)

### Performance
- Job list virtualized (TanStack Virtual) — render ~15 items instead of hundreds
- Search input debounced (300ms)
- `React.memo` on StatCard, JobCard, SourceCard
- CSS transitions for static animations (hover states, skeleton shimmer)
- Framer Motion reserved for enter/exit/layout animations
- Query deduplication and cache via TanStack Query
- Request cancellation on filter change / unmount

### Loading States
- Progressive skeleton hierarchy matching content shape
- Stale data shown with subtle opacity + spinner (not blank screen)
- Pipeline progress: animated progress bar + source status ticker

### Empty States
- "No jobs match your filters" → suggests removing filters
- "No profile configured" → onboarding flow inline
- "No runs yet" → explains what collection does + when next run is

## Implementation Phases

### Phase 1: Foundation
1. Install TanStack Query, TanStack Virtual
2. Create design tokens in index.css
3. Build shared UI components (Button, Card, Input, Badge, Skeleton, EmptyState, ErrorState)
4. Set up QueryClient provider in App.tsx
5. Create query hooks in src/lib/queries.ts

### Phase 2: MainPage Redesign
1. Build new MainPage layout shell with sections
2. Integrate Dashboard section (stats, pipeline, charts)
3. Integrate Jobs section (filters + virtualized list)
4. Integrate Settings as slide-over drawer
5. Remove dead page components

### Phase 3: Polish
1. Accessibility audit and fixes
2. Animation polish (micro-interactions, transitions)
3. Responsive testing and fixes
4. Error/empty state coverage
