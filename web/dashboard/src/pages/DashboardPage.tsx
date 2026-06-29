import { useState, useEffect, useCallback, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Stats, fetchStats, Profile, fetchProfile, PipelineStatus, fetchPipelineStatus } from '../lib/api'
import { useToast } from '../lib/ToastContext'
import StatCard from '../components/StatCard'
import SourceBreakdown from '../components/SourceBreakdown'
import TopCompanies from '../components/TopCompanies'
import PipelineControls from '../components/PipelineControls'
import RecentActivity from '../components/RecentActivity'
import SparkChart from '../components/SparkChart'
import SourceGlowGrid from '../components/SourceGlowGrid'
import SourceStatusTicker from '../components/SourceStatusTicker'
import { Link } from 'react-router-dom'
import {
  Briefcase, Filter, MapPin, CalendarDays,
  BarChart3, Target, Layers, User, ArrowRight, Sparkles,
} from 'lucide-react'

const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: 0.06, delayChildren: 0.1 },
  },
}

const itemVariants = {
  hidden: { opacity: 0, y: 16 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.4, ease: [0.25, 0.46, 0.45, 0.94] as [number, number, number, number] },
  },
}

export default function DashboardPage() {
  const { addToast } = useToast()
  const [stats, setStats] = useState<Stats | null>(null)
  const [profile, setProfile] = useState<Profile | null>(null)
  const [loading, setLoading] = useState(true)
  const [profileLoading, setProfileLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Pipeline live state
  const [pipelineStatus, setPipelineStatus] = useState<PipelineStatus | null>(null)
  const [justCompleted, setJustCompleted] = useState(false)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const loadStats = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await fetchStats()
      setStats(data)
    } catch {
      setError('Could not connect to the backend. Make sure the server is running.')
      setStats(null)
    } finally {
      setLoading(false)
    }
  }, [])

  const loadProfile = useCallback(async () => {
    setProfileLoading(true)
    try {
      const data = await fetchProfile()
      setProfile(data)
    } catch {
      setProfile(null)
    } finally {
      setProfileLoading(false)
    }
  }, [])

  // ── On mount: check if a pipeline is already running (survives refresh) ──
  useEffect(() => {
    loadStats()
    loadProfile()

    // Poll once to check for a running pipeline
    fetchPipelineStatus()
      .then(status => {
        if (status.running) {
          setPipelineStatus(status)
        }
      })
      .catch(() => { /* silently ignore */ })
  }, [loadStats, loadProfile])

  const profileReady: boolean = !!(profile && profile.target_roles && profile.target_roles.length > 0)

  const totalJobsTrend = stats?.recent_runs?.map(r => r.total_jobs) ?? []
  const indiaTrend = stats?.recent_runs?.map(r => r.india_jobs) ?? []

  // Track completion for flash animation
  useEffect(() => {
    if (pipelineStatus && !pipelineStatus.running && pipelineStatus.phase === 'complete') {
      setJustCompleted(true)
      const t = setTimeout(() => setJustCompleted(false), 8000)
      return () => clearTimeout(t)
    }
  }, [pipelineStatus])

  // ── Handle status ticks from PipelineControls poller ──
  const handleStatusTick = useCallback((status: PipelineStatus) => {
    setPipelineStatus(status)
  }, [])

  // ── Cleanup polling on unmount ──
  useEffect(() => {
    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current)
      }
    }
  }, [])

  const isPipelineLive = pipelineStatus?.running ?? false

  return (
    <main className="mx-auto max-w-[1440px] px-4 sm:px-6 lg:px-8 pb-16">
      {/* Error banner */}
      <AnimatePresence>
        {error && (
          <motion.div
            initial={{ opacity: 0, y: -10, height: 0 }}
            animate={{ opacity: 1, y: 0, height: 'auto' }}
            exit={{ opacity: 0, y: -10, height: 0 }}
            className="mt-6 rounded-xl border border-destructive/30 bg-destructive/10 px-5 py-3.5"
          >
            <div className="flex items-start gap-3">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-destructive/20">
                <span className="font-display text-lg font-black text-destructive">!</span>
              </div>
              <div>
                <p className="font-display text-sm font-bold text-destructive">Connection Error</p>
                <p className="mt-0.5 font-mono text-xs text-destructive/80">{error}</p>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Profile prompt */}
      <AnimatePresence>
        {!profileLoading && !profileReady && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ delay: 0.2 }}
            className="mt-6 rounded-2xl border-2 border-brand-blue/20 bg-gradient-to-r from-brand-blue/[0.04] to-brand-violet/[0.04] p-5 sm:p-6"
          >
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
              <div className="flex items-start gap-3">
                <motion.div
                  whileHover={{ scale: 1.1, rotate: -5 }}
                  className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-brand-blue/10"
                >
                  <User className="h-5 w-5 text-brand-blue" />
                </motion.div>
                <div>
                  <h3 className="font-display text-lg font-bold">Welcome! Let's set up your profile</h3>
                  <p className="mt-1 text-sm text-muted-foreground leading-relaxed">
                    Tell us the roles and locations you're targeting. We'll use this to find and score the best jobs for you.
                  </p>
                </div>
              </div>
              <motion.div whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }}>
                <Link
                  to="/profile"
                  className="inline-flex shrink-0 items-center gap-2 rounded-xl bg-gradient-brand px-5 py-2.5 font-display text-sm font-bold text-primary-foreground shadow-lg shadow-brand-blue/25 transition-shadow hover:shadow-xl hover:shadow-brand-blue/30"
                >
                  <Sparkles className="h-4 w-4" />
                  Set Up Profile <ArrowRight className="h-4 w-4" />
                </Link>
              </motion.div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Empty state — show when jobs are being collected for the first time */}
      <AnimatePresence>
        {!loading && !error && stats && stats.total === 0 && profileReady && (
          <motion.div
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-6 rounded-xl border border-amber-500/20 bg-amber-50/80 dark:bg-amber-950/20 px-5 py-3.5"
          >
            <div className="flex items-center gap-3">
              <Sparkles className="h-5 w-5 text-amber-600 dark:text-amber-400" />
              <p className="font-mono text-sm font-medium text-amber-800 dark:text-amber-200">
                Your job board is being populated. The collection runs automatically every 4 hours. Check back soon!
              </p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Source Status Ticker (during runs) */}
      <AnimatePresence>
        {(isPipelineLive || justCompleted) && pipelineStatus?.sources && (
          <div className="mt-4">
            <SourceStatusTicker
              sources={pipelineStatus.sources}
              running={isPipelineLive}
              elapsedSeconds={pipelineStatus.elapsed_seconds}
            />
          </div>
        )}
      </AnimatePresence>

      {/* Overview Section */}
      <motion.section
        variants={containerVariants}
        initial="hidden"
        animate="visible"
        className="mb-10 mt-8"
      >
        <motion.div variants={itemVariants} className="mb-5 flex items-center gap-3">
          <motion.div
            initial={{ scaleY: 0 }}
            animate={{ scaleY: 1 }}
            transition={{ delay: 0.3, duration: 0.4 }}
            className="h-8 w-1 rounded-full bg-gradient-brand origin-bottom"
          />
          <h2 className="font-display text-2xl font-bold tracking-tight text-foreground sm:text-3xl">
            Your Job Board
          </h2>
          {stats && stats.newest_scrape && (
            <motion.span
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              className="rounded-full bg-secondary px-3 py-1 font-mono text-[10px] font-semibold text-muted-foreground"
            >
              Last updated {new Date(stats.newest_scrape!).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })}
            </motion.span>
          )}
        </motion.div>

        {/* Bento grid of stat cards */}
        <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4 xl:grid-cols-6">
          <StatCard label="Jobs Found" value={stats?.total ?? 0} icon={<Briefcase className="h-4 w-4" />} trend={totalJobsTrend} loading={loading} variant="default" delay={0.1} className="col-span-2 sm:col-span-1 lg:col-span-1 xl:col-span-1" />
          <StatCard label="Unique Roles" value={stats?.unique ?? 0} icon={<Filter className="h-4 w-4" />} loading={loading} variant="secondary" delay={0.15} />
          <StatCard label="India Based" value={stats?.india_count ?? 0} icon={<MapPin className="h-4 w-4" />} trend={indiaTrend} loading={loading} variant="accent" delay={0.2} />
          <StatCard label="Added Today" value={stats?.today_jobs ?? 0} icon={<CalendarDays className="h-4 w-4" />} loading={loading} variant="success" highlight delay={0.25} />
          <StatCard label="Strong Matches" value={stats?.profile_strong ?? 0} icon={<Target className="h-4 w-4" />} loading={loading} variant="brand" className="hidden xl:flex" delay={0.3} />
          <StatCard label="Reviewed" value={stats?.classified ?? 0} icon={<Layers className="h-4 w-4" />} loading={loading} variant="secondary" className="hidden xl:flex" delay={0.35} />
        </div>
      </motion.section>

      {/* Main content grid */}
      <div className="grid gap-6 lg:grid-cols-3">
        {/* Left column — 2/3 width */}
        <motion.div
          variants={containerVariants}
          initial="hidden"
          animate="visible"
          className="space-y-6 lg:col-span-2"
        >
          {/* Jobs by Source */}
          <motion.section
            variants={itemVariants}
            className="rounded-xl border bg-card p-5 shadow-sm transition-shadow duration-300 hover:shadow-md sm:p-6"
          >
            <div className="mb-5 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <motion.div
                  whileHover={{ scale: 1.1, rotate: -3 }}
                  className="flex h-9 w-9 items-center justify-center rounded-xl bg-brand-blue/10"
                >
                  <BarChart3 className="h-4.5 w-4.5 text-brand-blue" />
                </motion.div>
                <div>
                  <h3 className="font-display text-lg font-bold tracking-tight">Where Your Jobs Come From</h3>
                  <p className="font-mono text-xs text-muted-foreground">Breakdown by platform — more sources mean more opportunities</p>
                </div>
              </div>
            </div>
            <SourceBreakdown sources={stats?.by_source ?? {}} total={stats?.total ?? 0} loading={loading} />
          </motion.section>

          {/* Pipeline Controls */}
          <motion.div variants={itemVariants}>
            <PipelineControls
              onRunComplete={loadStats}
              profileReady={profileReady}
              onStatusTick={handleStatusTick}
              isPipelineRunning={isPipelineLive}
            />
          </motion.div>

          {/* Source Glow Grid — now inside left column, matching width */}
          <SourceGlowGrid
            sources={pipelineStatus?.sources ?? null}
            running={isPipelineLive}
            justCompleted={justCompleted}
          />

          {/* Recent Activity — now inside left column, matching width */}
          <motion.div variants={itemVariants}>
            <RecentActivity runs={stats?.recent_runs ?? []} loading={loading} />
          </motion.div>
        </motion.div>

        {/* Right column — 1/3 width */}
        <motion.div
          variants={containerVariants}
          initial="hidden"
          animate="visible"
          className="space-y-6"
        >
          <motion.section
            variants={itemVariants}
            className="rounded-xl border bg-card p-5 shadow-sm transition-shadow duration-300 hover:shadow-md sm:p-6"
          >
            <div className="mb-4 flex items-center gap-3">
              <motion.div
                whileHover={{ scale: 1.1 }}
                className="flex h-9 w-9 items-center justify-center rounded-xl bg-brand-violet/10"
              >
                <CalendarDays className="h-4.5 w-4.5 text-brand-violet" />
              </motion.div>
              <div>
                <h3 className="font-display text-base font-bold tracking-tight">Growth Over Time</h3>
                <p className="font-mono text-xs text-muted-foreground">Your collection history</p>
              </div>
            </div>
            <SparkChart runs={stats?.recent_runs ?? []} loading={loading} />
          </motion.section>

          <motion.section
            variants={itemVariants}
            className="rounded-xl border bg-card p-5 shadow-sm transition-shadow duration-300 hover:shadow-md sm:p-6"
          >
            <div className="mb-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <motion.div
                  whileHover={{ scale: 1.1 }}
                  className="flex h-9 w-9 items-center justify-center rounded-xl bg-emerald-100 dark:bg-emerald-900/30"
                >
                  <Briefcase className="h-4.5 w-4.5 text-emerald-600 dark:text-emerald-400" />
                </motion.div>
                <div>
                  <h3 className="font-display text-base font-bold tracking-tight">Who's Hiring</h3>
                  <p className="font-mono text-xs text-muted-foreground">Companies with the most openings</p>
                </div>
              </div>
            </div>
            <TopCompanies companies={stats?.top_companies ?? []} loading={loading} />
          </motion.section>

          {stats?.top_india_locations && stats.top_india_locations.length > 0 && (
            <motion.section
              variants={itemVariants}
              className="rounded-xl border bg-card p-5 shadow-sm transition-shadow duration-300 hover:shadow-md sm:p-6"
            >
              <div className="mb-4 flex items-center gap-3">
                <motion.div
                  whileHover={{ scale: 1.1 }}
                  className="flex h-9 w-9 items-center justify-center rounded-xl bg-amber-100 dark:bg-amber-900/30"
                >
                  <MapPin className="h-4.5 w-4.5 text-amber-600 dark:text-amber-400" />
                </motion.div>
                <div>
                  <h3 className="font-display text-base font-bold tracking-tight">India Hotspots</h3>
                  <p className="font-mono text-xs text-muted-foreground">Top job markets near you</p>
                </div>
              </div>
              <div className="space-y-1.5">
                {stats.top_india_locations.map((loc, i) => (
                  <motion.div
                    key={loc.location}
                    initial={{ opacity: 0, x: -8 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: i * 0.04 }}
                    whileHover={{ x: 4 }}
                    className="flex items-center justify-between rounded-xl px-3 py-2.5 transition-colors hover:bg-secondary/50"
                  >
                    <span className="text-sm font-medium">{loc.location}</span>
                    <span className="font-mono text-sm font-semibold tabular-nums text-muted-foreground">
                      {loc.count.toLocaleString()}
                    </span>
                  </motion.div>
                ))}
              </div>
            </motion.section>
          )}
        </motion.div>
      </div>
    </main>
  )
}
