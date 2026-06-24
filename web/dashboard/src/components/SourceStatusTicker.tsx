import { motion, AnimatePresence } from 'framer-motion'
import { cn } from '@/lib/utils'
import { getSourceMeta, ACTIVE_PIPELINE_SOURCES } from '@/lib/sourceMeta'
import type { SourceState } from '@/lib/api'
import { CheckCircle2, Loader2, Clock, XCircle } from 'lucide-react'

interface SourceStatusTickerProps {
  sources: SourceState[] | null
  running: boolean
  elapsedSeconds: number
}

function SourceChip({ state }: { state: SourceState }) {
  const meta = getSourceMeta(state.name)
  const isRunning = state.status === 'running'
  const isCompleted = state.status === 'completed'
  const isError = state.status === 'error'

  return (
    <motion.div
      layout
      initial={{ opacity: 0, x: -12 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: 12 }}
      transition={{ duration: 0.25 }}
      className={cn(
        'inline-flex items-center gap-2 shrink-0 rounded-full px-3 py-1.5 border text-xs font-semibold transition-colors',
        isRunning && 'border-brand-blue/30 bg-brand-blue/5 text-brand-blue',
        isCompleted && 'border-emerald-500/20 bg-emerald-500/5 text-emerald-600 dark:text-emerald-400',
        isError && 'border-red-500/20 bg-red-500/5 text-red-500',
        !isRunning && !isCompleted && !isError && 'border-border/40 bg-muted/20 text-muted-foreground/60',
      )}
    >
      {/* Colored dot */}
      <span className="relative flex h-2 w-2">
        {isRunning && (
          <motion.span
            className="absolute inset-0 rounded-full bg-brand-blue"
            animate={{ scale: [1, 1.8, 1], opacity: [1, 0.4, 1] }}
            transition={{ duration: 1.2, repeat: Infinity, ease: 'easeInOut' }}
          />
        )}
        <span
          className={cn(
            'relative inline-flex h-2 w-2 rounded-full',
            isRunning && 'bg-brand-blue',
            isCompleted && 'bg-emerald-500',
            isError && 'bg-red-500',
            !isRunning && !isCompleted && !isError && 'bg-muted-foreground/30',
          )}
        />
      </span>

      <span>{meta.label}</span>

      {/* Status icon */}
      {isRunning && <Loader2 className="h-3 w-3 animate-spin" />}
      {isCompleted && <CheckCircle2 className="h-3 w-3" />}
      {isError && <XCircle className="h-3 w-3" />}
      {!isRunning && !isCompleted && !isError && <Clock className="h-3 w-3 opacity-40" />}
    </motion.div>
  )
}

export default function SourceStatusTicker({ sources, running, elapsedSeconds }: SourceStatusTickerProps) {
  if (!sources || sources.length === 0) return null

  // Filter to pipeline sources and sort: running first, then pending, then completed/error
  const pipelineSources = sources.filter(s => ACTIVE_PIPELINE_SOURCES.includes(s.name))
  const sorted = [...pipelineSources].sort((a, b) => {
    const order = { running: 0, pending: 1, completed: 2, error: 3 }
    return (order[a.status as keyof typeof order] ?? 99) - (order[b.status as keyof typeof order] ?? 99)
  })

  return (
    <motion.div
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      className="relative overflow-hidden rounded-lg border bg-card/80 backdrop-blur-sm px-3 py-2"
    >
      <div className="flex items-center gap-3 overflow-x-auto ">
        {/* Running indicator */}
        {running && (
          <motion.div
            animate={{ opacity: [0.6, 1, 0.6] }}
            transition={{ duration: 1.5, repeat: Infinity }}
            className="flex items-center gap-1.5 shrink-0 rounded-full bg-brand-blue/10 px-2.5 py-1"
          >
            <span className="h-1.5 w-1.5 rounded-full bg-brand-blue animate-pulse-soft" />
            <span className="font-mono text-[10px] font-bold text-brand-blue">
              {elapsedSeconds.toFixed(1)}s
            </span>
          </motion.div>
        )}

        {/* Scrolling chips container */}
        <div className="flex items-center gap-2 overflow-x-auto  pr-2">
          <AnimatePresence mode="popLayout">
            {sorted.map(s => (
              <SourceChip key={s.name} state={s} />
            ))}
          </AnimatePresence>
        </div>

        {/* Count summary */}
        {running && (
          <motion.span
            animate={{ opacity: [0.5, 1, 0.5] }}
            transition={{ duration: 2, repeat: Infinity }}
            className="ml-auto shrink-0 font-mono text-[10px] text-muted-foreground"
          >
            {sorted.filter(s => s.status === 'running').length} active
          </motion.span>
        )}
        {!running && (
          <span className="ml-auto shrink-0 font-mono text-[10px] text-muted-foreground/60">
            {sorted.filter(s => s.status === 'completed').length}/{sorted.length} done
          </span>
        )}
      </div>
    </motion.div>
  )
}
