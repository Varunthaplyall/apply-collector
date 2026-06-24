import { motion } from 'framer-motion'
import { cn, formatNumber, formatPercent } from '@/lib/utils'
import { BySource } from '@/lib/api'
import { getSourceMeta } from '@/lib/sourceMeta'

interface SourceBreakdownProps {
  sources: BySource
  total: number
  loading?: boolean
}

export default function SourceBreakdown({ sources, total, loading }: SourceBreakdownProps) {
  const entries = Object.entries(sources).sort(([, a], [, b]) => b - a)

  if (loading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="space-y-1.5">
            <div className="flex items-center justify-between">
              <div className="shimmer-bg h-4 w-24 rounded" />
              <div className="shimmer-bg h-4 w-12 rounded" />
            </div>
            <div className="shimmer-bg h-2 w-full rounded-full" />
          </div>
        ))}
      </div>
    )
  }

  if (entries.length === 0) {
    return (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="flex flex-col items-center justify-center py-12 text-muted-foreground"
      >
        <p className="font-mono text-sm">No data yet</p>
        <p className="mt-1 text-xs">Run a collection to populate sources</p>
      </motion.div>
    )
  }

  const maxCount = entries[0]?.[1] ?? 1

  return (
    <div className="space-y-3.5">
      {entries.map(([source, count], idx) => {
        const meta = getSourceMeta(source)
        const pct = (count / maxCount) * 100
        const share = formatPercent(count, total)

        return (
          <motion.div
            key={source}
            initial={{ opacity: 0, x: -12 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: idx * 0.05, duration: 0.35 }}
            className="group/item relative"
          >
            <div className="mb-1 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className={cn('h-2.5 w-2.5 rounded-sm shadow-sm', `bg-${meta.color}-500`)} />
                <span className="text-sm font-medium text-foreground transition-colors group-hover/item:text-foreground">
                  {meta.label}
                </span>
              </div>
              <div className="flex items-center gap-2 font-mono text-xs tabular-nums">
                <span className="font-semibold text-foreground">{formatNumber(count)}</span>
                <span className="text-muted-foreground">({share})</span>
              </div>
            </div>
            <div className="h-2.5 w-full overflow-hidden rounded-full bg-secondary">
              <motion.div
                className={cn(
                  'h-full rounded-full bg-gradient-to-r shadow-sm',
                  meta.gradient,
                  'group-hover/item:brightness-110',
                )}
                initial={{ width: 0 }}
                animate={{ width: `${pct}%` }}
                transition={{ duration: 0.8, delay: idx * 0.05 + 0.3, ease: 'easeOut' }}
              />
            </div>
          </motion.div>
        )
      })}
    </div>
  )
}
