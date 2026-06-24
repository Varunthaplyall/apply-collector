import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  type ReactNode,
} from 'react'
import { supabase } from './supabase'
import type { Session, User } from '@supabase/supabase-js'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface AuthState {
  session: Session | null
  user: User | null
  loading: boolean
  error: string | null
  signIn: (email: string, password: string) => Promise<void>
  signUp: (email: string, password: string) => Promise<void>
  signOut: () => Promise<void>
  clearError: () => void
}

const AuthContext = createContext<AuthState | undefined>(undefined)

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null)
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // ── Bootstrap: check for existing session on mount ───────────────
  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session)
      setUser(session?.user ?? null)
      _updateCachedToken(session?.access_token ?? null)
      setLoading(false)
    })

    // Listen for auth state changes (e.g. token refresh, sign-out from another tab)
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session)
      setUser(session?.user ?? null)
      _updateCachedToken(session?.access_token ?? null)
      setLoading(false)
    })

    return () => subscription.unsubscribe()
  }, [])

  // ── Sign in with email + password ────────────────────────────────
  const signIn = useCallback(async (email: string, password: string) => {
    setLoading(true)
    setError(null)
    const { data, error } = await supabase.auth.signInWithPassword({ email, password })
    if (error) {
      setError(error.message)
      setLoading(false)
      throw error
    }
    // Update state and token cache immediately — don't wait for onAuthStateChange
    setSession(data.session)
    setUser(data.session?.user ?? null)
    _updateCachedToken(data.session?.access_token ?? null)
    setLoading(false)
  }, [])

  // ── Sign up with email + password ────────────────────────────────
  const signUp = useCallback(async (email: string, password: string) => {
    setLoading(true)
    setError(null)
    const { error } = await supabase.auth.signUp({ email, password })
    if (error) {
      setError(error.message)
      setLoading(false)
      throw error
    }
    // Supabase may auto-sign-in after sign-up depending on project settings.
    // If email confirmation is enabled, the user won't be signed in yet.
    setLoading(false)
  }, [])

  // ── Sign out ─────────────────────────────────────────────────────
  const signOut = useCallback(async () => {
    await supabase.auth.signOut()
    setSession(null)
    setUser(null)
  }, [])

  const clearError = useCallback(() => setError(null), [])

  const value: AuthState = {
    session,
    user,
    loading,
    error,
    signIn,
    signUp,
    signOut,
    clearError,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) {
    throw new Error('useAuth must be used within an <AuthProvider>')
  }
  return ctx
}

// ---------------------------------------------------------------------------
// Synchronous token access (for non-React code, e.g. api.ts)
// ---------------------------------------------------------------------------
// The AuthProvider updates this module-level variable on every auth state
// change. This lets api.ts read the token synchronously without importing
// supabase directly or hardcoding localStorage key names.

let _cachedToken: string | null = null

export function getAccessToken(): string | null {
  return _cachedToken
}

export function _updateCachedToken(token: string | null) {
  _cachedToken = token
}
