export interface SourceMeta {
  name: string
  label: string
  color: string      // tailwind color name (e.g., "emerald", "blue", "sky")
  gradient: string   // tailwind gradient (e.g., "from-emerald-500 to-teal-500")
}

/** All 14 known job sources with display metadata.
 *  Shared by SourceBreakdown, SourceGlowGrid, and SourceStatusTicker.
 */
export const SOURCE_META: Record<string, SourceMeta> = {
  greenhouse:  { name: 'greenhouse', label: 'Greenhouse',  color: 'emerald',  gradient: 'from-emerald-500 to-teal-500' },
  lever:       { name: 'lever',      label: 'Lever',       color: 'blue',     gradient: 'from-blue-500 to-sky-500' },
  workday:     { name: 'workday',    label: 'Workday',     color: 'violet',   gradient: 'from-violet-500 to-purple-500' },
  linkedin:    { name: 'linkedin',   label: 'LinkedIn',    color: 'sky',      gradient: 'from-sky-500 to-cyan-500' },
  cutshort:    { name: 'cutshort',   label: 'Cutshort',    color: 'amber',    gradient: 'from-amber-500 to-orange-500' },
  wellfound:   { name: 'wellfound',  label: 'Wellfound',   color: 'rose',     gradient: 'from-rose-500 to-pink-500' },
  adzuna:      { name: 'adzuna',     label: 'Adzuna',      color: 'teal',     gradient: 'from-teal-500 to-emerald-500' },
  remoteok:    { name: 'remoteok',   label: 'RemoteOK',    color: 'orange',   gradient: 'from-orange-500 to-amber-500' },
  remotive:    { name: 'remotive',   label: 'Remotive',    color: 'cyan',     gradient: 'from-cyan-500 to-blue-500' },
  himalayas:   { name: 'himalayas',  label: 'Himalayas',   color: 'indigo',   gradient: 'from-indigo-500 to-violet-500' },
  yc_jobs:     { name: 'yc_jobs',    label: 'YC Jobs',     color: 'pink',     gradient: 'from-pink-500 to-rose-500' },
  arbeitnow:   { name: 'arbeitnow',  label: 'Arbeitnow',   color: 'lime',     gradient: 'from-lime-500 to-green-500' },
  iimjobs:     { name: 'iimjobs',    label: 'IIM Jobs',    color: 'fuchsia',  gradient: 'from-fuchsia-500 to-pink-500' },
  jsearch:     { name: 'jsearch',    label: 'JSearch',     color: 'yellow',   gradient: 'from-yellow-500 to-amber-500' },
}

/** Ordered list of all source entries (for grid layouts, tickers, etc.) */
export const SOURCE_LIST: SourceMeta[] = Object.values(SOURCE_META)

/** Ordered list of sources used in the async pipeline (matching run_all_async.py) */
export const ACTIVE_PIPELINE_SOURCES: string[] = [
  'remotive', 'greenhouse', 'lever', 'remoteok', 'arbeitnow',
  'himalayas', 'yc_jobs', 'cutshort', 'linkedin',
]

/** Lookup a source's metadata by name, with graceful fallback. */
export function getSourceMeta(source: string): SourceMeta {
  return SOURCE_META[source] ?? {
    name: source,
    label: source.charAt(0).toUpperCase() + source.slice(1),
    color: 'gray',
    gradient: 'from-gray-400 to-gray-500',
  }
}
