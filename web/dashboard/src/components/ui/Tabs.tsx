import { createContext, useContext, useState, type ReactNode, useCallback } from 'react'
import { motion } from 'framer-motion'
import { cn } from '../../lib/utils'

interface TabsContextValue {
  active: string
  setActive: (id: string) => void
}

const TabsContext = createContext<TabsContextValue | null>(null)

function useTabs() {
  const ctx = useContext(TabsContext)
  if (!ctx) throw new Error('Tabs components must be used within <Tabs>')
  return ctx
}

interface TabsProps {
  defaultValue: string
  children: ReactNode
  className?: string
  onChange?: (value: string) => void
}

function Tabs({ defaultValue, children, className, onChange }: TabsProps) {
  const [active, setActive] = useState(defaultValue)

  const handleChange = useCallback(
    (value: string) => {
      setActive(value)
      onChange?.(value)
    },
    [onChange],
  )

  return (
    <TabsContext.Provider value={{ active, setActive: handleChange }}>
      <div className={className}>{children}</div>
    </TabsContext.Provider>
  )
}

interface TabListProps {
  children: ReactNode
  className?: string
}

function TabList({ children, className }: TabListProps) {
  return (
    <div
      role="tablist"
      className={cn(
        'flex items-center gap-1 rounded-xl bg-muted/50 p-1 border border-border/30',
        className,
      )}
    >
      {children}
    </div>
  )
}

interface TabProps {
  id: string
  children: ReactNode
  count?: number
}

function Tab({ id, children, count }: TabProps) {
  const { active, setActive } = useTabs()
  const isActive = active === id

  return (
    <button
      role="tab"
      aria-selected={isActive}
      aria-controls={`tabpanel-${id}`}
      onClick={() => setActive(id)}
      className={cn(
        'relative flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition-colors',
        isActive ? 'text-foreground' : 'text-muted-foreground hover:text-foreground',
      )}
    >
      {isActive && (
        <motion.div
          layoutId="tab-indicator"
          className="absolute inset-0 rounded-lg bg-card shadow-sm border border-border/30"
          transition={{ type: 'spring', duration: 0.4, bounce: 0.1 }}
        />
      )}
      <span className="relative z-10">{children}</span>
      {count !== undefined && (
        <span
          className={cn(
            'relative z-10 ml-1 rounded-full px-1.5 py-0.5 text-[10px] font-semibold',
            isActive ? 'bg-muted text-foreground' : 'bg-muted/60 text-muted-foreground',
          )}
        >
          {count}
        </span>
      )}
    </button>
  )
}

interface TabPanelProps {
  id: string
  children: ReactNode
  className?: string
}

function TabPanel({ id, children, className }: TabPanelProps) {
  const { active } = useTabs()

  if (active !== id) return null

  return (
    <div
      role="tabpanel"
      id={`tabpanel-${id}`}
      aria-labelledby={id}
      className={className}
    >
      {children}
    </div>
  )
}

export { Tabs, TabList, Tab, TabPanel }
