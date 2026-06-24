import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { cn } from '@/lib/utils'
import { useAuth } from '@/lib/AuthContext'
import {
  LayoutDashboard, User, Briefcase, History, Sun, Moon, Layers,
  LogOut, LogIn,
} from 'lucide-react'

const NAV_ITEMS = [
  { href: '/', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/profile', label: 'Profile', icon: User },
  { href: '/jobs', label: 'Jobs', icon: Briefcase },
  { href: '/history', label: 'History', icon: History },
]

export default function NavHeader() {
  const location = useLocation()
  const navigate = useNavigate()
  const { user, signOut } = useAuth()
  const isLoginPage = location.pathname === '/login'

  const [dark, setDark] = useState(() => {
    if (typeof window !== 'undefined') {
      const stored = localStorage.getItem('theme')
      if (stored === 'dark') return true
      if (stored === 'light') return false
      return window.matchMedia('(prefers-color-scheme: dark)').matches
    }
    return false
  })

  const toggleTheme = () => {
    const next = !dark
    setDark(next)
    localStorage.setItem('theme', next ? 'dark' : 'light')
    document.documentElement.classList.toggle('dark', next)
  }

  const handleSignOut = async () => {
    await signOut()
    navigate('/login', { replace: true })
  }

  return (
    <motion.header
      initial={{ y: -20, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.4, ease: [0.25, 0.46, 0.45, 0.94] }}
      className="sticky top-0 z-50 border-b bg-card/80 backdrop-blur-xl supports-[backdrop-filter]:bg-card/60"
    >
      <div className="mx-auto flex max-w-[1440px] items-center justify-between px-4 py-3 sm:px-6 lg:px-8">
        {/* Brand */}
        <Link to={user ? '/' : '/login'} className="flex items-center gap-3 group">
          <motion.div
            whileHover={{ scale: 1.08, rotate: -3 }}
            whileTap={{ scale: 0.95 }}
            className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-brand shadow-lg shadow-brand-blue/25 transition-shadow group-hover:shadow-brand-violet/30"
          >
            <Layers className="h-5 w-5 text-primary-foreground" />
          </motion.div>
          <div className="hidden sm:block">
            <h1 className="font-display text-base font-black tracking-tight text-foreground">
              The Apply Collector
            </h1>
            <p className="font-mono text-[10px] font-medium uppercase tracking-[0.15em] text-muted-foreground">
              Job Pipeline Dashboard
            </p>
          </div>
        </Link>

        {/* Navigation — only show when authenticated */}
        {user && (
          <nav className="flex items-center gap-0.5">
            {NAV_ITEMS.map((item) => {
              const Icon = item.icon
              const isActive = location.pathname === item.href
              return (
                <Link
                  key={item.href}
                  to={item.href}
                  className={cn(
                    'relative flex items-center gap-1.5 rounded-xl px-3 py-2 text-sm font-medium transition-all duration-200',
                    'hover:bg-secondary active:scale-[0.97]',
                    isActive
                      ? 'bg-secondary text-foreground shadow-sm'
                      : 'text-muted-foreground hover:text-foreground',
                  )}
                >
                  {isActive && (
                    <motion.div
                      layoutId="nav-indicator"
                      className="absolute inset-x-2 -bottom-0.5 h-0.5 rounded-full bg-gradient-brand"
                      transition={{ type: 'spring', stiffness: 380, damping: 30 }}
                    />
                  )}
                  <Icon className={cn('h-4 w-4 transition-transform duration-200', isActive && 'scale-110')} />
                  <span className="hidden sm:inline">{item.label}</span>
                </Link>
              )
            })}
          </nav>
        )}

        {/* Right side: theme toggle + auth */}
        <div className="flex items-center gap-1">
          {/* Theme toggle */}
          <motion.button
            whileHover={{ scale: 1.1 }}
            whileTap={{ scale: 0.9 }}
            onClick={toggleTheme}
            className="flex items-center justify-center rounded-xl p-2 text-muted-foreground transition-all duration-200 hover:bg-secondary hover:text-foreground"
            aria-label="Toggle theme"
          >
            <motion.div
              key={dark ? 'sun' : 'moon'}
              initial={{ rotate: -90, opacity: 0 }}
              animate={{ rotate: 0, opacity: 1 }}
              exit={{ rotate: 90, opacity: 0 }}
              transition={{ duration: 0.2 }}
            >
              {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </motion.div>
          </motion.button>

          {/* Auth action */}
          {user ? (
            <motion.button
              whileHover={{ scale: 1.03 }}
              whileTap={{ scale: 0.97 }}
              onClick={handleSignOut}
              className="flex items-center gap-1.5 rounded-xl px-3 py-2 text-sm font-medium text-muted-foreground transition-all duration-200 hover:bg-destructive/10 hover:text-destructive"
              title={`Signed in as ${user.email}`}
            >
              <LogOut className="h-4 w-4" />
              <span className="hidden sm:inline">Sign Out</span>
            </motion.button>
          ) : !isLoginPage ? (
            <Link
              to="/login"
              className="flex items-center gap-1.5 rounded-xl bg-gradient-brand px-4 py-2 text-sm font-bold text-primary-foreground shadow-md shadow-brand-blue/20 transition-all duration-200 hover:shadow-lg hover:shadow-brand-violet/25 active:scale-[0.97]"
            >
              <LogIn className="h-4 w-4" />
              <span className="hidden sm:inline">Sign In</span>
            </Link>
          ) : null}
        </div>
      </div>
    </motion.header>
  )
}
