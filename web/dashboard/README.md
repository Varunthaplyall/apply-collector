# The Apply Collector — React Dashboard

Production-grade metrics dashboard built with React, TypeScript, Tailwind CSS, and shadcn/ui design patterns.

## Stack

- **React 18** — UI framework
- **TypeScript** — Type safety
- **Tailwind CSS 3** — Utility-first styling
- **shadcn/ui design tokens** — CSS variable-based theme system
- **Recharts** — Data visualization (bundled, available for expansion)
- **Lucide React** — Icon library
- **Vite 5** — Build tool

## Quick Start

```bash
# Install dependencies
npm install

# Development (Vite dev server on :3000, proxies /api to Flask :5000)
npm run dev

# Production build (outputs to ../static/dist/)
npm run build

# Then start Flask normally:
python -m web.app --port 5000
```

## Architecture

```
src/
├── lib/
│   ├── api.ts          # API client (fetch stats, trigger runs, SSE)
│   └── utils.ts        # cn(), formatNumber(), timeAgo()
├── components/
│   ├── NavHeader.tsx       # Sticky nav, theme toggle, refresh
│   ├── StatCard.tsx        # KPI cards with sparklines + trends
│   ├── SourceBreakdown.tsx # Animated horizontal bar chart
│   ├── TopCompanies.tsx    # Ranked company list with mini-bars
│   ├── SparkChart.tsx      # SVG sparkline with tooltips
│   ├── RecentActivity.tsx  # Timeline of recent collection runs
│   └── PipelineControls.tsx# Run triggers with terminal output
├── App.tsx              # Main dashboard layout (2-col grid)
├── main.tsx             # React entry point
└── index.css            # Design tokens, Tailwind layers, fonts
```

## Design System

- **Typography**: Cabinet Grotesk (display), Inter (body), JetBrains Mono (data)
- **Colors**: HSL-based CSS custom properties supporting light/dark themes
- **Spacing**: 4px base grid with Tailwind's spacing scale
- **Micro-interactions**: Hover scale, translate, color shifts on all interactive elements
- **Animations**: fade-in, slide-up, scale-in keyframes for content reveal
- **Radius**: 0.625rem default — slightly softened corners

## Features

- **Dark/Light mode** — Persisted to localStorage, respects system preference
- **Responsive** — Mobile-first grid, adapts from 1→2→4→6 columns
- **Skeleton loading** — All components have loading states
- **Empty states** — Graceful fallbacks when no data exists
- **SSE streaming** — Real-time pipeline run output in terminal-style panel
- **Trend indicators** — Sparklines and percentage badges on KPI cards

## Flask Integration

The built assets are output to `web/static/dist/` and served by Flask's static file handler.
The Flask template `web/templates/dashboard_react.html` loads the hashed JS/CSS bundles.
In development, the Vite dev server proxies `/api` calls to Flask on port 5000.
