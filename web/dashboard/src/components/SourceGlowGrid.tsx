import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { cn } from '@/lib/utils'
import { getSourceMeta, SOURCE_LIST } from '@/lib/sourceMeta'
import type { SourceState } from '@/lib/api'
import { CheckCircle2, XCircle, Loader2, Sparkles, Zap } from 'lucide-react'

interface SourceGlowGridProps {
  /** Per-source pipeline status; null or undefined means no data (idle grid) */
  sources: SourceState[] | null
  /** True while a pipeline run is active */
  running: boolean
  /** True when a run just completed (for success pulse + brief jubilant state) */
  justCompleted: boolean
}

/** Color map: tailwind color name → actual CSS color values for glow effects.
 *  Kept subtle — just enough to feel alive, not neon.  */
const GLOW_COLORS: Record<string, { box: string; bg: string; border: string }> = {
  emerald:  { box: 'rgba(16,185,129,0.22)',  bg: 'rgba(16,185,129,0.04)',  border: 'rgb(16,185,129)' },
  blue:     { box: 'rgba(59,130,246,0.22)',   bg: 'rgba(59,130,246,0.04)',   border: 'rgb(59,130,246)' },
  violet:   { box: 'rgba(139,92,246,0.22)',   bg: 'rgba(139,92,246,0.04)',   border: 'rgb(139,92,246)' },
  sky:      { box: 'rgba(14,165,233,0.22)',   bg: 'rgba(14,165,233,0.04)',   border: 'rgb(14,165,233)' },
  amber:    { box: 'rgba(245,158,11,0.22)',   bg: 'rgba(245,158,11,0.04)',   border: 'rgb(245,158,11)' },
  rose:     { box: 'rgba(244,63,94,0.22)',    bg: 'rgba(244,63,94,0.04)',    border: 'rgb(244,63,94)' },
  teal:     { box: 'rgba(20,184,166,0.22)',   bg: 'rgba(20,184,166,0.04)',   border: 'rgb(20,184,166)' },
  orange:   { box: 'rgba(249,115,22,0.22)',   bg: 'rgba(249,115,22,0.04)',   border: 'rgb(249,115,22)' },
  cyan:     { box: 'rgba(6,182,212,0.22)',    bg: 'rgba(6,182,212,0.04)',    border: 'rgb(6,182,212)' },
  indigo:   { box: 'rgba(99,102,241,0.22)',   bg: 'rgba(99,102,241,0.04)',   border: 'rgb(99,102,241)' },
  pink:     { box: 'rgba(236,72,153,0.22)',   bg: 'rgba(236,72,153,0.04)',   border: 'rgb(236,72,153)' },
  lime:     { box: 'rgba(132,204,22,0.22)',   bg: 'rgba(132,204,22,0.04)',   border: 'rgb(132,204,22)' },
  fuchsia:  { box: 'rgba(217,70,239,0.22)',   bg: 'rgba(217,70,239,0.04)',   border: 'rgb(217,70,239)' },
  yellow:   { box: 'rgba(250,204,21,0.22)',   bg: 'rgba(250,204,21,0.04)',   border: 'rgb(250,204,21)' },
  gray:     { box: 'rgba(156,163,175,0.15)',  bg: 'rgba(156,163,175,0.03)',  border: 'rgb(156,163,175)' },
}

function getGlow(color: string) {
  return GLOW_COLORS[color] ?? GLOW_COLORS.gray
}

/** A single source card in the grid — animated like a building in a night skyline. */
function SourceCard({
  source,
  status,
  jobsFound,
  error,
  running,
  justCompleted,
}: {
  source: string
  status?: string
  jobsFound?: number
  error?: string | null
  running: boolean
  justCompleted: boolean
}) {
  const meta = getSourceMeta(source)
  const glow = getGlow(meta.color)
  const isRunning = status === 'running'
  const isCompleted = status === 'completed'
  const isError = status === 'error'
  const isPending = !status || status === 'pending'
  const isActive = isRunning || isCompleted || isError

  // Flash state for completion celebration
  const [flash, setFlash] = useState(false)
  useEffect(() => {
    if (isCompleted && justCompleted) {
      setFlash(true)
      const t = setTimeout(() => setFlash(false), 1200)
      return () => clearTimeout(t)
    }
  }, [isCompleted, justCompleted])

  return (
    <motion.div
      layout
      initial={{ opacity: 0, scale: 0.92 }}
      animate={{
        opacity: 1,
        scale: 1,
        boxShadow: isActive
          ? `0 0 8px ${glow.box}, 0 0 18px ${glow.bg}`
          : 'none',
      }}
      transition={{ duration: 0.4, ease: 'easeOut' }}
      className={cn(
        'relative overflow-hidden rounded-xl border p-4 transition-all duration-700',
        isActive
          ? 'bg-card shadow-lg'
          : 'bg-card/30 border-border/20 opacity-50 hover:opacity-70 hover:border-border/40',
        isRunning && 'border-opacity-80',
        isCompleted && !flash && 'border-emerald-500/30',
        isError && 'border-red-500/30',
        flash && 'border-emerald-400 shadow-emerald-500/30',
      )}
      style={
        isRunning
          ? {
              borderColor: glow.border,
              borderWidth: '1.5px',
            }
          : undefined
      }
    >
      {/* Running: subtle shimmer wash */}
      {isRunning && (
        <motion.div
          className="absolute inset-0 rounded-xl"
          animate={{ opacity: [0.3, 0.7, 0.3] }}
          transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
          style={{
            background: `linear-gradient(135deg, ${glow.bg}, transparent 60%)`,
          }}
        />
      )}

      {/* Running: scanning line */}
      {isRunning && (
        <motion.div
          className="absolute left-0 right-0 h-[1px] opacity-25 pointer-events-none"
          style={{ background: glow.border }}
          animate={{ top: ['0%', '100%'] }}
          transition={{ duration: 3, repeat: Infinity, ease: 'linear' }}
        />
      )}

      {/* Running: subtle pulsing glow in background */}
      {isRunning && (
        <motion.div
          className="absolute inset-0 rounded-xl"
          animate={{ opacity: [0, 0.12, 0] }}
          transition={{ duration: 2.5, repeat: Infinity, ease: 'easeInOut' }}
          style={{
            background: `radial-gradient(circle at center, ${glow.box}, transparent 65%)`,
          }}
        />
      )}

      {/* Content */}
      <div className="relative z-10 flex flex-col items-center gap-2">
        {/* Source icon area */}
        <motion.div
          animate={
            isRunning
              ? { scale: [1, 1.06, 1], opacity: [0.85, 1, 0.85] }
              : isCompleted && flash
              ? { scale: [0.8, 1.3, 1], rotate: [0, 5, 0] }
              : {}
          }
          transition={
            isRunning
              ? { duration: 2, repeat: Infinity, ease: 'easeInOut' }
              : { duration: 0.5 }
          }
          className={cn(
            'flex h-10 w-10 items-center justify-center rounded-xl text-lg font-black shadow-sm transition-all',
            isRunning && 'text-white',
            isCompleted && !flash && 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400',
            isError && 'bg-red-500/10 text-red-600 dark:text-red-400',
            isPending && 'bg-muted text-muted-foreground',
          )}
          style={
            isRunning
              ? {
                  background: `linear-gradient(135deg, ${glow.border}, ${glow.border})`,
                  boxShadow: `0 0 6px ${glow.box}`,
                }
              : flash
              ? { background: 'linear-gradient(135deg, #10b981, #34d399)' }
              : undefined
          }
        >
          {isRunning ? (
            <Loader2 className="h-5 w-5 animate-spin" />
          ) : isCompleted ? (
            <CheckCircle2 className="h-5 w-5" />
          ) : isError ? (
            <XCircle className="h-5 w-5" />
          ) : (
            <Zap className="h-4 w-4 opacity-30" />
          )}
        </motion.div>

        {/* Label */}
        <span
          className={cn(
            'font-display text-sm font-semibold tracking-tight transition-colors text-center leading-tight',
            isActive ? 'text-foreground' : 'text-muted-foreground',
          )}
        >
          {meta.label}
        </span>

        {/* Status label */}
        <AnimatePresence mode="wait">
          {isRunning && (
            <motion.span
              key="running"
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              className="font-mono text-[10px] font-medium"
              style={{ color: glow.border }}
            >
              Collecting…
            </motion.span>
          )}
          {isCompleted && (
            <motion.span
              key="completed"
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              className="font-mono text-[10px] font-bold text-emerald-600 dark:text-emerald-400"
            >
              +{jobsFound ?? 0} jobs
            </motion.span>
          )}
          {isError && (
            <motion.span
              key="error"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="font-mono text-[10px] font-medium text-red-500"
              title={error ?? 'Unknown error'}
            >
              Failed
            </motion.span>
          )}
          {isPending && !running && (
            <span className="font-mono text-[10px] text-muted-foreground/40">idle</span>
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  )
}

export default function SourceGlowGrid({ sources, running, justCompleted }: SourceGlowGridProps) {
  // Build a lookup: source name → state
  const stateMap: Record<string, { status: string; jobsFound: number; error?: string | null }> = {}
  if (sources) {
    for (const s of sources) {
      stateMap[s.name] = {
        status: s.status,
        jobsFound: s.jobs_found ?? 0,
        error: s.error ?? null,
      }
    }
  }

  const hasEverRun = sources !== null && sources.length > 0

  return (
    <motion.section
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.35, duration: 0.5 }}
      className="mt-6 rounded-xl border bg-card p-5 shadow-sm sm:p-6"
    >
      {/* Header */}
      <div className="mb-4 flex items-center gap-3">
        <motion.div
          animate={running ? { rotate: [0, -5, 5, 0] } : {}}
          transition={{ duration: 3, repeat: Infinity }}
          className="flex h-9 w-9 items-center justify-center rounded-xl bg-brand-violet/10"
        >
          <Sparkles className="h-4.5 w-4.5 text-brand-violet" />
        </motion.div>
        <div>
          <h3 className="font-display text-lg font-bold tracking-tight">
            Live Source Monitor
          </h3>
          <p className="font-mono text-xs text-muted-foreground">
            {running
              ? 'Sources light up as we scan them for your jobs'
              : justCompleted
              ? 'All done! Here\'s what each source found for you'
              : hasEverRun
              ? 'Everything\'s quiet — sources are ready when you are'
              : 'Hit Run Pipeline and watch each source come alive'}
          </p>
        </div>
        {running && (
          <motion.span
            animate={{ opacity: [1, 0.5, 1] }}
            transition={{ duration: 1, repeat: Infinity }}
            className="ml-auto font-mono text-[10px] font-medium text-brand-violet"
          >
            LIVE
          </motion.span>
        )}
      </div>

      {/* Grid */}
      <div className="grid grid-cols-3 gap-2 sm:gap-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-7">
        {SOURCE_LIST.map((meta) => {
          const state = stateMap[meta.name]
          return (
            <SourceCard
              key={meta.name}
              source={meta.name}
              status={state?.status}
              jobsFound={state?.jobsFound}
              error={state?.error}
              running={running}
              justCompleted={justCompleted}
            />
          )
        })}
      </div>
    </motion.section>
  )
}
