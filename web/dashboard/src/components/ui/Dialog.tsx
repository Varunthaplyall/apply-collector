import { useEffect, useRef, type ReactNode, useCallback } from 'react'
import { X } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'

interface DialogProps {
  open: boolean
  onClose: () => void
  title?: string
  description?: string
  children: ReactNode
  className?: string
}

function Dialog({ open, onClose, title, description, children, className }: DialogProps) {
  const contentRef = useRef<HTMLDivElement>(null)

  // Focus trap + escape-to-close
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose()
        return
      }
      if (e.key !== 'Tab' || !contentRef.current) return

      const focusable = contentRef.current.querySelectorAll<HTMLElement>(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
      )
      if (!focusable.length) return

      const first = focusable[0]
      const last = focusable[focusable.length - 1]

      if (e.shiftKey) {
        if (document.activeElement === first) {
          e.preventDefault()
          last.focus()
        }
      } else {
        if (document.activeElement === last) {
          e.preventDefault()
          first.focus()
        }
      }
    },
    [onClose],
  )

  useEffect(() => {
    if (!open) return
    document.addEventListener('keydown', handleKeyDown)
    document.body.style.overflow = 'hidden'

    // Focus first focusable element
    const timer = setTimeout(() => {
      const first = contentRef.current?.querySelector<HTMLElement>(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
      )
      first?.focus()
    }, 50)

    return () => {
      document.removeEventListener('keydown', handleKeyDown)
      document.body.style.overflow = ''
      clearTimeout(timer)
    }
  }, [open, handleKeyDown])

  return (
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={onClose}
            aria-hidden="true"
          />

          {/* Content */}
          <motion.div
            ref={contentRef}
            role="dialog"
            aria-modal="true"
            aria-label={title}
            aria-describedby={description ? 'dialog-desc' : undefined}
            initial={{ opacity: 0, scale: 0.96, y: 8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: 8 }}
            transition={{ duration: 0.2, ease: 'easeOut' }}
            className={`relative z-10 max-h-[85vh] w-full max-w-lg overflow-y-auto rounded-2xl border border-border/50 bg-card p-6 shadow-xl ${className || ''}`}
          >
            {/* Close button */}
            <button
              onClick={onClose}
              className="absolute right-4 top-4 rounded-lg p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
              aria-label="Close dialog"
            >
              <X className="h-4 w-4" />
            </button>

            {title && (
              <h2 className="text-lg font-semibold text-foreground pr-8">{title}</h2>
            )}
            {description && (
              <p id="dialog-desc" className="mt-1 text-sm text-muted-foreground">
                {description}
              </p>
            )}
            <div className={title || description ? 'mt-4' : ''}>{children}</div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  )
}

export { Dialog, type DialogProps }
