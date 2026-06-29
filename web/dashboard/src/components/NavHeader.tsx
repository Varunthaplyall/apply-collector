import { Link, useLocation, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { useAuth } from '@/lib/AuthContext'
import { Layers, LogOut, LogIn } from 'lucide-react'

export default function NavHeader() {
  const location = useLocation()
  const navigate = useNavigate()
  const { user, signOut } = useAuth()
  const isLoginPage = location.pathname === '/login'

  const handleSignOut = async () => {
    await signOut()
    navigate('/login', { replace: true })
  }

  const isAuthPage = location.pathname === '/login'

  return (
    <header className="flex-shrink-0 z-50 border-b border-border bg-background/90 backdrop-blur-md">
      <div className="flex items-center justify-between h-12 px-4">
        {/* Brand */}
        <Link to={user ? '/' : '/login'} className="flex items-center gap-2 group">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-brand shadow-sm shadow-primary/20 group-hover:shadow-primary/30 transition-shadow">
            <Layers className="h-3.5 w-3.5 text-primary-foreground" />
          </div>
          <span className="font-display text-[13px] font-bold tracking-tight text-foreground hidden sm:inline">
            Apply Collector
          </span>
        </Link>

        {/* Right side: user + auth */}
        <div className="flex items-center gap-1">
          {user ? (
            <>
              <span className="font-mono text-[10px] text-muted-foreground/50 hidden sm:inline mr-2 truncate max-w-[160px]">
                {user.email}
              </span>
              <button
                onClick={handleSignOut}
                className="flex items-center gap-1 rounded-lg px-2.5 py-1.5 font-mono text-[10px] font-medium text-muted-foreground hover:text-destructive hover:bg-destructive/5 transition-all"
                title="Sign out"
              >
                <LogOut className="h-3 w-3" />
                <span className="hidden sm:inline">Sign Out</span>
              </button>
            </>
          ) : !isLoginPage ? (
            <Link
              to="/login"
              className="flex items-center gap-1.5 rounded-lg bg-gradient-brand px-3 py-1.5 font-mono text-[11px] font-bold text-primary-foreground shadow-sm shadow-primary/20 hover:shadow-md hover:shadow-primary/30 transition-all"
            >
              <LogIn className="h-3 w-3" />
              Sign In
            </Link>
          ) : null}
        </div>
      </div>
    </header>
  )
}
