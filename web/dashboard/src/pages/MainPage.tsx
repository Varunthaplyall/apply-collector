import { useState, useEffect, useCallback, useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { cn, safeUrl, timeAgo, formatNumber } from '@/lib/utils'
import {
  fetchJobs, type JobsResponse, type Job, type Profile, type Stats,
  type PipelineStatus, type CollectionStatus, type RunRecord,
} from '@/lib/api'
import {
  useStats, useJobs, useProfile, usePipelineStatus,
  useCollectionStatus, useDismissJob, useSaveJob, useSaveProfile,
  useRunHistory,
} from '@/lib/queries'
import { useToast, type ToastType } from '@/lib/ToastContext'
import { useAuth } from '@/lib/AuthContext'
import { useAdminMode } from '@/lib/admin'
import {
  Search, ChevronLeft, ChevronRight, MapPin,
  ExternalLink, Calendar, Briefcase, X,
  ThumbsDown, ThumbsUp, CheckCircle2,
  Settings, Sparkles, Target, Database,
  SlidersHorizontal, Layers, TrendingUp,
  Building2, Filter, Home, ListFilter,
  Loader2, RefreshCw, ArrowUpRight, Clock,
} from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Input } from '@/components/ui/Input'
import { Tabs, TabList, Tab, TabPanel } from '@/components/ui/Tabs'
import { EmptyState } from '@/components/ui/EmptyState'
import { ErrorState } from '@/components/ui/ErrorState'
import Skeleton from '@/components/Skeleton'
import PipelineControls from '@/components/PipelineControls'
import SparkChart from '@/components/SparkChart'
import TopCompanies from '@/components/TopCompanies'
import SourceBreakdown from '@/components/SourceBreakdown'
import RecentActivity from '@/components/RecentActivity'
import SettingsDrawer from '@/components/SettingsDrawer'

// ═══════════════════════════════════════════════════════════════════════════
// Constants
// ═══════════════════════════════════════════════════════════════════════════

const SORT_OPTIONS = [
  { value: 'match', label: 'Best Match' },
  { value: 'newest', label: 'Newest' },
  { value: 'oldest', label: 'Oldest' },
  { value: 'company', label: 'Company' },
  { value: 'title', label: 'Title' },
]

const ROLE_CATEGORIES = [
  'Software Engineer', 'Senior Software Engineer', 'Engineering Manager',
  'Data Scientist', 'DevOps Engineer', 'Security Engineer',
  'Product Manager', 'Product Designer', 'UX Designer',
]

const WORK_TYPES = ['Full-time', 'Part-time', 'Contract', 'Internship', 'Freelance']

const ALL_SOURCES = [
  'greenhouse', 'lever', 'workday', 'linkedin', 'cutshort',
  'remoteok', 'remotive', 'himalayas', 'yc_jobs', 'arbeitnow',
]

// ═══════════════════════════════════════════════════════════════════════════
// Main Page
// ═══════════════════════════════════════════════════════════════════════════

export default function MainPage() {
  const { user } = useAuth()
  const { isAdmin } = useAdminMode()
  const { addToast } = useToast()
  const [searchParams, setSearchParams] = useSearchParams()
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [activeTab, setActiveTab] = useState('dashboard')

  // Auto-open settings for onboarding
  useEffect(() => {
    if (searchParams.get('onboarding') === '1') {
      setSettingsOpen(true)
      const next = new URLSearchParams(searchParams)
      next.delete('onboarding')
      setSearchParams(next, { replace: true })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Filters from URL
  const filters = useMemo(() => ({
    source: searchParams.get('source') || '',
    company: searchParams.get('company') || '',
    location: searchParams.get('location') || '',
    search: searchParams.get('search') || '',
    india: searchParams.get('india') || '',
    sort: searchParams.get('sort') || 'match',
    page: parseInt(searchParams.get('page') || '1'),
  }), [searchParams])

  const activeFilterCount = useMemo(
    () => Object.entries(filters).filter(([k, v]) =>
      v && k !== 'sort' && k !== 'page' && String(v) !== ''
    ).length,
    [filters],
  )

  // Queries
  const { data: stats, isLoading: statsLoading } = useStats()
  const { data: jobsData, isLoading: jobsLoading, error: jobsError, refetch: refetchJobs } = useJobs(filters)
  const { data: profile } = useProfile()
  const { data: collectionStatus } = useCollectionStatus()

  // Profile is already prefetched above (line 110) — SettingsDrawer reads from cache
  // Run history is prefetched for the History tab (admin-only)
  const { data: runHistory } = useRunHistory()

  // Mutations
  const dismissMutation = useDismissJob()
  const saveMutation = useSaveJob()

  // URL helpers
  const updateFilter = useCallback((key: string, value: string) => {
    const next = new URLSearchParams(searchParams)
    if (value) next.set(key, value)
    else next.delete(key)
    if (key !== 'page') next.delete('page')
    setSearchParams(next)
  }, [searchParams, setSearchParams])

  const clearFilters = useCallback(() => {
    setSearchParams(new URLSearchParams({ sort: filters.sort }))
  }, [filters.sort, setSearchParams])

  // Job actions
  const handleDismiss = useCallback(async (jobId: number) => {
    try { await dismissMutation.mutateAsync(jobId) }
    catch { addToast('error', 'Error', 'Failed to dismiss job') }
  }, [dismissMutation, addToast])

  const handleSave = useCallback(async (jobId: number) => {
    try { await saveMutation.mutateAsync(jobId) }
    catch { addToast('error', 'Error', 'Failed to save job') }
  }, [saveMutation, addToast])

  // Pipeline status polling active when tab is Jobs
  const isPipelineActive = true // Always poll

  // Score helpers
  const scoreColor = (s: number | null | undefined) => {
    if (!s) return 'text-muted-foreground'
    if (s >= 80) return 'text-emerald-400'
    if (s >= 50) return 'text-amber-400'
    return 'text-muted-foreground'
  }

  const scoreBg = (s: number | null | undefined) => {
    if (!s) return 'bg-muted text-muted-foreground'
    if (s >= 80) return 'bg-emerald-500/15 text-emerald-400 border-emerald-500/20'
    if (s >= 50) return 'bg-amber-500/15 text-amber-400 border-amber-500/20'
    return 'bg-muted text-muted-foreground'
  }

  return (
    <div className="flex h-[calc(100vh-48px)]">
      {/* ── Main Content ──────────────────────────────────────────────── */}
      <main className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Tabs */}
        <div className="flex-shrink-0 border-b border-border bg-background/80 backdrop-blur-sm px-3 py-1.5">
          <div className="flex items-center justify-between">
            {isAdmin ? (
              <Tabs defaultValue="dashboard" onChange={setActiveTab}>
                <TabList>
                  <Tab id="dashboard">
                    <Home className="h-3.5 w-3.5" /> Dashboard
                  </Tab>
                  <Tab id="jobs" count={jobsData?.count}>
                    <ListFilter className="h-3.5 w-3.5" /> Jobs
                  </Tab>
                  <Tab id="history">
                    <Clock className="h-3.5 w-3.5" /> History
                  </Tab>
                </TabList>
              </Tabs>
            ) : (
              <div className="flex items-center gap-2">
                <ListFilter className="h-3.5 w-3.5 text-muted-foreground" />
                <span className="text-sm font-semibold text-foreground">Jobs</span>
                {jobsData && (
                  <span className="text-xs text-muted-foreground tabular-nums">
                    {formatNumber(jobsData.count)} results
                  </span>
                )}
              </div>
            )}

            <button
              onClick={() => setSettingsOpen(true)}
              className="flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
            >
              <Settings className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">Settings</span>
            </button>
          </div>
        </div>

        {/* Tab Content */}
        <div className="flex-1 overflow-y-auto">
          <AnimatePresence mode="wait">
            <motion.div
              key={isAdmin ? activeTab : 'jobs'}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.15 }}
              className="h-full"
            >
              {isAdmin && activeTab === 'dashboard' ? (
                <DashboardTab
                  stats={stats ?? null}
                  statsLoading={statsLoading}
                  collectionStatus={collectionStatus ?? null}
                  profile={profile ?? null}
                />
              ) : isAdmin && activeTab === 'history' ? (
                <HistoryTab runHistory={runHistory ?? []} />
              ) : (
                <JobsTab
                  filters={Object.fromEntries(Object.entries(filters).map(([k, v]) => [k, String(v)]))}
                  jobsData={jobsData ?? null}
                  loading={jobsLoading}
                  error={jobsError instanceof Error ? jobsError.message : null}
                  activeFilterCount={activeFilterCount}
                  collectionStatus={collectionStatus ?? null}
                  updateFilter={updateFilter}
                  clearFilters={clearFilters}
                  handleDismiss={handleDismiss}
                  handleSave={handleSave}
                  scoreColor={scoreColor}
                  scoreBg={scoreBg}
                  onRetry={() => refetchJobs()}
                  onOpenSettings={() => setSettingsOpen(true)}
                />
              )}
            </motion.div>
          </AnimatePresence>
        </div>
      </main>

      {/* ── Settings Drawer ────────────────────────────────────────────── */}
      <SettingsDrawer
      	open={settingsOpen}
      	onClose={() => setSettingsOpen(false)}
      />
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════════════
// Dashboard Tab
// ═══════════════════════════════════════════════════════════════════════════

function DashboardTab({
  stats, statsLoading, collectionStatus, profile,
}: {
  stats: Stats | null
  statsLoading: boolean
  collectionStatus: CollectionStatus | null
  profile: Profile | null
}) {
  const lastRunText = collectionStatus?.last_run
    ? timeAgo(collectionStatus.last_run.run_date)
    : null

  return (
    <div className="p-4 lg:p-6 space-y-5 max-w-[1440px] mx-auto">
      {/* Welcome + Stats row */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-foreground tracking-tight">Dashboard</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            {collectionStatus
              ? `${formatNumber(collectionStatus.total_jobs)} jobs collected · Last run ${lastRunText}`
              : 'Loading...'}
          </p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          {statsLoading ? (
            <Skeleton variant="block" className="h-8 w-32" />
          ) : stats ? (
            <>
              <Badge color="info" size="md">
                {formatNumber(stats.unique)} unique jobs
              </Badge>
              {stats.profile_matches > 0 && (
                <Badge color="success" size="md">
                  {stats.profile_matches} matches
                </Badge>
              )}
              {stats.today_jobs > 0 && (
                <Badge color="violet" size="md">
                  {formatNumber(stats.today_jobs)} today
                </Badge>
              )}
            </>
          ) : null}
        </div>
      </div>

      {/* Stat Cards Grid */}
      {statsLoading ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} variant="card" className="h-24" />
          ))}
        </div>
      ) : stats ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <StatCardSimple
            label="Total Jobs"
            value={formatNumber(stats.total)}
            icon={<Database className="h-4 w-4" />}
            color="blue"
          />
          <StatCardSimple
            label="Unique Jobs"
            value={formatNumber(stats.unique)}
            icon={<Layers className="h-4 w-4" />}
            color="violet"
          />
          <StatCardSimple
            label="India Jobs"
            value={formatNumber(stats.india_count)}
            icon={<MapPin className="h-4 w-4" />}
            color="amber"
          />
          <StatCardSimple
            label="Your Matches"
            value={formatNumber(stats.profile_matches)}
            icon={<Target className="h-4 w-4" />}
            color="emerald"
          />
        </div>
      ) : null}

      {/* Pipeline + Source Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <PipelineControls
          onRunComplete={() => {}}
          profileReady={!!profile}
        />
        {stats ? (
          <SourceBreakdown sources={stats.by_source} total={stats.total} />
        ) : (
          <Skeleton variant="card" className="h-48" />
        )}
      </div>

      {/* Charts + Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {stats?.recent_runs?.length ? (
          <SparkChart runs={stats.recent_runs} />
        ) : (
          <Skeleton variant="card" className="h-48" />
        )}
        {stats?.recent_runs?.length ? (
          <RecentActivity runs={stats.recent_runs} />
        ) : (
          <Skeleton variant="card" className="h-48" />
        )}
      </div>

      {/* Top Companies + Locations */}
      {stats && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <TopCompanies companies={stats.top_companies} />
          {stats.top_india_locations?.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <MapPin className="h-4 w-4 text-amber-400" /> Top India Locations
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {stats.top_india_locations.slice(0, 8).map((loc, i) => (
                    <div key={loc.location} className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">{loc.location}</span>
                      <span className="font-mono text-xs font-semibold text-foreground">{loc.count}</span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  )
}

// Simple stat card for dashboard
function StatCardSimple({ label, value, icon, color }: {
  label: string; value: string; icon: React.ReactNode; color: string
}) {
  const colorMap: Record<string, string> = {
    blue: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
    violet: 'bg-violet-500/10 text-violet-400 border-violet-500/20',
    amber: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
    emerald: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
  }

  return (
    <Card className="hover:border-border/80 transition-colors duration-150">
      <CardContent className="p-4">
        <div className="flex items-center justify-between">
          <p className="text-xs font-medium text-muted-foreground">{label}</p>
          <div className={cn(
            'flex h-8 w-8 items-center justify-center rounded-lg border',
            colorMap[color] || colorMap.blue,
          )}>
            {icon}
          </div>
        </div>
        <p className="mt-2 text-2xl font-bold text-foreground tabular-nums tracking-tight">{value}</p>
      </CardContent>
    </Card>
  )
}

// ═══════════════════════════════════════════════════════════════════════════
// History Tab (admin only)
// ═══════════════════════════════════════════════════════════════════════════

function HistoryTab({ runHistory }: { runHistory: RunRecord[] }) {
  return (
    <div className="p-4 lg:p-6 space-y-4 max-w-[1440px] mx-auto">
      <div>
        <h1 className="text-xl font-bold text-foreground tracking-tight">Run History</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          {runHistory.length} collection runs recorded
        </p>
      </div>

      {runHistory.length === 0 ? (
        <EmptyState
          icon={<Clock className="h-8 w-8" />}
          title="No run history yet"
          description="Run history appears here after the first collection completes."
        />
      ) : (
        <Card>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border">
                    <th className="text-left px-4 py-3 text-xs font-semibold text-muted-foreground">Date</th>
                    <th className="text-right px-3 py-3 text-xs font-semibold text-muted-foreground">Total</th>
                    <th className="text-right px-3 py-3 text-xs font-semibold text-muted-foreground">Unique</th>
                    <th className="text-right px-3 py-3 text-xs font-semibold text-muted-foreground">India</th>
                    <th className="text-right px-3 py-3 text-xs font-semibold text-muted-foreground">GH</th>
                    <th className="text-right px-3 py-3 text-xs font-semibold text-muted-foreground">Lever</th>
                    <th className="text-right px-3 py-3 text-xs font-semibold text-muted-foreground">WD</th>
                    <th className="text-right px-3 py-3 text-xs font-semibold text-muted-foreground">CS</th>
                    <th className="text-right px-4 py-3 text-xs font-semibold text-muted-foreground">Time</th>
                  </tr>
                </thead>
                <tbody>
                  {runHistory.map((run) => (
                    <tr key={run.run_date} className="border-b border-border/50 hover:bg-muted/30 transition-colors">
                      <td className="px-4 py-2.5 font-mono text-xs text-foreground whitespace-nowrap">
                        {new Date(run.run_date).toLocaleDateString('en-IN', {
                          day: 'numeric', month: 'short', year: 'numeric',
                          hour: '2-digit', minute: '2-digit',
                        })}
                      </td>
                      <td className="px-3 py-2.5 text-right font-mono text-xs tabular-nums">{run.total_jobs.toLocaleString()}</td>
                      <td className="px-3 py-2.5 text-right font-mono text-xs tabular-nums text-emerald-400">{run.unique_jobs.toLocaleString()}</td>
                      <td className="px-3 py-2.5 text-right font-mono text-xs tabular-nums">{run.india_jobs.toLocaleString()}</td>
                      <td className="px-3 py-2.5 text-right font-mono text-xs tabular-nums text-muted-foreground">{run.gh_jobs.toLocaleString()}</td>
                      <td className="px-3 py-2.5 text-right font-mono text-xs tabular-nums text-muted-foreground">{run.lever_jobs.toLocaleString()}</td>
                      <td className="px-3 py-2.5 text-right font-mono text-xs tabular-nums text-muted-foreground">{run.workday_jobs.toLocaleString()}</td>
                      <td className="px-3 py-2.5 text-right font-mono text-xs tabular-nums text-muted-foreground">{run.cutshort_jobs.toLocaleString()}</td>
                      <td className="px-4 py-2.5 text-right font-mono text-xs tabular-nums text-muted-foreground">{run.run_time_s}s</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════════════
// Jobs Tab
// ═══════════════════════════════════════════════════════════════════════════

function JobsTab({
  filters, jobsData, loading, error, activeFilterCount,
  collectionStatus, updateFilter, clearFilters,
  handleDismiss, handleSave, scoreColor, scoreBg, onRetry, onOpenSettings,
}: {
  filters: Record<string, string>
  jobsData: JobsResponse | null
  loading: boolean
  error: string | null
  activeFilterCount: number
  collectionStatus: CollectionStatus | null
  updateFilter: (key: string, value: string) => void
  clearFilters: () => void
  handleDismiss: (id: number) => void
  handleSave: (id: number) => void
  scoreColor: (s: number | null | undefined) => string
  scoreBg: (s: number | null | undefined) => string
  onRetry: () => void
  onOpenSettings: () => void
}) {
  const [searchValue, setSearchValue] = useState(filters.search)

  // Debounced search
  useEffect(() => {
    const timer = setTimeout(() => {
      if (searchValue !== filters.search) {
        updateFilter('search', searchValue)
      }
    }, 300)
    return () => clearTimeout(timer)
  }, [searchValue]) // eslint-disable-line react-hooks/exhaustive-deps

  // Sync search param → input
  useEffect(() => {
    setSearchValue(filters.search)
  }, [filters.search])

  const statusText = collectionStatus?.last_run
    ? timeAgo(collectionStatus.last_run.run_date)
    : null

  return (
    <div className="flex flex-col h-full">
      {/* Filter Bar */}
      <div className="flex-shrink-0 border-b border-border/50 bg-background/80 backdrop-blur-sm px-3 py-2">
        <div className="flex items-center gap-2 flex-wrap">
          <div className="relative flex-1 min-w-[160px] max-w-[320px]">
            <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground/50" aria-hidden="true" />
            <input
              type="search"
              aria-label="Search jobs"
              className="h-8 w-full rounded-lg border border-border/50 bg-muted/50 pl-8 pr-3 text-sm text-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:ring-2 focus:ring-ring/20 focus:border-ring/30 transition-colors"
              placeholder="Search jobs..."
              value={searchValue}
              onChange={e => setSearchValue(e.target.value)}
            />
          </div>

          <select
            aria-label="Filter by source"
            className="h-8 rounded-lg border border-border/50 bg-muted/50 px-2.5 text-xs text-foreground focus:outline-none focus:ring-2 focus:ring-ring/20"
            value={filters.source}
            onChange={e => updateFilter('source', e.target.value)}
          >
            <option value="">All Sources</option>
            {(jobsData?.sources ?? ALL_SOURCES).map(s => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>

          <input
            aria-label="Filter by location"
            className="h-8 w-28 rounded-lg border border-border/50 bg-muted/50 px-2.5 text-xs text-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:ring-2 focus:ring-ring/20"
            placeholder="Location..."
            value={filters.location}
            onChange={e => updateFilter('location', e.target.value)}
          />

          <label className={cn(
            'flex h-8 cursor-pointer items-center gap-1.5 rounded-lg border px-2.5 text-xs font-medium select-none transition-colors',
            filters.india === '1'
              ? 'border-amber-500/30 bg-amber-500/10 text-amber-400'
              : 'border-border/50 bg-muted/50 text-muted-foreground hover:text-foreground'
          )}>
            <input
              type="checkbox"
              checked={filters.india === '1'}
              onChange={e => updateFilter('india', e.target.checked ? '1' : '')}
              className="sr-only"
            />
            <MapPin className="h-3 w-3" /> India
          </label>

          <select
            aria-label="Sort order"
            className="h-8 rounded-lg border border-border/50 bg-muted/50 px-2.5 text-xs text-foreground focus:outline-none focus:ring-2 focus:ring-ring/20"
            value={filters.sort}
            onChange={e => updateFilter('sort', e.target.value)}
          >
            {SORT_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>

          <AnimatePresence>
            {activeFilterCount > 0 && (
              <motion.button
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.8 }}
                onClick={clearFilters}
                className="flex h-8 items-center gap-1 rounded-lg border border-destructive/20 px-2.5 text-xs text-muted-foreground hover:bg-destructive/10 hover:text-destructive transition-colors"
                aria-label="Clear all filters"
              >
                <X className="h-3 w-3" /> Clear
              </motion.button>
            )}
          </AnimatePresence>

          {/* Collection status + result count */}
          <div className="ml-auto flex items-center gap-3">
            {collectionStatus && (
              <span className="hidden sm:flex items-center gap-1.5 text-xs text-muted-foreground/50">
                <Database className="h-3 w-3" />
                {formatNumber(collectionStatus.total_jobs)} jobs · {statusText}
              </span>
            )}
            {jobsData && (
              <span className="text-xs font-semibold text-muted-foreground tabular-nums">
                {formatNumber(jobsData.count)} results
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Job List */}
      <div className="flex-1 overflow-y-auto">
        {loading && !jobsData ? (
          <div className="p-3 space-y-2">
            {Array.from({ length: 8 }).map((_, i) => (
              <Skeleton key={i} variant="card" className="h-[72px]" delay={i * 0.05} />
            ))}
          </div>
        ) : error ? (
          <ErrorState message={error} onRetry={onRetry} />
        ) : !jobsData?.jobs?.length ? (
          <EmptyState
            icon={<Briefcase className="h-8 w-8" />}
            title={
              activeFilterCount > 0
                ? 'No jobs match your filters'
                : 'No jobs collected yet'
            }
            description={
              activeFilterCount > 0
                ? 'Try removing some filters or adjusting your search terms.'
                : 'Jobs are collected automatically every 4 hours. Check back soon, or adjust your profile settings to match more sources.'
            }
            action={
              activeFilterCount > 0 ? (
                <Button variant="outline" size="sm" onClick={clearFilters}>Clear filters</Button>
              ) : (
                <Button variant="outline" size="sm" onClick={onOpenSettings}>
                  <Settings className="h-3.5 w-3.5 mr-1.5" /> Adjust Profile
                </Button>
              )
            }
          />
        ) : (
          <>
            <div className="p-3 space-y-1.5">
              {jobsData.jobs.map((job, i) => (
                <JobCard
                  key={job.id}
                  job={job}
                  index={i}
                  scoreColor={scoreColor}
                  scoreBg={scoreBg}
                  onDismiss={handleDismiss}
                  onSave={handleSave}
                />
              ))}
            </div>

            {/* Pagination */}
            {jobsData.total_pages > 1 && (
              <div className="flex items-center justify-center gap-2 pb-4">
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => updateFilter('page', String(jobsData.page - 1))}
                  disabled={jobsData.page <= 1}
                  aria-label="Previous page"
                >
                  <ChevronLeft className="h-4 w-4" />
                </Button>
                <span className="text-xs text-muted-foreground font-mono">
                  {jobsData.page} / {jobsData.total_pages}
                </span>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => updateFilter('page', String(jobsData.page + 1))}
                  disabled={jobsData.page >= jobsData.total_pages}
                  aria-label="Next page"
                >
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════════════
// Job Card
// ═══════════════════════════════════════════════════════════════════════════

function JobCard({
  job, index, scoreColor, scoreBg, onDismiss, onSave,
}: {
  job: Job; index: number
  scoreColor: (s: number | null | undefined) => string
  scoreBg: (s: number | null | undefined) => string
  onDismiss: (id: number) => void
  onSave: (id: number) => void
}) {
  const [saved, setSaved] = useState(false)
  const [dismissed, setDismissed] = useState(false)

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: Math.min(index * 0.015, 0.3), duration: 0.2 }}
      className={cn(
        'group/job rounded-lg border border-border/50 bg-card/70 hover:bg-card hover:border-border px-3 py-2.5 transition-all duration-150',
        dismissed && 'opacity-40 pointer-events-none',
      )}
    >
      <div className="flex items-start gap-3">
        {/* Score badge */}
        {job.profile_score != null && (
          <div className={cn(
            'flex-shrink-0 flex items-center justify-center w-10 h-10 rounded-xl border text-xs font-bold tabular-nums',
            scoreBg(job.profile_score),
          )}>
            {job.profile_score}
          </div>
        )}

        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5 flex-wrap">
            <a
              href={safeUrl(job.url)}
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm font-semibold text-foreground hover:text-primary truncate transition-colors"
            >
              {job.title}
            </a>
            {job.is_india === 1 && (
              <Badge color="warning" size="sm">
                <MapPin className="h-2 w-2 mr-0.5" /> IN
              </Badge>
            )}
            {job.match_score != null && job.match_score >= 80 && (
              <Badge color="success" size="sm">Strong Match</Badge>
            )}
          </div>

          <div className="mt-1 flex items-center gap-1.5 text-xs text-muted-foreground flex-wrap">
            <span className="font-medium text-foreground/80">{job.company}</span>
            {job.location && (
              <span className="flex items-center gap-0.5">
                <MapPin className="h-3 w-3 opacity-40" aria-hidden="true" />
                {job.location}
              </span>
            )}
            {job.salary_range && (
              <span className="font-mono text-[11px] text-muted-foreground/60">{job.salary_range}</span>
            )}
          </div>

          <div className="mt-1 flex items-center gap-2">
            <Badge color="default" size="sm">{job.source}</Badge>
            {job.scraped_at && (
              <span className="flex items-center gap-0.5 text-[10px] text-muted-foreground/40">
                <Calendar className="h-2.5 w-2.5" aria-hidden="true" />
                {timeAgo(job.scraped_at)}
              </span>
            )}
          </div>
        </div>

        {/* Actions — always visible, not hover-revealed */}
        <div className="flex-shrink-0 flex items-center gap-0.5">
          <button
            onClick={(e) => { e.preventDefault(); setSaved(!saved); onSave(job.id) }}
            className={cn(
              'rounded-lg p-1.5 transition-colors',
              saved
                ? 'bg-emerald-500/10 text-emerald-400'
                : 'text-muted-foreground/40 hover:text-emerald-400 hover:bg-emerald-500/5',
            )}
            aria-label={saved ? 'Unsave job' : 'Save job'}
          >
            {saved ? <CheckCircle2 className="h-3.5 w-3.5" /> : <ThumbsUp className="h-3.5 w-3.5" />}
          </button>
          <button
            onClick={(e) => { e.preventDefault(); setDismissed(true); onDismiss(job.id) }}
            className={cn(
              'rounded-lg p-1.5 transition-colors',
              dismissed
                ? 'bg-red-500/10 text-red-400'
                : 'text-muted-foreground/40 hover:text-red-400 hover:bg-red-500/5',
            )}
            aria-label="Dismiss job"
          >
            <ThumbsDown className="h-3.5 w-3.5" />
          </button>
          <a
            href={safeUrl(job.url)}
            target="_blank"
            rel="noopener noreferrer"
            className="rounded-lg p-1.5 text-muted-foreground/40 hover:text-foreground hover:bg-muted transition-colors"
            aria-label="Open job posting in new tab"
          >
            <ExternalLink className="h-3.5 w-3.5" />
          </a>
        </div>
      </div>
    </motion.div>
  )
}
