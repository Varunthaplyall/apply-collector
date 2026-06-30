import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { cn } from '@/lib/utils'
import { type Profile } from '@/lib/api'
import { useProfile, useSaveProfile } from '@/lib/queries'
import { useToast, type ToastType } from '@/lib/ToastContext'
import {
  X, Settings, Target, MapPin, Sparkles, Briefcase, SlidersHorizontal,
} from 'lucide-react'
import { Button } from '@/components/ui/Button'
import Skeleton from '@/components/Skeleton'

const ROLE_CATEGORIES = [
  'Software Engineer', 'Senior Software Engineer', 'Engineering Manager',
  'Data Scientist', 'DevOps Engineer', 'Security Engineer',
  'Product Manager', 'Product Designer', 'UX Designer',
]

const WORK_TYPES = ['Full-time', 'Part-time', 'Contract', 'Internship', 'Freelance']

const ALL_SOURCES = [
  'greenhouse', 'lever', 'workday', 'linkedin', 'cutshort',
  'remoteok', 'remotive', 'himalayas', 'yc_jobs', 'arbeitnow',
]

interface SettingsDrawerProps {
  open: boolean
  onClose: () => void
}

export default function SettingsDrawer({ open, onClose }: SettingsDrawerProps) {
  const { data: fetchedProfile, isLoading: profileLoading } = useProfile()
  const saveProfileMutation = useSaveProfile()
  const { addToast } = useToast()
  const [saving, setSaving] = useState(false)

  const defaultProfile: Profile = {
    id: null, name: '', email: '', target_roles: [], job_title_aliases: [],
    preferred_locations: [], skills: [], work_types: [], experience_years: 5,
    remote_only: false, salary_min: 0, preferred_industries: [], preferred_company_stage: [],
    enabled_sources: ALL_SOURCES, keywords_include: [], keywords_exclude: [], is_active: false,
  }
  const [local, setLocal] = useState<Profile>(defaultProfile)

  useEffect(() => {
    if (fetchedProfile) setLocal(fetchedProfile)
  }, [fetchedProfile])

  const update = (key: string, value: unknown) => {
    setLocal(p => p ? { ...p, [key]: value } : p)
  }

  const toggleArray = (key: string, item: string) => {
    setLocal(p => {
      if (!p) return p
      const arr = (p as unknown as Record<string, unknown>)[key] as string[]
      return { ...p, [key]: arr.includes(item) ? arr.filter(i => i !== item) : [...arr, item] }
    })
  }

  const handleSave = async () => {
    if (!local) return
    setSaving(true)
    try {
      const fd: Record<string, string> = {}
      if (local.id) fd.id = String(local.id)
      fd.name = local.name || 'User'
      fd.email = local.email || ''
      fd.target_roles = local.target_roles.join(',')
      fd.job_title_aliases = local.job_title_aliases.join(',')
      fd.preferred_locations = local.preferred_locations.join(',')
      fd.skills = local.skills.join(',')
      fd.work_types = local.work_types.join(',')
      fd.experience_years_min = String(local.experience_years)
      fd.experience_years_max = String(Math.min(local.experience_years + 10, 30))
      fd.remote_preference = local.remote_only ? 'REMOTE' : 'ANY'
      fd.min_salary = String(local.salary_min)
      fd.salary_currency = 'USD'
      fd.preferred_industries = local.preferred_industries.join(',')
      fd.preferred_sources = local.enabled_sources.join(',')
      fd.include_keywords = local.keywords_include.join(',')
      fd.exclude_keywords = local.keywords_exclude.join(',')
      fd.experience_level = 'MID'
      fd.education_level = 'ANY'

      await saveProfileMutation.mutateAsync(fd)
      addToast('success', 'Saved', 'Profile updated')
      onClose()
    } catch (err) {
      addToast('error', 'Error', err instanceof Error ? err.message : 'Failed to save')
    } finally {
      setSaving(false)
    }
  }

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            onClick={onClose}
            className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm"
          />
          <motion.aside
            initial={{ x: 380, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: 380, opacity: 0 }}
            transition={{ duration: 0.2, ease: 'easeOut' }}
            className="fixed right-0 top-0 z-50 h-full w-[420px] max-w-[92vw] border-l border-border/50 bg-card shadow-2xl overflow-hidden flex flex-col"
          >
            {/* Header */}
            <div className="flex items-center justify-between px-5 py-3.5 border-b border-border/50">
              <div className="flex items-center gap-2.5">
                <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-primary/10">
                  <Settings className="h-4 w-4 text-primary" />
                </div>
                <div>
                  <h2 className="text-sm font-bold text-foreground">Profile Settings</h2>
                  <p className="text-[11px] text-muted-foreground">Customize your job matching</p>
                </div>
              </div>
              <Button variant="ghost" size="icon" onClick={onClose} aria-label="Close settings">
                <X className="h-4 w-4" />
              </Button>
            </div>

            {/* Content */}
            {profileLoading ? (
              <div className="flex-1 p-5 space-y-3">
                {Array.from({ length: 6 }).map((_, i) => (
                  <Skeleton key={i} variant="block" className="h-12" delay={i * 0.05} />
                ))}
              </div>
            ) : (
              <div className="flex-1 overflow-y-auto p-5 space-y-5">
                <Section icon={<Target className="h-3.5 w-3.5" />} label="Target Roles" color="text-primary">
                  <div className="flex flex-wrap gap-1.5 mb-2">
                    {ROLE_CATEGORIES.map(role => (
                      <button
                        key={role}
                        onClick={() => toggleArray('target_roles', role)}
                        className={cn(
                          'rounded-lg border px-2.5 py-1 text-xs font-medium transition-all',
                          local.target_roles.includes(role)
                            ? 'border-primary/40 bg-primary text-primary-foreground'
                            : 'border-border/50 bg-muted/50 text-muted-foreground hover:border-muted-foreground/30',
                        )}
                      >
                        {role}
                      </button>
                    ))}
                  </div>
                  <input
                    className="h-8 w-full rounded-lg border border-border/50 bg-muted/50 px-2.5 text-xs text-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:ring-2 focus:ring-ring/20"
                    value={local.target_roles.join(', ')}
                    onChange={e => update('target_roles', e.target.value.split(',').map(s => s.trim()).filter(Boolean))}
                    placeholder="Or type custom roles..."
                  />
                </Section>

                <Section icon={<MapPin className="h-3.5 w-3.5" />} label="Locations" color="text-emerald-400">
                  <input
                    className="h-8 w-full rounded-lg border border-border/50 bg-muted/50 px-2.5 text-xs text-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:ring-2 focus:ring-ring/20"
                    value={local.preferred_locations.join(', ')}
                    onChange={e => update('preferred_locations', e.target.value.split(',').map(s => s.trim()).filter(Boolean))}
                    placeholder="Bengaluru, Remote, Mumbai, Delhi NCR..."
                  />
                  <label className="flex items-center gap-2 mt-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={local.remote_only}
                      onChange={e => update('remote_only', e.target.checked)}
                      className="h-4 w-4 rounded border-border/50 bg-muted accent-primary"
                    />
                    <span className="text-xs text-muted-foreground">Remote only</span>
                  </label>
                </Section>

                <Section icon={<Sparkles className="h-3.5 w-3.5" />} label="Skills" color="text-violet-400">
                  <input
                    className="h-8 w-full rounded-lg border border-border/50 bg-muted/50 px-2.5 text-xs text-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:ring-2 focus:ring-ring/20"
                    value={local.skills.join(', ')}
                    onChange={e => update('skills', e.target.value.split(',').map(s => s.trim()).filter(Boolean))}
                    placeholder="Python, React, TypeScript, AWS, Docker..."
                  />
                </Section>

                <Section icon={<Briefcase className="h-3.5 w-3.5" />} label="Experience & Salary" color="text-amber-400">
                  <div className="space-y-3">
                    <div>
                      <div className="flex justify-between text-[11px] text-muted-foreground mb-1">
                        <span>Min Experience</span>
                        <span className="font-mono font-semibold text-foreground">{local.experience_years}y</span>
                      </div>
                      <input type="range" min="0" max="20" value={local.experience_years}
                        onChange={e => update('experience_years', parseInt(e.target.value))}
                        className="w-full accent-primary h-1.5" />
                    </div>
                    <div>
                      <div className="flex justify-between text-[11px] text-muted-foreground mb-1">
                        <span>Min Salary</span>
                        <span className="font-mono font-semibold text-foreground">${local.salary_min.toLocaleString()}</span>
                      </div>
                      <input type="range" min="0" max="300000" step="10000" value={local.salary_min}
                        onChange={e => update('salary_min', parseInt(e.target.value))}
                        className="w-full accent-emerald-500 h-1.5" />
                    </div>
                  </div>
                </Section>

                <Section icon={<SlidersHorizontal className="h-3.5 w-3.5" />} label="Work Type" color="text-cyan-400">
                  <div className="flex flex-wrap gap-1.5">
                    {WORK_TYPES.map(wt => (
                      <button key={wt} onClick={() => toggleArray('work_types', wt)}
                        className={cn(
                          'rounded-lg border px-2.5 py-1 text-xs font-medium transition-all',
                          local.work_types.includes(wt)
                            ? 'border-cyan-500/30 bg-cyan-500/15 text-cyan-400'
                            : 'border-border/50 bg-muted/50 text-muted-foreground hover:border-muted-foreground/30',
                        )}>
                        {wt}
                      </button>
                    ))}
                  </div>
                </Section>

                <Section icon={<X className="h-3.5 w-3.5" />} label="Exclude Keywords" color="text-destructive">
                  <input
                    className="h-8 w-full rounded-lg border border-border/50 bg-muted/50 px-2.5 text-xs text-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:ring-2 focus:ring-ring/20"
                    value={local.keywords_exclude.join(', ')}
                    onChange={e => update('keywords_exclude', e.target.value.split(',').map(s => s.trim()).filter(Boolean))}
                    placeholder="Junior, internship, sales..."
                  />
                </Section>
              </div>
            )}

            {/* Footer */}
            <div className="flex-shrink-0 px-5 py-3.5 border-t border-border/50">
              <Button
                onClick={handleSave}
                loading={saving}
                disabled={!local.target_roles.length}
                className="w-full"
                size="lg"
              >
                {!local.target_roles.length ? 'Select at least one role' : 'Save Settings'}
              </Button>
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  )
}

function Section({ icon, label, color, children }: {
  icon: React.ReactNode; label: string; color: string; children: React.ReactNode
}) {
  return (
    <div>
      <div className="flex items-center gap-1.5 mb-2">
        <span className={color}>{icon}</span>
        <span className="text-xs font-semibold text-foreground">{label}</span>
      </div>
      {children}
    </div>
  )
}
