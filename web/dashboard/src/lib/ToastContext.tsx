import { createContext, useContext, useState, useCallback, type ReactNode } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { CheckCircle2, AlertCircle, XCircle, Info, X } from 'lucide-react'
import { cn } from './utils'

type ToastType = 'success' | 'error' | 'warning' | 'info'

interface Toast {
  id: string
  type: ToastType
  title: string
  message?: string
}

interface ToastContextValue {
  toasts: Toast[]
  addToast: (type: ToastType, title: string, message?: string) => void
  removeToast: (id: string) => void
}

const ToastContext = createContext<ToastContextValue | undefined>(undefined)

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within <ToastProvider>')
  return ctx
}

const iconMap = {
  success: CheckCircle2,
  error: XCircle,
  warning: AlertCircle,
  info: Info,
}

const colorMap = {
  success: {
    border: 'border-emerald-500/30',
    bg: 'bg-emerald-50 dark:bg-emerald-950/40',
    icon: 'text-emerald-600 dark:text-emerald-400',
    title: 'text-emerald-800 dark:text-emerald-200',
    msg: 'text-emerald-600/80 dark:text-emerald-400/70',
    bar: 'bg-gradient-success',
  },
  error: {
    border: 'border-red-500/30',
    bg: 'bg-red-50 dark:bg-red-950/40',
    icon: 'text-red-600 dark:text-red-400',
    title: 'text-red-800 dark:text-red-200',
    msg: 'text-red-600/80 dark:text-red-400/70',
    bar: 'bg-gradient-to-r from-red-500 to-rose-500',
  },
  warning: {
    border: 'border-amber-500/30',
    bg: 'bg-amber-50 dark:bg-amber-950/40',
    icon: 'text-amber-600 dark:text-amber-400',
    title: 'text-amber-800 dark:text-amber-200',
    msg: 'text-amber-600/80 dark:text-amber-400/70',
    bar: 'bg-gradient-to-r from-amber-500 to-orange-500',
  },
  info: {
    border: 'border-blue-500/30',
    bg: 'bg-blue-50 dark:bg-blue-950/40',
    icon: 'text-blue-600 dark:text-blue-400',
    title: 'text-blue-800 dark:text-blue-200',
    msg: 'text-blue-600/80 dark:text-blue-400/70',
    bar: 'bg-gradient-brand',
  },
}

let toastId = 0

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])

  const addToast = useCallback((type: ToastType, title: string, message?: string) => {
    const id = `toast-${++toastId}`
    setToasts(prev => [...prev, { id, type, title, message }])
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id))
    }, 5000)
  }, [])

  const removeToast = useCallback((id: string) => {
    setToasts(prev => prev.filter(t => t.id !== id))
  }, [])

  return (
    <ToastContext.Provider value={{ toasts, addToast, removeToast }}>
      {children}
      <div className="pointer-events-none fixed inset-0 z-[100] flex items-end justify-end p-4 sm:p-6">
        <div className="flex w-full max-w-sm flex-col-reverse gap-3">
          <AnimatePresence mode="popLayout">
            {toasts.map(toast => {
              const Icon = iconMap[toast.type]
              const colors = colorMap[toast.type]
              return (
                <motion.div
                  key={toast.id}
                  layout
                  initial={{ opacity: 0, y: 50, scale: 0.95 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: 20, scale: 0.95, transition: { duration: 0.2 } }}
                  className={cn(
                    'pointer-events-auto relative overflow-hidden rounded-xl border bg-card shadow-2xl',
                    colors.border,
                  )}
                >
                  {/* Accent bar */}
                  <div className={cn('absolute inset-x-0 top-0 h-0.5', colors.bar)} />

                  <div className={cn('flex items-start gap-3 p-4', colors.bg)}>
                    <Icon className={cn('mt-0.5 h-5 w-5 flex-shrink-0', colors.icon)} />
                    <div className="flex-1 min-w-0">
                      <p className={cn('font-display text-sm font-bold', colors.title)}>
                        {toast.title}
                      </p>
                      {toast.message && (
                        <p className={cn('mt-0.5 font-mono text-xs', colors.msg)}>
                          {toast.message}
                        </p>
                      )}
                    </div>
                    <button
                      onClick={() => removeToast(toast.id)}
                      className="flex-shrink-0 rounded-md p-1 text-muted-foreground/50 transition-colors hover:text-foreground"
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </motion.div>
              )
            })}
          </AnimatePresence>
        </div>
      </div>
    </ToastContext.Provider>
  )
}
