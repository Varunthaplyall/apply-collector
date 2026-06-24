import { useMemo } from 'react'
import { motion } from 'framer-motion'
import { cn, formatNumber } from '@/lib/utils'
import { RunRecord } from '@/lib/api'
import { TrendingUp } from 'lucide-react'

interface SparkChartProps {
  runs: RunRecord[]
  loading?: boolean
}

export default function SparkChart({ runs, loading }: SparkChartProps) {
  const data = useMemo(() => {
    return [...runs].reverse().map(r => r.total_jobs)
  }, [runs])

  if (loading) {
    return (
      <div className="space-y-3">
        <div className="shimmer-bg h-32 w-full rounded-lg" />
        <div className="flex justify-between">
          <div className="shimmer-bg h-3 w-16 rounded" />
          <div className="shimmer-bg h-3 w-16 rounded" />
        </div>
      </div>
    )
  }

  if (data.length === 0) {
    return (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="flex items-center justify-center py-8 text-muted-foreground"
      >
        <p className="font-mono text-sm">No run history yet</p>
      </motion.div>
    )
  }

  const min = Math.min(...data)
  const max = Math.max(...data)
  const range = max - min || 1

  const width = 100
  const height = 100
  const padding = 6
  const points = data.map((v, i) => {
    const x = padding + (i / (data.length - 1 || 1)) * (width - padding * 2)
    const y = height - padding - ((v - min) / range) * (height - padding * 2)
    return `${x},${y}`
  })

  const pathD = points.length > 1
    ? `M${points.join(' L')}`
    : `M${points[0]} L${points[0]}`

  const areaD = points.length > 1
    ? `${pathD} L${width - padding},${height - padding} L${padding},${height - padding} Z`
    : ''

  const first = data[0]
  const last = data[data.length - 1]
  const change = last && first ? ((last - first) / first) * 100 : 0
  const isUp = change >= 0

  const gradientId = 'sparkGradient-' + Math.random().toString(36).slice(2, 8)

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.5 }}
    >
      <div className="relative">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          className="h-36 w-full"
          preserveAspectRatio="none"
        >
          <defs>
            <linearGradient id={gradientId} x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="hsl(var(--brand-blue))" stopOpacity="0.3" />
              <stop offset="100%" stopColor="hsl(var(--brand-blue))" stopOpacity="0.02" />
            </linearGradient>
          </defs>
          {areaD && (
            <motion.path
              d={areaD}
              fill={`url(#${gradientId})`}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.8, delay: 0.2 }}
            />
          )}
          <motion.path
            d={pathD}
            fill="none"
            stroke="hsl(var(--brand-blue))"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            initial={{ pathLength: 0, opacity: 0 }}
            animate={{ pathLength: 1, opacity: 1 }}
            transition={{ duration: 1, ease: 'easeInOut', delay: 0.3 }}
          />
          {points.map((p, i) => {
            const [cx, cy] = p.split(',').map(Number)
            const isLast = i === points.length - 1
            return (
              <motion.circle
                key={i}
                cx={cx}
                cy={cy}
                r={isLast ? 4.5 : 0}
                fill={isLast ? 'hsl(var(--brand-blue))' : 'transparent'}
                initial={{ r: 0 }}
                animate={{ r: isLast ? 4.5 : 0 }}
                transition={{ delay: 1.2 }}
                className={isLast ? 'animate-pulse-glow' : ''}
              />
            )
          })}
        </svg>

        {/* Hover tooltip regions */}
        <div className="absolute inset-0 flex">
          {data.map((v, i) => (
            <div key={i} className="group/tip relative flex-1 cursor-default">
              <div className={cn(
                'absolute -top-10 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-lg bg-foreground px-2.5 py-1 font-mono text-xs font-semibold text-background shadow-lg',
                'pointer-events-none opacity-0 translate-y-1 transition-all duration-200 group-hover/tip:opacity-100 group-hover/tip:translate-y-0',
              )}>
                {formatNumber(v)}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Footer stats */}
      <div className="mt-3 flex items-center justify-between">
        <div>
          <p className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
            {runs[runs.length - 1]?.run_date
              ? new Date(runs[runs.length - 1].run_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
              : ''}
          </p>
        </div>
        <motion.div
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          transition={{ delay: 0.5, type: 'spring', stiffness: 400 }}
          className={cn(
            'flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold',
            isUp
              ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400'
              : 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
          )}
        >
          <TrendingUp className={cn('h-3 w-3 transition-transform duration-300', !isUp && 'rotate-180')} />
          {Math.abs(change).toFixed(1)}%
        </motion.div>
      </div>

      {/* Latest value */}
      <div className="mt-1">
        <motion.span
          initial={{ opacity: 0, x: -8 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.4 }}
          className="font-display text-2xl font-black tracking-tight"
        >
          {formatNumber(last)}
        </motion.span>
        <span className="ml-2 text-xs font-medium text-muted-foreground">
          total collected
        </span>
      </div>
    </motion.div>
  )
}
