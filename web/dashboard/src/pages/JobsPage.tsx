import { useState, useEffect, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { cn, timeAgo } from '../lib/utils'
import { fetchJobs, JobsResponse, Job, dismissJob, saveJob } from '../lib/api'
import { useToast } from '../lib/ToastContext'
import {
  Search, ChevronLeft, ChevronRight, MapPin,
  ExternalLink, Calendar, Briefcase, X, Sparkles,
  ThumbsDown, ThumbsUp, CheckCircle2,
} from 'lucide-react'

const SORT_OPTIONS = [
  { value: 'newest', label: 'Newest First' },
  { value: 'oldest', label: 'Oldest First' },
  { value: 'company', label: 'Company A-Z' },
  { value: 'title', label: 'Title A-Z' },
  { value: 'match', label: 'Profile Match' },
]

const jobVariants = {
  hidden: { opacity: 0, y: 8 },
  visible: (i: number) => ({
    opacity: 1,
    y: 0,
    transition: { delay: i * 0.03, duration: 0.3 },
  }),
}

export default function JobsPage() {
  const { addToast } = useToast()
  const [searchParams, setSearchParams] = useSearchParams()
  const [data, setData] = useState<JobsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [dismissedIds, setDismissedIds] = useState<Set<number>>(new Set())
  const [savedIds, setSavedIds] = useState<Set<number>>(new Set())

  const handleDismiss = async (jobId: number) => {
    try {
      await dismissJob(jobId)
      setDismissedIds(prev => new Set(prev).add(jobId))
      setSavedIds(prev => { const s = new Set(prev); s.delete(jobId); return s })
      addToast('info', 'Dismissed', 'Job dismissed. Similar jobs will rank lower.')
    } catch {
      addToast('error', 'Error', 'Failed to dismiss job')
    }
  }

  const handleSave = async (jobId: number) => {
    try {
      await saveJob(jobId)
      setSavedIds(prev => new Set(prev).add(jobId))
      setDismissedIds(prev => { const s = new Set(prev); s.delete(jobId); return s })
      addToast('success', 'Saved', 'Job saved! Similar jobs will rank higher.')
    } catch {
      addToast('error', 'Error', 'Failed to save job')
    }
  }

  const filters = {
    source: searchParams.get('source') || '',
    company: searchParams.get('company') || '',
    location: searchParams.get('location') || '',
    search: searchParams.get('search') || '',
    india: searchParams.get('india') || '',
    date_from: searchParams.get('date_from') || '',
    date_to: searchParams.get('date_to') || '',
    sort: searchParams.get('sort') || 'newest',
    page: parseInt(searchParams.get('page') || '1'),
  }

  const activeFilters = Object.entries(filters).filter(([k, v]) =>
    v && k !== 'sort' && k !== 'page' && String(v) !== ''
  ).length

  const loadJobs = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetchJobs(filters)
      setData(res)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load jobs')
    } finally {
      setLoading(false)
    }
  }, [searchParams.toString()])

  useEffect(() => { loadJobs() }, [loadJobs])

  const updateFilter = (key: string, value: string) => {
    const next = new URLSearchParams(searchParams)
    if (value) next.set(key, value)
    else next.delete(key)
    if (key !== 'page') next.delete('page')
    setSearchParams(next)
  }

  const clearFilters = () => setSearchParams(new URLSearchParams({ sort: filters.sort }))

  const fitBadge = (fit: string | null): { color: string; label: string } | null => {
    if (!fit) return null
    switch (fit) {
      case 'STRONG': return { color: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400 border-emerald-300 dark:border-emerald-700', label: 'STRONG' }
      case 'GOOD': return { color: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400 border-amber-300 dark:border-amber-700', label: 'GOOD' }
      case 'WEAK': return { color: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400 border-red-300 dark:border-red-700', label: 'WEAK' }
      default: return null
    }
  }

  const scoreColor = (score: number | null | undefined): string => {
    if (!score) return 'text-muted-foreground'
    if (score >= 80) return 'text-emerald-600 dark:text-emerald-400'
    if (score >= 50) return 'text-amber-600 dark:text-amber-400'
    return 'text-muted-foreground'
  }

  return (
    <main className="mx-auto max-w-[1440px] px-4 sm:px-6 lg:px-8 pb-16">
      {/* Header */}
      <motion.section
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        className="mb-6 mt-8"
      >
        <div className="mb-4 flex items-center gap-3">
          <motion.div
            initial={{ scaleY: 0 }}
            animate={{ scaleY: 1 }}
            transition={{ duration: 0.4 }}
            className="h-8 w-1 rounded-full bg-gradient-brand origin-bottom"
          />
          <h2 className="font-display text-2xl font-bold tracking-tight text-foreground sm:text-3xl">
            Jobs
          </h2>
          {data && (
            <motion.span
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              className="rounded-full bg-secondary px-3 py-1 font-mono text-[10px] font-semibold text-muted-foreground"
            >
              {data.count.toLocaleString()} results
            </motion.span>
          )}
        </div>

        {/* Filter bar */}
        <div className="rounded-xl border bg-card p-4 shadow-sm">
          <div className="flex flex-wrap items-end gap-3">
            <FilterGroup label="Search">
              <div className="relative">
                <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                <input
                  className="h-9 w-full rounded-lg border bg-background pl-8 pr-3 font-mono text-sm transition-all duration-200 focus:border-brand-blue focus:outline-none focus:ring-2 focus:ring-brand-blue/20 sm:w-52"
                  placeholder="Title, company..."
                  value={filters.search}
                  onChange={e => updateFilter('search', e.target.value)}
                />
              </div>
            </FilterGroup>
            <FilterGroup label="Source">
              <select className="h-9 rounded-lg border bg-background px-2.5 font-mono text-sm transition-all duration-200 focus:border-brand-blue focus:outline-none focus:ring-2 focus:ring-brand-blue/20" value={filters.source} onChange={e => updateFilter('source', e.target.value)}>
                <option value="">All Sources</option>
                {(data?.sources ?? []).map(s => <option key={s} value={s}>{s}</option>)}
              </select>
            </FilterGroup>
            <FilterGroup label="Company">
              <input className="h-9 w-40 rounded-lg border bg-background px-3 font-mono text-sm transition-all duration-200 focus:border-brand-blue focus:outline-none focus:ring-2 focus:ring-brand-blue/20" placeholder="Company name..." value={filters.company} onChange={e => updateFilter('company', e.target.value)} />
            </FilterGroup>
            <FilterGroup label="Location">
              <input className="h-9 w-40 rounded-lg border bg-background px-3 font-mono text-sm transition-all duration-200 focus:border-brand-blue focus:outline-none focus:ring-2 focus:ring-brand-blue/20" placeholder="City..." value={filters.location} onChange={e => updateFilter('location', e.target.value)} />
            </FilterGroup>
            <FilterGroup label="Sort">
              <select className="h-9 rounded-lg border bg-background px-2.5 font-mono text-sm transition-all duration-200 focus:border-brand-blue focus:outline-none focus:ring-2 focus:ring-brand-blue/20" value={filters.sort} onChange={e => updateFilter('sort', e.target.value)}>
                {SORT_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </FilterGroup>
            <FilterGroup label="India">
              <label className="flex h-9 cursor-pointer items-center gap-2 rounded-lg border bg-background px-3 hover:bg-secondary/50 transition-colors">
                <input type="checkbox" checked={filters.india === '1'} onChange={e => updateFilter('india', e.target.value === '1' ? '' : '1')} className="accent-brand-blue" />
                <span className="font-mono text-xs font-medium">India only</span>
              </label>
            </FilterGroup>
            <AnimatePresence>
              {activeFilters > 0 && (
                <motion.button
                  initial={{ opacity: 0, scale: 0.8 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.8 }}
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                  onClick={clearFilters}
                  className="flex h-9 items-center gap-1 rounded-lg px-3 font-mono text-xs font-medium text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
                >
                  <X className="h-3.5 w-3.5" /> Clear
                </motion.button>
              )}
            </AnimatePresence>
          </div>
        </div>
      </motion.section>

      {/* Results */}
      {loading ? (
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.06 }}
              className="rounded-xl border bg-card p-5"
            >
              <div className="shimmer-bg h-5 w-3/4 rounded-lg mb-2" />
              <div className="shimmer-bg h-4 w-1/2 rounded mb-3" />
              <div className="shimmer-bg h-3 w-1/3 rounded" />
            </motion.div>
          ))}
        </div>
      ) : error ? (
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          className="flex flex-col items-center justify-center rounded-xl border bg-card py-16"
        >
          <p className="font-mono text-sm text-destructive">{error}</p>
          <motion.button
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            onClick={loadJobs}
            className="mt-4 rounded-xl bg-gradient-brand px-5 py-2.5 font-display text-sm font-bold text-primary-foreground shadow-lg"
          >
            Retry
          </motion.button>
        </motion.div>
      ) : !data?.jobs.length ? (
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          className="flex flex-col items-center justify-center rounded-xl border bg-card py-16 text-muted-foreground"
        >
          <Briefcase className="mb-3 h-10 w-10 opacity-20" />
          <p className="font-mono text-sm">No jobs match your filters</p>
          <motion.button
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            onClick={clearFilters}
            className="mt-4 rounded-xl bg-secondary px-5 py-2.5 font-mono text-xs font-semibold"
          >
            Clear all filters
          </motion.button>
        </motion.div>
      ) : (
        <>
          <div className="space-y-2">
            {data.jobs.map((job, i) => {
              const badge = fitBadge(job.role_fit)
              return (
                <motion.div
                  key={job.id}
                  custom={i}
                  variants={jobVariants}
                  initial="hidden"
                  animate="visible"
                  whileHover={{ y: -2 }}
                  className="group/job rounded-xl border bg-card p-4 shadow-sm transition-shadow duration-200 hover:shadow-md sm:p-5"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <a
                          href={job.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="font-display text-base font-bold text-foreground transition-colors group-hover/job:text-brand-blue hover:underline decoration-brand-blue/30"
                        >
                          {job.title}
                        </a>
                        {badge && (
                          <span className={cn('inline-flex items-center rounded-md border px-1.5 py-0.5 font-mono text-[10px] font-bold', badge.color)}>
                            {badge.label}
                          </span>
                        )}
                        {job.is_india === 1 && (
                          <span className="inline-flex items-center gap-1 rounded-md border border-amber-500/30 bg-amber-50 px-1.5 py-0.5 font-mono text-[10px] font-bold text-amber-700 dark:bg-amber-900/20 dark:text-amber-400">
                            <MapPin className="h-2.5 w-2.5" />IN
                          </span>
                        )}
                      </div>
                      <div className="mt-1.5 flex items-center gap-3 text-sm text-muted-foreground flex-wrap">
                        <span className="font-medium text-foreground">{job.company}</span>
                        {job.location && (
                          <span className="flex items-center gap-1 text-xs">
                            <MapPin className="h-3 w-3" /> {job.location}
                          </span>
                        )}
                        {job.salary_range && (
                          <span className="font-mono text-xs">{job.salary_range}</span>
                        )}
                      </div>
                      <div className="mt-2 flex items-center gap-3 flex-wrap">
                        <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">{job.source}</span>
                        {job.scraped_at && (
                          <span className="flex items-center gap-1 text-[10px] text-muted-foreground/60">
                            <Calendar className="h-2.5 w-2.5" /> {timeAgo(job.scraped_at)}
                          </span>
                        )}
                        {job.profile_score != null && (
                          <motion.span
                            initial={{ opacity: 0, scale: 0 }}
                            animate={{ opacity: 1, scale: 1 }}
                            transition={{ delay: i * 0.03 + 0.2 }}
                            className={cn('ml-auto font-mono text-xs font-bold cursor-help', scoreColor(job.profile_score))}
                            title={job.profile_reasons
                              ? JSON.parse(job.profile_reasons).join('\n')
                              : `Profile match score: ${job.profile_score}%`}
                          >
                            {job.profile_score}% match
                          </motion.span>
                        )}
                      </div>
                    </div>
                    <div className="flex-shrink-0 flex items-center gap-1.5">
                      {/* Save button */}
                      <motion.button
                        whileHover={{ scale: 1.1 }}
                        whileTap={{ scale: 0.9 }}
                        onClick={(e) => { e.preventDefault(); handleSave(job.id) }}
                        className={cn(
                          'rounded-xl p-2 transition-all',
                          savedIds.has(job.id)
                            ? 'bg-emerald-100 text-emerald-600 dark:bg-emerald-900/30 dark:text-emerald-400'
                            : 'text-muted-foreground hover:bg-secondary hover:text-emerald-500',
                        )}
                        title="Save this job"
                      >
                        {savedIds.has(job.id) ? <CheckCircle2 className="h-4 w-4" /> : <ThumbsUp className="h-4 w-4" />}
                      </motion.button>

                      {/* Dismiss button */}
                      <motion.button
                        whileHover={{ scale: 1.1 }}
                        whileTap={{ scale: 0.9 }}
                        onClick={(e) => { e.preventDefault(); handleDismiss(job.id) }}
                        className={cn(
                          'rounded-xl p-2 transition-all',
                          dismissedIds.has(job.id)
                            ? 'bg-red-100 text-red-500 dark:bg-red-900/30 dark:text-red-400'
                            : 'text-muted-foreground hover:bg-secondary hover:text-red-400',
                        )}
                        title="Dismiss this job"
                      >
                        {dismissedIds.has(job.id) ? <X className="h-4 w-4" /> : <ThumbsDown className="h-4 w-4" />}
                      </motion.button>

                      {/* External link */}
                      <motion.a
                        whileHover={{ scale: 1.1 }}
                        whileTap={{ scale: 0.9 }}
                        href={job.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="rounded-xl p-2 text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
                        title="Open in new tab"
                      >
                        <ExternalLink className="h-4 w-4" />
                      </motion.a>
                    </div>
                  </div>
                </motion.div>
              )
            })}
          </div>

          {/* Pagination */}
          {data.total_pages > 1 && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className="mt-6 flex items-center justify-between rounded-xl border bg-card px-5 py-3 shadow-sm"
            >
              <span className="font-mono text-xs text-muted-foreground">
                Page {data.page} of {data.total_pages}
              </span>
              <div className="flex items-center gap-1">
                <motion.button
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                  onClick={() => updateFilter('page', String(data.page - 1))}
                  disabled={data.page <= 1}
                  className="rounded-lg p-2 text-muted-foreground transition-colors hover:bg-secondary disabled:opacity-30"
                >
                  <ChevronLeft className="h-4 w-4" />
                </motion.button>
                {Array.from({ length: Math.min(data.total_pages, 7) }, (_, i) => {
                  const pageNum = i + 1
                  const isActive = pageNum === data.page
                  return (
                    <motion.button
                      key={pageNum}
                      whileHover={{ scale: 1.05 }}
                      whileTap={{ scale: 0.95 }}
                      onClick={() => updateFilter('page', String(pageNum))}
                      className={cn(
                        'rounded-lg px-3 py-1.5 font-mono text-xs font-semibold transition-all',
                        isActive
                          ? 'bg-gradient-brand text-primary-foreground shadow-md'
                          : 'text-muted-foreground hover:bg-secondary',
                      )}
                    >
                      {pageNum}
                    </motion.button>
                  )
                })}
                <motion.button
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                  onClick={() => updateFilter('page', String(data.page + 1))}
                  disabled={data.page >= data.total_pages}
                  className="rounded-lg p-2 text-muted-foreground transition-colors hover:bg-secondary disabled:opacity-30"
                >
                  <ChevronRight className="h-4 w-4" />
                </motion.button>
              </div>
            </motion.div>
          )}
        </>
      )}
    </main>
  )
}

function FilterGroup({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <label className="font-mono text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">{label}</label>
      {children}
    </div>
  )
}
