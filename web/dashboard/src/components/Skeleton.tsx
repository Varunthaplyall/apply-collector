import { cn } from '@/lib/utils'

interface SkeletonProps {
  className?: string
  variant?: 'text' | 'heading' | 'circle' | 'card' | 'block'
  lines?: number
  delay?: number
}

const variantClasses = {
  text: 'h-4 rounded-md w-full',
  heading: 'h-7 rounded-md w-3/4',
  circle: 'h-10 w-10 rounded-full motion-safe:animate-pulse-soft',
  card: 'h-32 rounded-xl w-full',
  block: 'h-12 rounded-lg w-full',
}

function Skeleton({ className, variant = 'text', lines = 1, delay = 0 }: SkeletonProps) {
  if (variant === 'card') {
    return (
      <div
        className={cn('rounded-xl border border-border/50 bg-card p-5 shadow-sm', className)}
        style={{ animationDelay: `${delay}s` }}
        aria-hidden="true"
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
      </div>
    )
  }

  return (
    <div
      className={cn(variantClasses[variant], 'shimmer-bg', className)}
      style={{ animationDelay: `${delay}s` }}
      aria-hidden="true"
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
    </div>
  )
}

export { Skeleton, type SkeletonProps }
export default Skeleton
