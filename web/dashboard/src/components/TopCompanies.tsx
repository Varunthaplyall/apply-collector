import { motion } from 'framer-motion'
import { TopCompany } from '@/lib/api'
import { cn, formatNumber } from '@/lib/utils'

interface TopCompaniesProps {
  companies: TopCompany[]
  loading?: boolean
}

const RANK_BADGES: Record<number, { bg: string; text: string; gradient: string }> = {
  0: { bg: 'bg-amber-100 dark:bg-amber-900/40', text: 'text-amber-700 dark:text-amber-400', gradient: 'from-amber-400 to-orange-400' },
  1: { bg: 'bg-slate-200 dark:bg-slate-800', text: 'text-slate-600 dark:text-slate-400', gradient: 'from-slate-400 to-slate-500' },
  2: { bg: 'bg-orange-100 dark:bg-orange-900/40', text: 'text-orange-700 dark:text-orange-400', gradient: 'from-orange-400 to-amber-400' },
}

export default function TopCompanies({ companies, loading }: TopCompaniesProps) {
  if (loading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="flex items-center gap-3 rounded-lg px-3 py-2.5">
            <div className="shimmer-bg h-6 w-6 rounded-md" />
            <div className="shimmer-bg h-4 flex-1 rounded" />
            <div className="shimmer-bg h-4 w-10 rounded" />
          </div>
        ))}
      </div>
    )
  }

  if (companies.length === 0) {
    return (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="flex flex-col items-center justify-center py-10 text-muted-foreground"
      >
        <p className="font-mono text-sm">No data yet</p>
      </motion.div>
    )
  }

  const maxCount = companies[0]?.count ?? 1

  return (
    <div className="space-y-1.5">
      {companies.map((c, i) => {
        const badge = RANK_BADGES[i] ?? {
          bg: 'bg-muted',
          text: 'text-muted-foreground',
          gradient: 'from-muted-foreground/30 to-muted-foreground/50',
        }

        return (
          <motion.div
            key={c.company}
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.04, duration: 0.3 }}
            whileHover={{ x: 4 }}
            className={cn(
              'group/item flex items-center gap-3 rounded-xl px-3 py-2.5 transition-all duration-200',
              'hover:bg-secondary/60',
            )}
          >
            {/* Rank badge */}
            <div className={cn(
              'flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-lg font-mono text-xs font-bold ring-1 ring-inset',
              badge.bg,
              badge.text,
              i < 3 ? 'ring-amber-500/20' : 'ring-border',
            )}>
              {i + 1}
            </div>

            {/* Company name */}
            <span className="flex-1 truncate text-sm font-medium transition-colors group-hover/item:text-foreground">
              {c.company}
            </span>

            {/* Count + mini bar */}
            <div className="flex items-center gap-2">
              <div className="h-1.5 w-16 overflow-hidden rounded-full bg-secondary">
                <motion.div
                  className={cn('h-full rounded-full bg-gradient-to-r', badge.gradient)}
                  initial={{ width: 0 }}
                  animate={{ width: `${(c.count / maxCount) * 100}%` }}
                  transition={{ duration: 0.6, delay: i * 0.04 + 0.3, ease: 'easeOut' }}
                />
              </div>
              <span className="w-10 text-right font-mono text-xs font-semibold tabular-nums text-muted-foreground">
                {formatNumber(c.count)}
              </span>
            </div>
          </motion.div>
        )
      })}
    </div>
  )
}
