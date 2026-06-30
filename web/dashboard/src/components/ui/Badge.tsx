import { type HTMLAttributes } from 'react'
import { cn } from '../../lib/utils'

const colors = {
  default: 'bg-muted text-muted-foreground border-border/50',
  success: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
  warning: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
  danger: 'bg-red-500/10 text-red-400 border-red-500/20',
  info: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
  violet: 'bg-violet-500/10 text-violet-400 border-violet-500/20',
} as const

const sizes = {
  sm: 'px-1.5 py-0.5 text-[10px]',
  md: 'px-2 py-0.5 text-xs',
} as const

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  color?: keyof typeof colors
  size?: keyof typeof sizes
}

function Badge({ className, color = 'default', size = 'md', ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-md border font-medium',
        colors[color],
        sizes[size],
        className,
      )}
      {...props}
    />
  )
}

export { Badge, type BadgeProps }
