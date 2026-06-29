import { Navigate, useLocation } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { useAuth } from '@/lib/AuthContext'
import { fetchProfileStatus } from '@/lib/api'
import { Layers } from 'lucide-react'

export default function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth()
  const location = useLocation()
  const [profileChecked, setProfileChecked] = useState(false)
  const [needsOnboarding, setNeedsOnboarding] = useState(false)

  // ── After auth loads, check if the user has a profile ──
  useEffect(() => {
    if (!user || loading) return

    // Don't redirect if already on the profile page
    if (location.pathname === '/profile') {
      setProfileChecked(true)
      return
    }

    fetchProfileStatus()
      .then(status => {
        if (!status.has_profile) {
          setNeedsOnboarding(true)
        }
        setProfileChecked(true)
      })
      .catch(() => {
        setProfileChecked(true) // fail open — let user through
      })
  }, [user, loading, location.pathname])

  if (loading || (!profileChecked && user)) {
    return (
      <main className="flex min-h-[70vh] items-center justify-center">
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          className="flex flex-col items-center gap-5"
        >
          {/* Animated logo */}
          <motion.div
            animate={{
              scale: [1, 1.12, 1],
              boxShadow: [
                '0 0 0 0 hsl(var(--primary) / 0)',
                '0 0 0 8px hsl(var(--primary) / 0.15)',
                '0 0 0 0 hsl(var(--primary) / 0)',
              ],
            }}
            transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
            className="flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-brand shadow-xl"
          >
            <Layers className="h-8 w-8 text-primary-foreground" />
          </motion.div>

          <div className="text-center">
            <p className="font-display text-base font-bold text-foreground">
              Loading your workspace
            </p>
            <p className="mt-1 font-mono text-xs text-muted-foreground">
              Verifying authentication...
            </p>
          </div>

          {/* Progress bar */}
          <div className="h-1 w-48 overflow-hidden rounded-full bg-secondary">
            <motion.div
              className="h-full rounded-full bg-gradient-brand"
              animate={{ x: ['-100%', '100%'] }}
              transition={{ duration: 1.5, repeat: Infinity, ease: 'easeInOut' }}
            />
          </div>
        </motion.div>
      </main>
    )
  }

  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  // ── New user without profile → let through, MainPage will auto-open settings ──
  // Pass onboarding flag via location state so MainPage can open the settings panel
  if (needsOnboarding && location.pathname !== '/login') {
    return (
      <Navigate
        to={{ pathname: '/', search: '?onboarding=1' }}
        replace
      />
    )
  }

  return <>{children}</>
}
