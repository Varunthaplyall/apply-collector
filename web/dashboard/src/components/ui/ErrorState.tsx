import { AlertTriangle, RefreshCw } from 'lucide-react'
import { Button } from './Button'

interface ErrorStateProps {
  title?: string
  message?: string
  onRetry?: () => void
  className?: string
}

function ErrorState({
  title = 'Something went wrong',
  message = 'An unexpected error occurred. Please try again.',
  onRetry,
  className,
}: ErrorStateProps) {
  return (
    <div
      className={`flex flex-col items-center justify-center gap-3 py-16 px-4 text-center ${className || ''}`}
      role="alert"
    >
      <div className="mb-2 flex h-16 w-16 items-center justify-center rounded-2xl bg-destructive/10 text-destructive">
        <AlertTriangle className="h-8 w-8" aria-hidden="true" />
      </div>
      <div className="max-w-sm space-y-1">
        <h3 className="text-base font-semibold text-foreground">{title}</h3>
        <p className="text-sm text-muted-foreground">{message}</p>
      </div>
      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry} className="mt-2 gap-2">
          <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
          Try again
        </Button>
      )}
    </div>
  )
}

export { ErrorState, type ErrorStateProps }
