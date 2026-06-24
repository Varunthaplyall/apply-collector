import { motion } from 'framer-motion'
import { RunRecord } from '@/lib/api'
import { cn, timeAgo } from '@/lib/utils'
import { Activity, Clock, Zap } from 'lucide-react'

interface RecentActivityProps {
  runs: RunRecord[]
  loading?: boolean
}

export default function RecentActivity({ runs, loading }: RecentActivityProps) {
  return (
    <motion.section
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.2 }}
      className="group rounded-xl border bg-card p-5 shadow-sm transition-shadow duration-300 hover:shadow-md sm:p-6"
    >
      <div className="mb-5 flex items-center gap-3">
        <motion.div
          whileHover={{ scale: 1.1, rotate: -5 }}
          className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-brand shadow-sm"
        >
          <Activity className="h-4.5 w-4.5 text-primary-foreground" />
        </motion.div>
        <div>
          <h3 className="font-display text-lg font-bold tracking-tight">
            Your Run History
          </h3>
          <p className="font-mono text-xs text-muted-foreground">
            Past collections and what they found for you
          </p>
        </div>
      </div>

      {loading ? (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="flex gap-4">
              <div className="shimmer-bg h-10 w-10 rounded-full" />
              <div className="flex-1 space-y-2">
                <div className="shimmer-bg h-4 w-32 rounded" />
                <div className="shimmer-bg h-3 w-full rounded" />
              </div>
            </div>
          ))}
        </div>
      ) : runs.length === 0 ? (
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          className="flex flex-col items-center justify-center py-10 text-muted-foreground"
        >
          <Clock className="mb-3 h-8 w-8 opacity-30" />
          <p className="font-mono text-sm">Nothing here yet</p>
          <p className="mt-1 text-xs">Your first pipeline run will show up here</p>
        </motion.div>
      ) : (
        <div className="relative">
          {/* Timeline line */}
          <div className="absolute bottom-0 left-[19px] top-2 w-px bg-gradient-to-b from-primary/50 via-border to-transparent" />

          <div className="space-y-4">
            {runs.map((run, idx) => (
              <motion.div
                key={run.run_date}
                initial={{ opacity: 0, x: -16 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: idx * 0.08, duration: 0.4 }}
                className="relative flex gap-4"
              >
                {/* Timeline dot */}
                <motion.div
                  whileHover={{ scale: 1.15 }}
                  className={cn(
                    'relative z-10 mt-1 flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full border-2 transition-all duration-300',
                    idx === 0
                      ? 'border-brand-blue bg-brand-blue/10 shadow-sm shadow-brand-blue/20'
                      : 'border-muted-foreground/20 bg-card',
                    'group-hover:border-brand-blue/50',
                  )}
                >
                  <Zap className={cn(
                    'h-4 w-4 transition-colors',
                    idx === 0 ? 'text-brand-blue' : 'text-muted-foreground',
                  )} />
                </motion.div>

                {/* Content */}
                <div className="flex-1 pb-4">
                  <div className="flex items-center gap-3 flex-wrap">
                    <time className="font-mono text-xs font-semibold text-muted-foreground">
                      {timeAgo(run.run_date)}
                    </time>
                    <span className="font-mono text-xs text-muted-foreground/60">
                      {new Date(run.run_date).toLocaleDateString('en-US', {
                        month: 'short',
                        day: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </span>
                    <span className="ml-auto flex items-center gap-1 rounded-full bg-secondary px-2 py-0.5 font-mono text-[10px] font-semibold tabular-nums text-muted-foreground">
                      <Clock className="h-3 w-3" />
                      {run.run_time_s.toFixed(1)}s
                    </span>
                  </div>

                  {/* Mini stat grid */}
                  <div className="mt-2 grid grid-cols-4 gap-2 sm:grid-cols-5">
                    <MiniStat label="Total" value={run.total_jobs} />
                    <MiniStat label="Unique" value={run.unique_jobs} />
                    <MiniStat label="India" value={run.india_jobs} highlight />
                    <MiniStat label="GH" value={run.gh_jobs} />
                    <MiniStat label="Lever" value={run.lever_jobs} />
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      )}
    </motion.section>
  )
}

function MiniStat({ label, value, highlight }: { label: string; value: number; highlight?: boolean }) {
  return (
    <motion.div
      whileHover={{ scale: 1.04 }}
      className={cn(
        'rounded-lg border px-2.5 py-1.5 transition-colors hover:bg-secondary/40',
        highlight && 'border-amber-500/20 bg-amber-50/50 dark:bg-amber-900/10',
      )}
    >
      <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
        {label}
      </p>
      <p className={cn(
        'mt-0.5 font-mono text-sm font-bold tabular-nums',
        highlight ? 'text-amber-700 dark:text-amber-400' : 'text-foreground',
      )}>
        {value.toLocaleString()}
      </p>
    </motion.div>
  )
}
