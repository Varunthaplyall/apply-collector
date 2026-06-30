import { forwardRef, type ButtonHTMLAttributes } from 'react'
import { Loader2 } from 'lucide-react'
import { cn } from '../../lib/utils'

const variants = {
  primary:
    'bg-primary text-primary-foreground hover:bg-primary/90 shadow-sm',
  secondary:
    'bg-secondary text-secondary-foreground hover:bg-secondary/80',
  ghost:
    'text-muted-foreground hover:text-foreground hover:bg-muted/50',
  danger:
    'bg-destructive text-destructive-foreground hover:bg-destructive/90 shadow-sm',
  outline:
    'border border-border bg-transparent hover:bg-muted/50 text-foreground',
  subtle:
    'bg-muted/60 text-foreground hover:bg-muted',
} as const

const sizes = {
  sm: 'h-8 px-3 text-xs gap-1.5 rounded-md',
  md: 'h-9 px-4 text-sm gap-2 rounded-lg',
  lg: 'h-11 px-6 text-base gap-2.5 rounded-lg',
  icon: 'h-9 w-9 p-0 rounded-lg',
} as const

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: keyof typeof variants
  size?: keyof typeof sizes
  loading?: boolean
}

const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'primary', size = 'md', loading, disabled, children, ...props }, ref) => {
    return (
      <button
        ref={ref}
        disabled={disabled || loading}
        className={cn(
          'inline-flex items-center justify-center font-medium transition-colors duration-150',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:ring-offset-2 focus-visible:ring-offset-background',
          'disabled:pointer-events-none disabled:opacity-50',
          variants[variant],
          sizes[size],
          className,
        )}
        {...props}
      >
        {loading && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
        {children}
      </button>
    )
  },
)

Button.displayName = 'Button'

export { Button, type ButtonProps }
