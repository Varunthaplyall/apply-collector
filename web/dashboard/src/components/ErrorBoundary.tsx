import { Component, type ReactNode } from 'react'
import { motion } from 'framer-motion'
import { AlertTriangle, RefreshCw } from 'lucide-react'

interface Props {
  children: ReactNode
  fallback?: ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
}

export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null })
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback

      return (
        <main className="flex min-h-[70vh] items-center justify-center px-4">
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 16 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            transition={{ duration: 0.4, ease: [0.25, 0.46, 0.45, 0.94] as [number, number, number, number] }}
            className="text-center max-w-md"
          >
            <motion.div
              animate={{
                scale: [1, 1.05, 1],
                rotate: [0, -2, 2, 0],
              }}
              transition={{ duration: 3, repeat: Infinity }}
              className="mx-auto mb-6 flex h-20 w-20 items-center justify-center rounded-3xl bg-destructive/10"
            >
              <AlertTriangle className="h-10 w-10 text-destructive" />
            </motion.div>
            <h2 className="font-display text-2xl font-black tracking-tight text-foreground">
              Something went wrong
            </h2>
            <p className="mt-2 font-mono text-sm text-muted-foreground">
              An unexpected error occurred. Please try refreshing the page.
            </p>
            {this.state.error && (
              <div className="mt-4 rounded-xl border border-destructive/20 bg-destructive/5 p-4 text-left">
                <p className="font-mono text-xs text-destructive break-all">
                  {this.state.error.message}
                </p>
              </div>
            )}
            <motion.button
              whileHover={{ scale: 1.03 }}
              whileTap={{ scale: 0.97 }}
              onClick={() => window.location.reload()}
              className="mt-6 inline-flex items-center gap-2 rounded-xl bg-gradient-brand px-6 py-3 font-display text-sm font-bold text-primary-foreground shadow-lg shadow-brand-blue/25 hover:shadow-xl"
            >
              <RefreshCw className="h-4 w-4" />
              Refresh Page
            </motion.button>
          </motion.div>
        </main>
      )
    }

    return this.props.children
  }
}
