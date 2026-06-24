import { ReactNode } from 'react'
import { motion } from 'framer-motion'
import { cn, formatNumber } from '@/lib/utils'
import { TrendingUp, TrendingDown, Minus } from 'lucide-react'

interface StatCardProps {
  label: string
  value: number
  icon?: ReactNode
  trend?: number[]
  loading?: boolean
  variant?: 'default' | 'secondary' | 'accent' | 'success' | 'warning' | 'brand'
  highlight?: boolean
  className?: string
  delay?: number
}

const variantStyles = {
  default: {
    iconBg: 'bg-brand-blue/10',
    iconColor: 'text-brand-blue',
    valueColor: 'text-foreground',
    bar: 'bg-gradient-brand',
    accent: 'bg-brand-blue',
    glow: 'shadow-brand-blue/10',
  },
  secondary: {
    iconBg: 'bg-brand-violet/10',
    iconColor: 'text-brand-violet',
    valueColor: 'text-foreground',
    bar: 'bg-gradient-to-r from-brand-violet to-brand-indigo',
    accent: 'bg-brand-violet',
    glow: 'shadow-brand-violet/10',
  },
  accent: {
    iconBg: 'bg-brand-amber/10',
    iconColor: 'text-brand-amber',
    valueColor: 'text-foreground',
    bar: 'bg-gradient-to-r from-amber-500 to-orange-500',
    accent: 'bg-brand-amber',
    glow: 'shadow-brand-amber/10',
  },
  success: {
    iconBg: 'bg-emerald-100 dark:bg-emerald-900/30',
    iconColor: 'text-emerald-700 dark:text-emerald-400',
    valueColor: 'text-emerald-700 dark:text-emerald-400',
    bar: 'bg-gradient-success',
    accent: 'bg-emerald-500',
    glow: 'shadow-emerald-500/10',
  },
  warning: {
    iconBg: 'bg-amber-100 dark:bg-amber-900/30',
    iconColor: 'text-amber-700 dark:text-amber-400',
    valueColor: 'text-foreground',
    bar: 'bg-gradient-to-r from-amber-500 to-orange-500',
    accent: 'bg-brand-amber',
    glow: 'shadow-amber-500/10',
  },
  brand: {
    iconBg: 'bg-rose-100 dark:bg-rose-900/30',
    iconColor: 'text-rose-600 dark:text-rose-400',
    valueColor: 'text-foreground',
    bar: 'bg-gradient-to-r from-rose-500 to-pink-500',
    accent: 'bg-brand-rose',
    glow: 'shadow-rose-500/10',
  },
}

function computeTrend(trend: number[]): { direction: 'up' | 'down' | 'flat'; pct: number } {
  if (trend.length < 2) return { direction: 'flat', pct: 0 }
  const last = trend[trend.length - 1]
  const prev = trend[trend.length - 2]
  if (!prev) return { direction: 'flat', pct: 0 }
  const pct = ((last - prev) / prev) * 100
  if (pct > 0.5) return { direction: 'up', pct: Math.abs(pct) }
  if (pct < -0.5) return { direction: 'down', pct: Math.abs(pct) }
  return { direction: 'flat', pct: 0 }
}

export default function StatCard({
  label,
  value,
  icon,
  trend,
  loading,
  variant = 'default',
  highlight = false,
  className,
  delay = 0,
}: StatCardProps) {
  const s = variantStyles[variant]
  const trendData = trend ? computeTrend(trend) : null

  if (loading) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay, duration: 0.4 }}
        className={cn(
          'relative flex flex-col gap-3 overflow-hidden rounded-xl border bg-card p-4 sm:p-5',
          className,
        )}
      >
        <div className="flex items-center gap-2">
          <div className="shimmer-bg h-8 w-8 rounded-lg" />
          <div className="shimmer-bg h-3 w-20 rounded" />
        </div>
        <div className="shimmer-bg h-9 w-24 rounded-lg" />
        <div className="mt-1 shimmer-bg h-8 w-full rounded-lg" />
      </motion.div>
    )
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 16, scale: 0.97 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ delay, duration: 0.45, ease: [0.25, 0.46, 0.45, 0.94] }}
      whileHover={{ y: -3, transition: { duration: 0.2 } }}
      className={cn(
        'group relative flex flex-col overflow-hidden rounded-xl border bg-card p-4 shadow-sm transition-shadow duration-300 sm:p-5',
        'hover:shadow-lg hover:shadow-brand-blue/5',
        highlight && 'ring-2 ring-emerald-500/20 ring-offset-2 ring-offset-background',
        className,
      )}
    >
      {/* Gradient accent bar */}
      <div className={cn(
        'absolute inset-x-0 top-0 h-[3px] origin-left scale-x-0 rounded-b transition-transform duration-500 group-hover:scale-x-100',
        s.bar,
      )} />

      {/* Subtle background glow on hover */}
      <div className={cn(
        'pointer-events-none absolute -inset-1 rounded-2xl opacity-0 transition-opacity duration-500 group-hover:opacity-100',
        s.glow,
        'bg-gradient-to-b from-transparent to-transparent',
      )} />

      {/* Header row */}
      <div className="relative z-10 flex items-center gap-2.5">
        {icon && (
          <motion.div
            whileHover={{ scale: 1.15, rotate: -5 }}
            className={cn(
              'flex h-8 w-8 items-center justify-center rounded-xl shadow-sm',
              s.iconBg,
              s.iconColor,
            )}
          >
            {icon}
          </motion.div>
        )}
        <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          {label}
        </span>
        {trendData && trendData.direction !== 'flat' && (
          <motion.span
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ delay: delay + 0.3, type: 'spring', stiffness: 400, damping: 20 }}
            className={cn(
              'ml-auto flex items-center gap-0.5 rounded-full px-1.5 py-0.5 text-[10px] font-semibold',
              trendData.direction === 'up'
                ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400'
                : 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
            )}
          >
            {trendData.direction === 'up' ? (
              <TrendingUp className="h-3 w-3" />
            ) : (
              <TrendingDown className="h-3 w-3" />
            )}
            {trendData.pct.toFixed(1)}%
          </motion.span>
        )}
        {trendData?.direction === 'flat' && trendData.pct === 0 && trend && trend.length >= 2 && (
          <span className="ml-auto flex items-center gap-0.5 rounded-full bg-muted px-1.5 py-0.5 text-[10px] font-semibold text-muted-foreground">
            <Minus className="h-3 w-3" />
            0%
          </span>
        )}
      </div>

      {/* Value — prominent typography with count-up feel */}
      <motion.div
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ delay: delay + 0.15, duration: 0.35 }}
        className={cn(
          'relative z-10 mt-2 font-display text-3xl font-black tracking-tight transition-all duration-300 sm:text-4xl',
          'group-hover:tracking-normal',
          s.valueColor,
        )}
      >
        {formatNumber(value)}
      </motion.div>

      {/* Mini sparkline bar */}
      {trend && trend.length > 0 && (
        <div className="relative z-10 mt-3 flex items-end gap-[2px] h-7">
          {trend.map((v, i) => {
            const max = Math.max(...trend, 1)
            const h = Math.max(3, (v / max) * 100)
            return (
              <div
                key={i}
                className={cn(
                  'flex-1 rounded-sm transition-all duration-300',
                  i === trend.length - 1
                    ? s.bar
                    : 'bg-muted-foreground/20 group-hover:bg-muted-foreground/30',
                )}
                style={{ height: `${h}%` }}
              />
            )
          })}
        </div>
      )}
    </motion.div>
  )
}
