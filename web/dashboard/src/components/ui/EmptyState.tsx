import { type ReactNode } from 'react'
import { cn } from '../../lib/utils'

interface EmptyStateProps {
  icon?: ReactNode
  title: string
  description?: string
  action?: ReactNode
  className?: string
}

function EmptyState({ icon, title, description, action, className }: EmptyStateProps) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center gap-3 py-16 px-4 text-center',
        className,
      )}
      role="status"
    >
      {icon && (
        <div className="mb-2 flex h-16 w-16 items-center justify-center rounded-2xl bg-muted/60 text-muted-foreground">
          {icon}
        </div>
      )}
      <div className="max-w-sm space-y-1">
        <h3 className="text-base font-semibold text-foreground">{title}</h3>
        {description && (
          <p className="text-sm text-muted-foreground">{description}</p>
        )}
      </div>
      {action && <div className="mt-2">{action}</div>}
    </div>
  )
}

export { EmptyState, type EmptyStateProps }
