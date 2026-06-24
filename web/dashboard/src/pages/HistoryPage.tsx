import { useState, useEffect, useCallback } from 'react'
import { motion } from 'framer-motion'
import { cn, timeAgo } from '../lib/utils'
import { fetchRunHistory, RunRecord } from '../lib/api'
import { History, Clock, Zap, Database, TrendingUp } from 'lucide-react'

const easeOut: [number, number, number, number] = [0.25, 0.46, 0.45, 0.94]

const timelineVariants = {
  hidden: { opacity: 0, x: -20 },
  visible: (i: number) => ({
    opacity: 1,
    x: 0,
    transition: { delay: i * 0.06, duration: 0.4, ease: easeOut },
  }),
}

export default function HistoryPage() {
  const [runs, setRuns] = useState<RunRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try { setRuns(await fetchRunHistory()) }
    catch (err) { setError(err instanceof Error ? err.message : 'Failed to load') }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  return (
    <main className="mx-auto max-w-[1440px] px-4 sm:px-6 lg:px-8 pb-16">
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
            Run History
          </h2>
          {!loading && (
            <motion.span
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              className="rounded-full bg-secondary px-3 py-1 font-mono text-[10px] font-semibold text-muted-foreground"
            >
              {runs.length} runs
            </motion.span>
          )}
        </div>
      </motion.section>

      {loading ? (
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.06 }}
              className="shimmer-bg h-20 rounded-xl border"
            />
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
            onClick={load}
            className="mt-4 rounded-xl bg-gradient-brand px-5 py-2.5 font-display text-sm font-bold text-primary-foreground shadow-lg"
          >
            Retry
          </motion.button>
        </motion.div>
      ) : runs.length === 0 ? (
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          className="flex flex-col items-center justify-center rounded-xl border bg-card py-16 text-muted-foreground"
        >
          <History className="mb-3 h-10 w-10 opacity-20" />
          <p className="font-mono text-sm">No runs recorded yet</p>
          <p className="mt-1 text-xs">Trigger a collection from the Dashboard to see history</p>
        </motion.div>
      ) : (
        <div className="relative">
          {/* Timeline line */}
          <div className="absolute bottom-0 left-[27px] top-6 w-px bg-gradient-to-b from-brand-blue/50 via-border to-transparent" />

          <div className="space-y-4">
            {runs.map((run, idx) => (
              <motion.div
                key={run.run_date}
                custom={idx}
                variants={timelineVariants}
                initial="hidden"
                animate="visible"
                className="relative flex gap-5"
              >
                {/* Timeline dot */}
                <motion.div
                  whileHover={{ scale: 1.15, boxShadow: '0 0 16px hsl(var(--brand-blue)/0.3)' }}
                  className={cn(
                    'relative z-10 mt-1 flex h-14 w-14 flex-shrink-0 items-center justify-center rounded-full border-2 transition-all',
                    idx === 0
                      ? 'border-brand-blue bg-brand-blue/10 shadow-sm shadow-brand-blue/15'
                      : 'border-muted-foreground/20 bg-card',
                  )}
                >
                  {idx === 0
                    ? <Zap className="h-5 w-5 text-brand-blue" />
                    : <Database className="h-5 w-5 text-muted-foreground/60" />
                  }
                </motion.div>

                {/* Content card */}
                <motion.div
                  whileHover={{ y: -2 }}
                  className="flex-1 rounded-xl border bg-card p-5 shadow-sm transition-shadow hover:shadow-md"
                >
                  <div className="flex items-center gap-3 flex-wrap mb-3">
                    <time className="font-mono text-sm font-bold text-foreground">
                      {new Date(run.run_date).toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' })}
                    </time>
                    <time className="font-mono text-xs text-muted-foreground">
                      {new Date(run.run_date).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })}
                    </time>
                    <span className="font-mono text-xs text-muted-foreground/60">{timeAgo(run.run_date)}</span>
                    <span className="ml-auto flex items-center gap-1.5 rounded-full bg-secondary px-2.5 py-1 font-mono text-[10px] font-bold tabular-nums text-muted-foreground">
                      <Clock className="h-3 w-3" /> {run.run_time_s.toFixed(1)}s
                    </span>
                  </div>
                  <div className="grid grid-cols-3 gap-2 sm:grid-cols-5 lg:grid-cols-8">
                    <RunStat label="Total" value={run.total_jobs} />
                    <RunStat label="Unique" value={run.unique_jobs} />
                    <RunStat label="India" value={run.india_jobs} accent />
                    <RunStat label="Greenhouse" value={run.gh_jobs} />
                    <RunStat label="Lever" value={run.lever_jobs} />
                    <RunStat label="Workday" value={run.workday_jobs} />
                    <RunStat label="Cutshort" value={run.cutshort_jobs} />
                    <RunStat label="Dupes" value={run.total_jobs - run.unique_jobs} muted />
                  </div>
                </motion.div>
              </motion.div>
            ))}
          </div>
        </div>
      )}

      {/* Summary stats */}
      {runs.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3, duration: 0.5 }}
          className="mt-8 rounded-xl border bg-card p-5 shadow-sm"
        >
          <div className="flex items-center gap-3 mb-4">
            <motion.div
              whileHover={{ rotate: 15 }}
              className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-brand"
            >
              <TrendingUp className="h-5 w-5 text-primary-foreground" />
            </motion.div>
            <h3 className="font-display text-base font-bold">Summary</h3>
          </div>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <SummaryStat label="Total Runs" value={runs.length} />
            <SummaryStat label="Avg Jobs/Run" value={Math.round(runs.reduce((a, r) => a + r.total_jobs, 0) / runs.length)} />
            <SummaryStat label="Avg Time" value={`${(runs.reduce((a, r) => a + r.run_time_s, 0) / runs.length).toFixed(1)}s`} />
            <SummaryStat label="First Run" value={new Date(runs[runs.length - 1].run_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })} />
          </div>
        </motion.div>
      )}
    </main>
  )
}

function RunStat({ label, value, accent, muted }: { label: string; value: number; accent?: boolean; muted?: boolean }) {
  return (
    <motion.div
      whileHover={{ scale: 1.05 }}
      className={cn(
        'rounded-lg border px-3 py-2 transition-colors hover:bg-secondary/40',
        accent && 'border-amber-500/20 bg-amber-50/50 dark:bg-amber-900/10',
      )}
    >
      <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">{label}</p>
      <p className={cn(
        'mt-0.5 font-mono text-sm font-bold tabular-nums',
        accent ? 'text-amber-700 dark:text-amber-400' : muted ? 'text-muted-foreground/60' : 'text-foreground',
      )}>
        {value.toLocaleString()}
      </p>
    </motion.div>
  )
}

function SummaryStat({ label, value }: { label: string; value: string | number }) {
  return (
    <motion.div
      whileHover={{ scale: 1.02 }}
      className="rounded-xl border bg-background px-4 py-3 transition-colors hover:bg-secondary/20"
    >
      <p className="font-mono text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">{label}</p>
      <p className="mt-1 font-display text-xl font-bold text-foreground">{value}</p>
    </motion.div>
  )
}
