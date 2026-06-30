import { useState, useRef, useCallback, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { cn } from '@/lib/utils'
import { triggerCollect, createRunSSE, fetchPipelineStatus, fetchCollectionStatus } from '@/lib/api'
import type { PipelineStatus, CollectionStatus } from '@/lib/api'
import { useToast } from '@/lib/ToastContext'
import { useAdminMode } from '@/lib/admin'
import {
  Play, Loader2, Terminal, Zap, CheckCircle2, Clock,
  Sparkles, ArrowRight, ChevronDown, ChevronUp, Rocket, Layers,
  RefreshCw, Database,
} from 'lucide-react'
import { Link } from 'react-router-dom'

interface PipelineControlsProps {
  onRunComplete: () => void
  profileReady: boolean
  onStatusTick?: (status: PipelineStatus) => void
  /** True if pipeline was already running on page mount (survived refresh). */
  isPipelineRunning?: boolean
}

interface LogEntry {
  type: 'phase' | 'result' | 'info' | 'error' | 'complete'
  message: string
  timestamp: Date
}

const phaseEmoji: Record<string, string> = {
  start: '\u{1F680}',
  profile: '\u{1F464}',
  collecting: '\u{1F50D}',
  scoring: '\u{1F3AF}',
  scoring_complete: '✅',
  complete: '\u{1F3C1}',
}

export default function PipelineControls({
  onRunComplete,
  profileReady,
  onStatusTick,
  isPipelineRunning = false,
}: PipelineControlsProps) {
  const { isAdmin } = useAdminMode()
  const { addToast } = useToast()
  const [running, setRunning] = useState(false)
  const [stage, setStage] = useState<string | null>(null)
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [progress, setProgress] = useState(0)
  const [done, setDone] = useState(false)
  const [result, setResult] = useState<{ inserted: number; existing: number; elapsed: number } | null>(null)
  const [logsExpanded, setLogsExpanded] = useState(false)
  const [currentSource, setCurrentSource] = useState<string | null>(null)
  const [collectionStatus, setCollectionStatus] = useState<CollectionStatus | null>(null)
  const logEndRef = useRef<HTMLDivElement>(null)
  const esRef = useRef<EventSource | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // ── Fetch collection status on mount ──
  useEffect(() => {
    fetchCollectionStatus()
      .then(setCollectionStatus)
      .catch(() => { /* silently ignore */ })
  }, [])

  const addLog = useCallback((entry: LogEntry) => {
    setLogs(prev => [...prev, entry])
  }, [])

  const scrollToBottom = useCallback(() => {
    setTimeout(() => {
      logEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }, 50)
  }, [])

  // ── Resume polling if pipeline was already running on mount (refresh survival) ──
  useEffect(() => {
    if (!isPipelineRunning) return

    setRunning(true)
    setStage('collecting')
    setProgress(40)

    // Reconnect SSE for live log events
    esRef.current?.close()
    const es = createRunSSE(
      (data) => {
        setStage(data.phase)
        const emoji = phaseEmoji[data.phase] || '⚡'
        addLog({ type: 'phase', message: `${emoji} ${data.message || data.phase}`, timestamp: new Date() })
        const pp: Record<string, number> = { start: 10, profile: 15, collecting: 40, scoring: 70, scoring_complete: 90, complete: 100 }
        setProgress(pp[data.phase] || progress)
        scrollToBottom()
      },
      (data) => {
        if (data.inserted !== undefined) {
          setResult({ inserted: data.inserted as number, existing: data.existing as number, elapsed: data.elapsed as number })
        }
      },
      () => {},
      () => {
        setProgress(100)
        setDone(true)
        setRunning(false)
        setStage(null)
        setCurrentSource(null)
        onRunComplete()
        setTimeout(() => setDone(false), 6000)
      },
    )
    esRef.current = es

    return () => {
      es?.close()
    }
  }, [isPipelineRunning])  // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!running) return

    let pollCount = 0
    pollRef.current = setInterval(async () => {
      pollCount++
      try {
        const status = await fetchPipelineStatus()
        onStatusTick?.(status)

        const runningSource = status.sources?.find(s => s.status === 'running')
        setCurrentSource(runningSource?.label ?? null)

        if (!status.running && pollCount > 2) {
          if (pollRef.current) {
            clearInterval(pollRef.current)
            pollRef.current = null
          }
        }
      } catch {
        // silently ignore
      }
    }, 500)

    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current)
        pollRef.current = null
      }
    }
  }, [running, onStatusTick])

  const startPipeline = useCallback(async () => {
    setRunning(true)
    setDone(false)
    setResult(null)
    setLogs([])
    setProgress(5)
    setLogsExpanded(false)
    setCurrentSource(null)

    try {
      const resp = await triggerCollect()

      if (!resp.ok) {
        addLog({ type: 'error', message: resp.error ?? 'Unknown error', timestamp: new Date() })
        setRunning(false)
        setProgress(0)
        addToast('error', 'Pipeline Failed', resp.error ?? 'An unknown error occurred')
        return
      }

      esRef.current?.close()

      const es = createRunSSE(
        (data) => {
          setStage(data.phase)
          const emoji = phaseEmoji[data.phase] || '⚡'
          addLog({ type: 'phase', message: `${emoji} ${data.message || data.phase}`, timestamp: new Date() })

          const phaseProgress: Record<string, number> = {
            start: 10, profile: 15, collecting: 40, scoring: 70, scoring_complete: 90, complete: 100,
          }
          setProgress(phaseProgress[data.phase] || progress)
          scrollToBottom()
        },
        (data) => {
          addLog({ type: 'result', message: `\n--- RESULTS ---`, timestamp: new Date() })
          if (data.inserted !== undefined) {
            addLog({ type: 'info', message: `  New jobs:  ${data.inserted}`, timestamp: new Date() })
            addLog({ type: 'info', message: `  Existing:  ${data.existing}`, timestamp: new Date() })
            addLog({ type: 'info', message: `  Time:      ${data.elapsed}s`, timestamp: new Date() })
            setResult({ inserted: data.inserted as number, existing: data.existing as number, elapsed: data.elapsed as number })
          }
          scrollToBottom()
        },
        (data) => {
          addLog({ type: 'error', message: `ERROR: ${data.error}`, timestamp: new Date() })
          scrollToBottom()
        },
        () => {
          setProgress(100)
          setDone(true)
          addLog({ type: 'complete', message: '\nPipeline complete — jobs collected & scored!', timestamp: new Date() })
          setRunning(false)
          setStage(null)
          setCurrentSource(null)
          addToast('success', 'Pipeline Complete!', 'Jobs collected, scored, and ready to review')
          onRunComplete()
          scrollToBottom()
          setTimeout(() => setDone(false), 6000)
        },
      )
      esRef.current = es
    } catch (err) {
      addLog({ type: 'error', message: `Failed: ${err}`, timestamp: new Date() })
      setRunning(false)
      setProgress(0)
      addToast('error', 'Pipeline Error', String(err))
    }
  }, [addLog, scrollToBottom, onRunComplete, addToast, progress])

  return (
    <motion.section
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.1 }}
      className="rounded-xl border bg-card p-5 shadow-sm transition-shadow duration-300 hover:shadow-md sm:p-6"
    >
      {/* ── Card Header: icon + title + premium CTA button ── */}
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <motion.div
            animate={running ? { rotate: [0, -5, 5, 0] } : {}}
            transition={{ duration: 3, repeat: Infinity }}
            className="flex h-9 w-9 items-center justify-center rounded-xl bg-brand-blue/10"
          >
            <Layers className="h-4.5 w-4.5 text-brand-blue" />
          </motion.div>
          <div>
            <h3 className="font-display text-lg font-bold tracking-tight">Find Your Next Role</h3>
            <p className="font-mono text-xs text-muted-foreground">
              {running && currentSource
                ? `Scanning ${currentSource} for jobs that match your profile`
                : running
                ? 'Scanning across all sources for you…'
                : done
                ? 'All done! Your matches are ready to review'
                : 'Job pool auto-refreshes every 4 hours — scored against your profile'}
            </p>
          </div>
        </div>

        {/* Right side: collection status + optional dev trigger */}
        <div className="flex items-center gap-2.5">
          {logs.length > 0 && (
            <motion.button
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              onClick={() => setLogsExpanded(!logsExpanded)}
              className={cn(
                'flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 font-mono text-[10px] font-semibold transition-colors',
                logsExpanded
                  ? 'border-primary/30 bg-primary/5 text-primary'
                  : 'border-border bg-muted/30 text-muted-foreground hover:text-foreground',
              )}
            >
              <Terminal className="h-3 w-3" />
              {logsExpanded ? <ChevronDown className="h-3 w-3" /> : <ChevronUp className="h-3 w-3" />}
            </motion.button>
          )}

          {/* ── Collection Status (replaces Run Pipeline button in production) ── */}
          {!running && !done && collectionStatus && (
            <div className="flex items-center gap-2 rounded-xl border border-border bg-secondary/30 px-3 py-1.5">
              <Database className="h-3.5 w-3.5 text-muted-foreground" />
              <span className="font-mono text-[11px] font-semibold tabular-nums text-muted-foreground">
                {collectionStatus.total_jobs.toLocaleString()} jobs
              </span>
              {collectionStatus.last_run && (
                <span className="font-mono text-[10px] text-muted-foreground/60">
                  · {(() => {
                    const d = new Date(collectionStatus.last_run.run_date)
                    const mins = Math.round((Date.now() - d.getTime()) / 60000)
                    if (mins < 1) return 'just now'
                    if (mins < 60) return `${mins}m ago`
                    if (mins < 1440) return `${Math.round(mins / 60)}h ago`
                    return `${Math.round(mins / 1440)}d ago`
                  })()}
                </span>
              )}
            </div>
          )}

          {/* ── Admin-only: manual Run Pipeline trigger ── */}
          {isAdmin && (
            <motion.button
              whileHover={profileReady && !running ? { scale: 1.03 } : {}}
              whileTap={profileReady && !running ? { scale: 0.97 } : {}}
              onClick={startPipeline}
              disabled={running || !profileReady}
              className={cn(
                'relative inline-flex shrink-0 items-center gap-2 rounded-xl px-4 py-2 font-display text-sm font-bold transition-all duration-300',
                'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
                profileReady
                  ? 'bg-gradient-to-r from-brand-blue via-brand-blue to-brand-violet text-white shadow-md shadow-brand-blue/20 hover:shadow-lg hover:shadow-brand-blue/30'
                  : 'bg-muted text-muted-foreground cursor-not-allowed opacity-50',
                running && 'bg-gradient-to-r from-brand-blue to-brand-violet text-white shadow-lg shadow-brand-violet/25',
                done && 'bg-gradient-to-r from-emerald-500 to-teal-500 text-white shadow-lg shadow-emerald-500/25',
              )}
              title={!profileReady ? 'Set up your profile first' : running ? 'Pipeline is running' : 'Run collection pipeline'}
            >
              <div className="absolute inset-0 rounded-xl bg-gradient-to-b from-white/10 to-transparent pointer-events-none" />
              {running && (
                <motion.div
                  className="absolute inset-0 rounded-xl bg-gradient-to-r from-transparent via-white/8 to-transparent pointer-events-none"
                  animate={{ x: ['-100%', '100%'] }}
                  transition={{ duration: 2, repeat: Infinity, ease: 'linear' }}
                />
              )}
              {running && (
                <motion.div
                  className="absolute -inset-[3px] rounded-xl pointer-events-none border-2 border-brand-blue/30"
                  animate={{ opacity: [0, 1, 0] }}
                  transition={{ duration: 1.5, repeat: Infinity }}
                />
              )}
              <span className="relative z-10 flex items-center gap-2">
                {running ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : done ? (
                  <CheckCircle2 className="h-4 w-4" />
                ) : (
                  <Rocket className="h-4 w-4" />
                )}
                <span>
                  {running ? 'Collecting…'
                   : done
                   ? (result ? `+${result.inserted} jobs` : 'Done!')
                   : 'Run Pipeline'}
                </span>
              </span>
            </motion.button>
          )}
        </div>
      </div>

      {/* ── Profile-not-ready banner ── */}
      <AnimatePresence>
        {!profileReady && (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            className="mb-4 rounded-xl border-2 border-amber-500/20 bg-amber-50/80 dark:bg-amber-950/10 px-4 py-3 flex items-center gap-3"
          >
            <Sparkles className="h-4 w-4 text-amber-600 shrink-0" />
            <div className="flex-1">
              <p className="text-sm font-medium text-amber-800 dark:text-amber-200">Set up your profile first</p>
              <p className="text-xs text-amber-600/80 dark:text-amber-300/70">Tell us what roles and locations you want</p>
            </div>
            <Link
              to="/profile"
              className="inline-flex items-center gap-1.5 rounded-lg bg-amber-600 px-3 py-1.5 text-xs font-bold text-white hover:bg-amber-700 transition-colors"
            >
              Profile <ArrowRight className="h-3 w-3" />
            </Link>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Progress bar (during runs) ── */}
      <AnimatePresence>
        {running && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="mb-4"
          >
            <div className="h-1.5 w-full overflow-hidden rounded-full bg-secondary">
              <motion.div
                className="h-full rounded-full bg-gradient-brand"
                animate={{ width: `${progress}%` }}
                transition={{ duration: 0.5, ease: 'easeOut' }}
              />
            </div>
            <div className="mt-1.5 flex items-center justify-between font-mono text-[10px] text-muted-foreground">
              <span>{stage ? stage.charAt(0).toUpperCase() + stage.slice(1) : 'Starting…'}</span>
              <span>{progress}%</span>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Done result summary ── */}
      <AnimatePresence>
        {done && result && (
          <motion.div
            initial={{ opacity: 0, y: -6, height: 0 }}
            animate={{ opacity: 1, y: 0, height: 'auto' }}
            exit={{ opacity: 0, y: -6, height: 0 }}
            className="mb-4 grid grid-cols-3 gap-2"
          >
            <div className="rounded-xl border border-emerald-500/20 bg-emerald-50/50 dark:bg-emerald-950/10 px-3 py-2.5">
              <p className="font-mono text-[10px] font-semibold uppercase text-emerald-600 dark:text-emerald-400">New</p>
              <p className="font-display text-lg font-black text-emerald-700 dark:text-emerald-300">{result.inserted}</p>
            </div>
            <div className="rounded-xl border border-muted bg-secondary/30 px-3 py-2.5">
              <p className="font-mono text-[10px] font-semibold uppercase text-muted-foreground">Duplicates</p>
              <p className="font-display text-lg font-black text-foreground">{result.existing}</p>
            </div>
            <div className="rounded-xl border border-muted bg-secondary/30 px-3 py-2.5">
              <p className="font-mono text-[10px] font-semibold uppercase text-muted-foreground">Time</p>
              <p className="font-display text-lg font-black text-foreground">{result.elapsed}s</p>
            </div>
            <Link
              to="/jobs?sort=match"
              className="col-span-3 inline-flex items-center justify-center gap-2 rounded-xl bg-gradient-brand px-4 py-2.5 font-display text-sm font-bold text-primary-foreground shadow-lg shadow-brand-blue/20 transition-shadow hover:shadow-xl hover:shadow-brand-blue/30"
            >
              View Matched Jobs <ArrowRight className="h-4 w-4" />
            </Link>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Collapsible terminal log ── */}
      <AnimatePresence>
        {logs.length > 0 && logsExpanded && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.3 }}
            className="overflow-hidden rounded-xl border shadow-inner"
          >
            <div className="flex items-center gap-2 border-b bg-muted/50 px-4 py-2">
              <div className="flex gap-1.5">
                <div className={cn('h-2.5 w-2.5 rounded-full', running ? 'bg-red-400' : 'bg-muted-foreground/30')} />
                <div className={cn('h-2.5 w-2.5 rounded-full', running ? 'bg-amber-400' : 'bg-muted-foreground/30')} />
                <div className="h-2.5 w-2.5 rounded-full bg-emerald-400" />
              </div>
              <div className="flex items-center gap-2 font-mono text-xs text-muted-foreground">
                <span className={cn('inline-block h-2 w-2 rounded-full', running ? 'bg-emerald-500 animate-pulse-soft' : done ? 'bg-emerald-500' : 'bg-muted-foreground')} />
                {running ? (stage || 'Running...') : done ? 'Complete' : 'Log'}
              </div>
              <span className="ml-auto font-mono text-[10px] text-muted-foreground/50">{logs.length} lines</span>
            </div>

            <div className="max-h-64 overflow-y-auto bg-[#08080a] p-4 font-mono text-xs leading-relaxed">
              <AnimatePresence>
                {logs.map((entry, i) => (
                  <motion.div
                    key={`${i}-${entry.timestamp.getTime()}`}
                    initial={{ opacity: 0, x: -4 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.15 }}
                    className={cn(
                      'flex items-start gap-2',
                      entry.type === 'phase' && 'text-blue-400',
                      entry.type === 'result' && 'mt-1 font-bold text-amber-400',
                      entry.type === 'info' && 'text-emerald-400',
                      entry.type === 'error' && 'text-red-400',
                      entry.type === 'complete' && 'mt-1 font-bold text-emerald-300',
                    )}
                  >
                    <Clock className="h-3 w-3 mt-0.5 shrink-0 opacity-50" />
                    <span>{entry.message}</span>
                  </motion.div>
                ))}
              </AnimatePresence>
              {running && (
                <motion.span
                  className="ml-5 inline-block h-4 w-2 bg-emerald-400 rounded-sm"
                  animate={{ opacity: [1, 0.3, 1] }}
                  transition={{ duration: 0.8, repeat: Infinity }}
                />
              )}
              <div ref={logEndRef} />
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.section>
  )
}
