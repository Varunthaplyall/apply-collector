import { useState, type FormEvent } from 'react'
import { Navigate, useNavigate, useLocation } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { useAuth } from '@/lib/AuthContext'
import { Layers, Mail, Lock, Loader2, Eye, EyeOff, Sparkles } from 'lucide-react'

type Mode = 'login' | 'signup'

export default function LoginPage() {
  const { user, loading: authLoading, error, signIn, signUp, clearError } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const [mode, setMode] = useState<Mode>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [successMessage, setSuccessMessage] = useState('')

  if (!authLoading && user) {
    const from = (location.state as { from?: Location })?.from?.pathname || '/'
    return <Navigate to={from} replace />
  }

  const from = (location.state as { from?: Location })?.from?.pathname || '/'

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    clearError()
    setSuccessMessage('')
    setSubmitting(true)

    try {
      if (mode === 'login') {
        await signIn(email, password)
        navigate(from, { replace: true })
      } else {
        await signUp(email, password)
        setSuccessMessage(
          'Account created! Check your email for a confirmation link, or sign in if already confirmed.'
        )
        setMode('login')
      }
    } catch {
      // Error is already set in AuthContext
    } finally {
      setSubmitting(false)
    }
  }

  const toggleMode = () => {
    clearError()
    setSuccessMessage('')
    setMode(mode === 'login' ? 'signup' : 'login')
  }

  return (
    <main className="relative flex min-h-[80vh] items-center justify-center px-4">
      {/* Background mesh */}
      <div className="pointer-events-none absolute inset-0 bg-mesh" />

      <motion.div
        initial={{ opacity: 0, y: 20, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.5, ease: [0.25, 0.46, 0.45, 0.94] }}
        className="relative w-full max-w-sm"
      >
        {/* Brand */}
        <div className="mb-8 text-center">
          <motion.div
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ delay: 0.2, type: 'spring', stiffness: 260, damping: 20 }}
            className="mx-auto mb-5 flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-brand shadow-xl shadow-brand-blue/30"
          >
            <Layers className="h-8 w-8 text-primary-foreground" />
          </motion.div>
          <motion.h1
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="font-display text-2xl font-black tracking-tight"
          >
            <span className="gradient-text">The Apply Collector</span>
          </motion.h1>
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.4 }}
            className="mt-2 font-mono text-xs text-muted-foreground"
          >
            {mode === 'login' ? 'Sign in to your account' : 'Create a new account'}
          </motion.p>
        </div>

        {/* Form */}
        <motion.form
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.35 }}
          onSubmit={handleSubmit}
          className="rounded-2xl border bg-card p-6 shadow-lg shadow-black/[0.02] dark:shadow-black/20"
          key={mode}
        >
          <div className="space-y-4">
            {/* Email */}
            <div>
              <label
                htmlFor="email"
                className="mb-1.5 block font-mono text-[10px] font-semibold uppercase tracking-wider text-muted-foreground"
              >
                Email
              </label>
              <div className="relative group/input">
                <Mail className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground transition-colors group-focus-within/input:text-brand-blue" />
                <input
                  id="email"
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  className="h-11 w-full rounded-xl border bg-background pl-10 pr-3 font-mono text-sm placeholder:text-muted-foreground/50 transition-all duration-200 focus:border-brand-blue focus:outline-none focus:ring-2 focus:ring-brand-blue/20"
                />
              </div>
            </div>

            {/* Password */}
            <div>
              <label
                htmlFor="password"
                className="mb-1.5 block font-mono text-[10px] font-semibold uppercase tracking-wider text-muted-foreground"
              >
                Password
              </label>
              <div className="relative group/input">
                <Lock className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground transition-colors group-focus-within/input:text-brand-blue" />
                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  required
                  minLength={6}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="h-11 w-full rounded-xl border bg-background pl-10 pr-10 font-mono text-sm placeholder:text-muted-foreground/50 transition-all duration-200 focus:border-brand-blue focus:outline-none focus:ring-2 focus:ring-brand-blue/20"
                />
                <motion.button
                  whileHover={{ scale: 1.1 }}
                  whileTap={{ scale: 0.9 }}
                  type="button"
                  onClick={() => setShowPassword((s) => !s)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                  tabIndex={-1}
                >
                  {showPassword ? (
                    <EyeOff className="h-4 w-4" />
                  ) : (
                    <Eye className="h-4 w-4" />
                  )}
                </motion.button>
              </div>
            </div>

            {/* Error */}
            <AnimatePresence>
              {error && (
                <motion.div
                  initial={{ opacity: 0, height: 0, y: -4 }}
                  animate={{ opacity: 1, height: 'auto', y: 0 }}
                  exit={{ opacity: 0, height: 0, y: -4 }}
                  className="rounded-xl border border-destructive/30 bg-destructive/10 px-3 py-2.5 font-mono text-xs text-destructive"
                >
                  {error}
                </motion.div>
              )}
            </AnimatePresence>

            {/* Success */}
            <AnimatePresence>
              {successMessage && (
                <motion.div
                  initial={{ opacity: 0, height: 0, y: -4 }}
                  animate={{ opacity: 1, height: 'auto', y: 0 }}
                  exit={{ opacity: 0, height: 0, y: -4 }}
                  className="rounded-xl border border-emerald-300 bg-emerald-50 px-3 py-2.5 font-mono text-xs text-emerald-700 dark:border-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-400"
                >
                  <Sparkles className="inline h-3 w-3 mr-1" />
                  {successMessage}
                </motion.div>
              )}
            </AnimatePresence>

            {/* Submit */}
            <motion.button
              whileHover={{ scale: 1.01 }}
              whileTap={{ scale: 0.98 }}
              type="submit"
              disabled={submitting || authLoading}
              className="flex h-11 w-full items-center justify-center gap-2 rounded-xl bg-gradient-brand font-display text-sm font-bold text-primary-foreground shadow-lg shadow-brand-blue/25 transition-all hover:shadow-xl hover:shadow-brand-blue/30 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {submitting ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : null}
              {mode === 'login' ? 'Sign In' : 'Create Account'}
            </motion.button>

            {/* Toggle mode */}
            <p className="text-center font-mono text-xs text-muted-foreground">
              {mode === 'login' ? (
                <>
                  Don&apos;t have an account?{' '}
                  <motion.button
                    whileHover={{ scale: 1.05 }}
                    type="button"
                    onClick={toggleMode}
                    className="font-semibold text-brand-blue hover:underline"
                  >
                    Sign up
                  </motion.button>
                </>
              ) : (
                <>
                  Already have an account?{' '}
                  <motion.button
                    whileHover={{ scale: 1.05 }}
                    type="button"
                    onClick={toggleMode}
                    className="font-semibold text-brand-blue hover:underline"
                  >
                    Sign in
                  </motion.button>
                </>
              )}
            </p>
          </div>
        </motion.form>
      </motion.div>
    </main>
  )
}
