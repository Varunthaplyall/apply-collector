import { cn } from '@/lib/utils'
import { motion } from 'framer-motion'

interface SkeletonProps {
  className?: string
  /**
   * Variants:
   * - 'text': single line of text
   * - 'heading': taller heading line
   * - 'circle': circular avatar
   * - 'card': full card skeleton
   * - 'block': generic block
   */
  variant?: 'text' | 'heading' | 'circle' | 'card' | 'block'
  /** Number of lines for 'text' variant */
  lines?: number
  /** Animation delay stagger (in seconds) */
  delay?: number
}

const variantClasses = {
  text: 'h-4 rounded-md w-full',
  heading: 'h-7 rounded-md w-3/4',
  circle: 'h-10 w-10 rounded-full',
  card: 'h-32 rounded-xl w-full',
  block: 'h-12 rounded-lg w-full',
}

export default function Skeleton({ className, variant = 'text', lines = 1, delay = 0 }: SkeletonProps) {
  if (variant === 'card') {
    return (
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay, duration: 0.35 }}
        className={cn('rounded-xl border bg-card p-5 shadow-sm', className)}
      >
        <div className="flex items-center gap-3 mb-4">
          <div className="shimmer-bg h-9 w-9 rounded-lg" />
          <div className="shimmer-bg h-4 w-28 rounded-md" />
        </div>
        <div className="space-y-3">
          <div className="shimmer-bg h-9 w-3/4 rounded-lg" />
          <div className="shimmer-bg h-4 w-full rounded-md" />
          <div className="shimmer-bg h-4 w-2/3 rounded-md" />
        </div>
      </motion.div>
    )
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.3 }}
      className={cn(variantClasses[variant], 'shimmer-bg', className)}
    >
      {variant === 'text' && lines > 1 ? (
        <div className="space-y-2">
          {Array.from({ length: lines }).map((_, i) => (
            <div
              key={i}
              className="shimmer-bg h-4 rounded-md"
              style={{ width: `${90 - i * 12}%` }}
            />
          ))}
        </div>
      ) : null}
    </motion.div>
  )
}
