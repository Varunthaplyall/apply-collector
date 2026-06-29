import { useState, useEffect, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { cn, timeAgo } from '@/lib/utils'
import {
  fetchJobs, JobsResponse, Job, dismissJob, saveJob,
  fetchCollectionStatus, CollectionStatus,
  fetchProfile, saveProfile, Profile,
} from '@/lib/api'
import { useToast } from '@/lib/ToastContext'
import {
  Search, ChevronLeft, ChevronRight, MapPin,
  ExternalLink, Calendar, Briefcase, X,
  ThumbsDown, ThumbsUp, CheckCircle2,
  Settings, Sparkles, Target, Database,
  SlidersHorizontal,
} from 'lucide-react'

// ────────────────────────────────────────────────────────────────────────
const SORT_OPTIONS = [
  { value: 'match', label: 'Best Match' },
  { value: 'newest', label: 'Newest' },
  { value: 'oldest', label: 'Oldest' },
  { value: 'company', label: 'Company' },
  { value: 'title', label: 'Title' },
]

const ROLE_CATEGORIES = [
  'Software Engineer', 'Senior Software Engineer', 'Engineering Manager', 'Data Scientist',
  'DevOps Engineer', 'QA Engineer', 'Security Engineer', 'IT Support',
  'Product Manager', 'Product Designer', 'UX Designer', 'UI Designer', 'Technical Writer',
  'Marketing Manager', 'Sales Representative', 'Account Executive', 'Content Writer',
  'SEO Specialist', 'Social Media Manager', 'Brand Manager',
  'Accountant', 'Financial Analyst', 'Operations Manager', 'Project Manager',
  'Business Analyst', 'HR Manager', 'Recruiter', 'Office Manager',
  'Nurse', 'Doctor', 'Pharmacist', 'Medical Assistant', 'Lab Technician',
  'Teacher', 'Professor', 'Teaching Assistant', 'Curriculum Designer',
  'Customer Support', 'Administrative Assistant', 'Consultant', 'Freelancer',
]

const ALL_SOURCES = [
  'greenhouse', 'lever', 'workday', 'linkedin', 'cutshort',
  'wellfound', 'adzuna', 'remoteok', 'remotive', 'himalayas',
  'yc_jobs', 'arbeitnow', 'iimjobs', 'jsearch',
]
// ────────────────────────────────────────────────────────────────────────

const jobVariants = {
  hidden: { opacity: 0, y: 6 },
  visible: (i: number) => ({
    opacity: 1, y: 0,
    transition: { delay: Math.min(i * 0.025, 0.6), duration: 0.25 },
  }),
}

export default function MainPage() {
  const { addToast } = useToast()
  const [searchParams, setSearchParams] = useSearchParams()
  const [data, setData] = useState<JobsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [dismissedIds, setDismissedIds] = useState<Set<number>>(new Set())
  const [savedIds, setSavedIds] = useState<Set<number>>(new Set())
  const [collectionStatus, setCollectionStatus] = useState<CollectionStatus | null>(null)
  const [settingsOpen, setSettingsOpen] = useState(false)

  // Auto-open settings for onboarding (new users without profile)
  useEffect(() => {
    if (searchParams.get('onboarding') === '1') {
      setSettingsOpen(true)
      const next = new URLSearchParams(searchParams)
      next.delete('onboarding')
      setSearchParams(next, { replace: true })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const filters = {
    source: searchParams.get('source') || '',
    company: searchParams.get('company') || '',
    location: searchParams.get('location') || '',
    search: searchParams.get('search') || '',
    india: searchParams.get('india') || '',
    sort: searchParams.get('sort') || 'match',
    page: parseInt(searchParams.get('page') || '1'),
  }

  const activeFilterCount = Object.entries(filters).filter(([k, v]) =>
    v && k !== 'sort' && k !== 'page' && String(v) !== ''
  ).length

  const loadJobs = useCallback(async () => {
    setLoading(true); setError(null)
    try { const res = await fetchJobs(filters); setData(res) }
    catch (err) { setError(err instanceof Error ? err.message : 'Failed') }
    finally { setLoading(false) }
  }, [searchParams.toString()])

  useEffect(() => { loadJobs() }, [loadJobs])

  useEffect(() => {
    fetchCollectionStatus().then(setCollectionStatus).catch(() => {})
  }, [])

  const updateFilter = (key: string, value: string) => {
    const next = new URLSearchParams(searchParams)
    if (value) next.set(key, value); else next.delete(key)
    if (key !== 'page') next.delete('page')
    setSearchParams(next)
  }

  const clearFilters = () => setSearchParams(new URLSearchParams({ sort: filters.sort }))

  const handleDismiss = async (jobId: number) => {
    try {
      await dismissJob(jobId)
      setDismissedIds(prev => new Set(prev).add(jobId))
      setSavedIds(prev => { const s = new Set(prev); s.delete(jobId); return s })
    } catch { addToast('error', 'Error', 'Failed') }
  }

  const handleSave = async (jobId: number) => {
    try {
      await saveJob(jobId)
      setSavedIds(prev => new Set(prev).add(jobId))
      setDismissedIds(prev => { const s = new Set(prev); s.delete(jobId); return s })
    } catch { addToast('error', 'Error', 'Failed') }
  }

  const scoreColor = (s: number | null | undefined) => {
    if (!s) return 'text-muted-foreground'
    if (s >= 80) return 'text-emerald-400'
    if (s >= 50) return 'text-amber-400'
    return 'text-muted-foreground'
  }

  const scoreBg = (s: number | null | undefined) => {
    if (!s) return 'bg-secondary text-muted-foreground'
    if (s >= 80) return 'bg-emerald-500/15 text-emerald-400'
    if (s >= 50) return 'bg-amber-500/15 text-amber-400'
    return 'bg-secondary text-muted-foreground'
  }

  const statusText = collectionStatus?.last_run
    ? (() => {
        const d = new Date(collectionStatus.last_run.run_date)
        const mins = Math.round((Date.now() - d.getTime()) / 60000)
        if (mins < 1) return 'just now'
        if (mins < 60) return `${mins}m ago`
        if (mins < 1440) return `${Math.round(mins / 60)}h ago`
        return `${Math.round(mins / 1440)}d ago`
      })()
    : null

  return (
    <div className="flex h-[calc(100vh-48px)]">
      {/* ── Main Content ──────────────────────────────────────────── */}
      <main className="flex-1 flex flex-col min-w-0">
        {/* Filter bar */}
        <div className="flex-shrink-0 border-b border-border bg-background/80 backdrop-blur-sm px-3 py-2">
          <div className="flex items-center gap-1.5 flex-wrap">
            <div className="relative flex-1 min-w-[140px] max-w-[280px]">
              <Search className="absolute left-2 top-1/2 h-3 w-3 -translate-y-1/2 text-muted-foreground/50" />
              <input
                className="h-7 w-full rounded-md border-0 bg-muted pl-7 pr-2.5 font-mono text-[12px] text-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:ring-1 focus:ring-primary/30"
                placeholder="Search jobs..."
                value={filters.search}
                onChange={e => updateFilter('search', e.target.value)}
              />
            </div>

            <select
              className="h-7 rounded-md border-0 bg-muted px-2 font-mono text-[11px] text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary/30"
              value={filters.source}
              onChange={e => updateFilter('source', e.target.value)}
            >
              <option value="">All Sources</option>
              {(data?.sources ?? ALL_SOURCES).map(s => <option key={s} value={s}>{s}</option>)}
            </select>

            <input
              className="h-7 w-24 rounded-md border-0 bg-muted px-2 font-mono text-[11px] text-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:ring-1 focus:ring-primary/30"
              placeholder="Location..."
              value={filters.location}
              onChange={e => updateFilter('location', e.target.value)}
            />

            <label className={cn(
              'flex h-7 cursor-pointer items-center gap-1 rounded-md px-2 font-mono text-[10px] font-medium select-none',
              filters.india === '1' ? 'bg-amber-500/10 text-amber-400' : 'bg-muted text-muted-foreground hover:text-foreground'
            )}>
              <input type="checkbox" checked={filters.india === '1'} onChange={e => updateFilter('india', e.target.checked ? '1' : '')} className="sr-only" />
              <MapPin className="h-2.5 w-2.5" />India
            </label>

            <select
              className="h-7 rounded-md border-0 bg-muted px-2 font-mono text-[11px] text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary/30"
              value={filters.sort}
              onChange={e => updateFilter('sort', e.target.value)}
            >
              {SORT_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>

            <AnimatePresence>
              {activeFilterCount > 0 && (
                <motion.button
                  initial={{ opacity: 0, scale: 0.8 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.8 }}
                  onClick={clearFilters}
                  className="flex h-7 items-center gap-1 rounded-md px-2 font-mono text-[10px] text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
                >
                  <X className="h-2.5 w-2.5" />Clear
                </motion.button>
              )}
            </AnimatePresence>

            <div className="ml-auto flex items-center gap-2">
              {collectionStatus && (
                <span className="hidden sm:flex items-center gap-1 font-mono text-[10px] text-muted-foreground/40">
                  <Database className="h-2.5 w-2.5" />
                  {collectionStatus.total_jobs.toLocaleString()} · {statusText}
                </span>
              )}
              {data && (
                <span className="font-mono text-[10px] font-semibold text-muted-foreground tabular-nums">{data.count.toLocaleString()} results</span>
              )}
            </div>
          </div>
        </div>

        {/* Job list */}
        <div className="flex-1 overflow-y-auto px-3 py-2">
          {loading ? (
            <div className="space-y-1.5">
              {Array.from({ length: 8 }).map((_, i) => (
                <div key={i} className="rounded-lg border border-border bg-card p-3">
                  <div className="shimmer-bg h-3.5 w-3/4 rounded mb-1.5" />
                  <div className="shimmer-bg h-2.5 w-1/2 rounded mb-1.5" />
                  <div className="shimmer-bg h-2.5 w-1/3 rounded" />
                </div>
              ))}
            </div>
          ) : error ? (
            <div className="flex flex-col items-center justify-center py-16">
              <p className="font-mono text-xs text-destructive">{error}</p>
              <button onClick={loadJobs} className="mt-3 rounded-md bg-primary px-3 py-1.5 font-mono text-[11px] font-semibold text-primary-foreground">Retry</button>
            </div>
          ) : !data?.jobs.length ? (
            <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
              <Briefcase className="mb-2 h-8 w-8 opacity-15" />
              <p className="font-mono text-xs">No jobs match your filters</p>
              {activeFilterCount > 0 && (
                <button onClick={clearFilters} className="mt-3 rounded-md bg-muted px-3 py-1.5 font-mono text-[11px]">Clear filters</button>
              )}
            </div>
          ) : (
            <>
              <div className="space-y-1">
                {data.jobs.map((job, i) => (
                  <JobCard key={job.id} job={job} index={i} scoreColor={scoreColor} scoreBg={scoreBg}
                    isDismissed={dismissedIds.has(job.id)} isSaved={savedIds.has(job.id)}
                    onDismiss={handleDismiss} onSave={handleSave} />
                ))}
              </div>
              {data.total_pages > 1 && (
                <div className="flex items-center justify-center gap-1.5 mt-4 pb-3">
                  <button onClick={() => updateFilter('page', String(data.page - 1))} disabled={data.page <= 1}
                    className="rounded p-1 text-muted-foreground hover:bg-muted disabled:opacity-20">
                    <ChevronLeft className="h-3.5 w-3.5" />
                  </button>
                  <span className="font-mono text-[10px] text-muted-foreground px-1">{data.page}/{data.total_pages}</span>
                  <button onClick={() => updateFilter('page', String(data.page + 1))} disabled={data.page >= data.total_pages}
                    className="rounded p-1 text-muted-foreground hover:bg-muted disabled:opacity-20">
                    <ChevronRight className="h-3.5 w-3.5" />
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      </main>

      {/* ── Settings Panel ────────────────────────────────────────── */}
      <AnimatePresence>
        {settingsOpen && (
          <>
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              onClick={() => setSettingsOpen(false)}
              className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm" />
            <motion.aside
              initial={{ x: 340, opacity: 0 }} animate={{ x: 0, opacity: 1 }} exit={{ x: 340, opacity: 0 }}
              transition={{ type: 'spring', stiffness: 300, damping: 30 }}
              className="fixed right-0 top-0 z-50 h-full w-[380px] max-w-[92vw] border-l border-border bg-card shadow-2xl overflow-y-auto"
            >
              <SettingsPanel onClose={() => setSettingsOpen(false)} />
            </motion.aside>
          </>
        )}
      </AnimatePresence>

      {/* Settings FAB */}
      <button onClick={() => setSettingsOpen(true)}
        className={cn(
          'fixed right-3 bottom-3 z-30 flex items-center gap-1.5 rounded-lg px-3 py-2 font-mono text-[11px] font-semibold shadow-lg',
          'bg-card border border-border text-muted-foreground hover:text-foreground hover:border-primary/30 transition-all',
          settingsOpen && 'opacity-0 pointer-events-none',
        )}>
        <Settings className="h-3 w-3" />Settings
      </button>
    </div>
  )
}

// ────────────────────────────────────────────────────────────────────────
// Job Card
// ────────────────────────────────────────────────────────────────────────

function JobCard({ job, index, scoreColor, scoreBg, isDismissed, isSaved, onDismiss, onSave }: {
  job: Job; index: number
  scoreColor: (s: number | null | undefined) => string
  scoreBg: (s: number | null | undefined) => string
  isDismissed: boolean; isSaved: boolean
  onDismiss: (id: number) => void; onSave: (id: number) => void
}) {
  return (
    <motion.div custom={index} variants={jobVariants} initial="hidden" animate="visible"
      className="group/job rounded-lg border border-border/60 bg-card/60 hover:bg-card hover:border-border px-3 py-2.5 transition-all duration-150">
      <div className="flex items-start gap-3">
        {job.profile_score != null && (
          <div className={cn('flex-shrink-0 flex items-center justify-center w-9 h-9 rounded-lg font-mono text-[10px] font-bold', scoreBg(job.profile_score))}>
            {job.profile_score}
          </div>
        )}
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5 flex-wrap">
            <a href={job.url} target="_blank" rel="noopener noreferrer"
              className="font-sans text-[13px] font-semibold text-foreground hover:text-primary truncate">
              {job.title}
            </a>
            {job.is_india === 1 && (
              <span className="inline-flex items-center gap-0.5 rounded px-1 py-0.5 font-mono text-[9px] font-semibold bg-amber-500/10 text-amber-400">
                <MapPin className="h-2 w-2" />IN
              </span>
            )}
          </div>
          <div className="mt-0.5 flex items-center gap-1.5 text-[11px] text-muted-foreground flex-wrap">
            <span className="font-medium text-foreground/80">{job.company}</span>
            {job.location && <span className="flex items-center gap-0.5"><MapPin className="h-2.5 w-2.5 opacity-40" />{job.location}</span>}
            {job.salary_range && <span className="font-mono text-[10px] text-muted-foreground/50">{job.salary_range}</span>}
          </div>
          <div className="mt-1 flex items-center gap-2">
            <span className="font-mono text-[9px] uppercase tracking-wider text-muted-foreground/40">{job.source}</span>
            {job.scraped_at && <span className="flex items-center gap-0.5 text-[9px] text-muted-foreground/30"><Calendar className="h-2 w-2" />{timeAgo(job.scraped_at)}</span>}
          </div>
        </div>
        <div className="flex-shrink-0 flex items-center gap-0 opacity-0 group-hover/job:opacity-100 transition-opacity">
          <button onClick={(e) => { e.preventDefault(); onSave(job.id) }}
            className={cn('rounded p-1', isSaved ? 'bg-emerald-500/10 text-emerald-400' : 'text-muted-foreground/30 hover:text-emerald-400 hover:bg-emerald-500/5')}>
            {isSaved ? <CheckCircle2 className="h-3 w-3" /> : <ThumbsUp className="h-3 w-3" />}
          </button>
          <button onClick={(e) => { e.preventDefault(); onDismiss(job.id) }}
            className={cn('rounded p-1', isDismissed ? 'bg-red-500/10 text-red-400' : 'text-muted-foreground/30 hover:text-red-400 hover:bg-red-500/5')}>
            {isDismissed ? <X className="h-3 w-3" /> : <ThumbsDown className="h-3 w-3" />}
          </button>
          <a href={job.url} target="_blank" rel="noopener noreferrer"
            className="rounded p-1 text-muted-foreground/30 hover:text-foreground hover:bg-muted">
            <ExternalLink className="h-3 w-3" />
          </a>
        </div>
      </div>
    </motion.div>
  )
}

// ────────────────────────────────────────────────────────────────────────
// Settings Panel
// ────────────────────────────────────────────────────────────────────────

function SettingsPanel({ onClose }: { onClose: () => void }) {
  const { addToast } = useToast()
  const [profile, setProfile] = useState<Profile | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    fetchProfile().then(data => {
      setProfile(data || {
        id: null, name: '', email: '', target_roles: [], job_title_aliases: [],
        preferred_locations: [], skills: [], work_types: [], experience_years: 5,
        remote_only: false, salary_min: 0, preferred_industries: [], preferred_company_stage: [],
        enabled_sources: ALL_SOURCES, keywords_include: [], keywords_exclude: [], is_active: false,
      })
    }).catch(() => {}).finally(() => setLoading(false))
  }, [])

  if (!profile) return null

  const update = (key: string, value: unknown) => { setProfile(p => p ? { ...p, [key]: value } : p) }
  const toggleArray = (key: string, item: string) => {
    setProfile(p => {
      if (!p) return p
      const arr = p[key as keyof Profile] as string[]
      return { ...p, [key]: arr.includes(item) ? arr.filter(i => i !== item) : [...arr, item] }
    })
  }

  const handleSave = async () => {
    if (!profile) return; setSaving(true)
    try {
      const fd: Record<string, string> = {}
      if (profile.id) fd.id = String(profile.id)
      fd.name = profile.name || 'User'; fd.email = profile.email || ''
      fd.target_roles = profile.target_roles.join(',')
      fd.job_title_aliases = profile.job_title_aliases.join(',')
      fd.preferred_locations = profile.preferred_locations.join(',')
      fd.skills = profile.skills.join(',')
      fd.work_types = profile.work_types.join(',')
      fd.experience_years_min = String(profile.experience_years)
      fd.experience_years_max = String(Math.min(profile.experience_years + 10, 30))
      fd.remote_preference = profile.remote_only ? 'REMOTE' : 'ANY'
      fd.min_salary = String(profile.salary_min); fd.salary_currency = 'USD'
      fd.preferred_industries = profile.preferred_industries.join(',')
      fd.preferred_sources = profile.enabled_sources.join(',')
      fd.include_keywords = profile.keywords_include.join(',')
      fd.exclude_keywords = profile.keywords_exclude.join(',')
      fd.experience_level = 'MID'; fd.education_level = 'ANY'
      await saveProfile(fd); addToast('success', 'Saved', 'Profile updated'); onClose()
    } catch (err) { addToast('error', 'Error', err instanceof Error ? err.message : 'Failed') }
    finally { setSaving(false) }
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary/10">
            <Settings className="h-3.5 w-3.5 text-primary" />
          </div>
          <div>
            <h2 className="font-sans text-[13px] font-bold text-foreground">Settings</h2>
            <p className="font-mono text-[9px] text-muted-foreground">Profile & preferences</p>
          </div>
        </div>
        <button onClick={onClose} className="rounded p-1 text-muted-foreground hover:text-foreground hover:bg-muted">
          <X className="h-4 w-4" />
        </button>
      </div>

      {loading ? (
        <div className="flex-1 p-4 space-y-2">
          {Array.from({ length: 5 }).map((_, i) => <div key={i} className="shimmer-bg h-10 rounded-lg" />)}
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          <Section icon={<Target className="h-3 w-3" />} label="Target Roles" color="text-primary">
            <div className="flex flex-wrap gap-1">
              {ROLE_CATEGORIES.map(role => (
                <button key={role} onClick={() => toggleArray('target_roles', role)}
                  className={cn('rounded-md border px-2 py-0.5 font-mono text-[10px] font-medium transition-all',
                    profile.target_roles.includes(role)
                      ? 'border-primary bg-primary text-primary-foreground'
                      : 'border-border bg-muted text-muted-foreground hover:border-muted-foreground/20')}>{role}</button>
              ))}
            </div>
            <input
              className="mt-1.5 h-7 w-full rounded-md border-0 bg-muted px-2 font-mono text-[11px] text-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:ring-1 focus:ring-primary/30"
              value={profile.target_roles.join(', ')}
              onChange={e => update('target_roles', e.target.value.split(',').map(s => s.trim()).filter(Boolean))}
              placeholder="Or type custom roles..."
            />
          </Section>

          <Section icon={<MapPin className="h-3 w-3" />} label="Locations" color="text-emerald-400">
            <input
              className="h-7 w-full rounded-md border-0 bg-muted px-2 font-mono text-[11px] text-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:ring-1 focus:ring-primary/30"
              value={profile.preferred_locations.join(', ')}
              onChange={e => update('preferred_locations', e.target.value.split(',').map(s => s.trim()).filter(Boolean))}
              placeholder="Bengaluru, Remote, Mumbai, Delhi NCR..."
            />
            <label className="flex items-center gap-1.5 mt-1.5 cursor-pointer">
              <input type="checkbox" checked={profile.remote_only} onChange={e => update('remote_only', e.target.checked)} className="accent-primary" />
              <span className="font-mono text-[10px] text-muted-foreground">Remote only</span>
            </label>
          </Section>

          <Section icon={<Sparkles className="h-3 w-3" />} label="Skills" color="text-brand-violet">
            <input
              className="h-7 w-full rounded-md border-0 bg-muted px-2 font-mono text-[11px] text-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:ring-1 focus:ring-primary/30"
              value={profile.skills.join(', ')}
              onChange={e => update('skills', e.target.value.split(',').map(s => s.trim()).filter(Boolean))}
              placeholder="Python, React, TypeScript, AWS, Docker..."
            />
          </Section>

          <Section icon={<Briefcase className="h-3 w-3" />} label="Experience & Salary" color="text-amber-400">
            <div className="space-y-2.5">
              <div>
                <div className="flex justify-between font-mono text-[9px] text-muted-foreground mb-0.5">
                  <span>Min Experience</span><span>{profile.experience_years}y</span>
                </div>
                <input type="range" min="0" max="20" value={profile.experience_years} onChange={e => update('experience_years', parseInt(e.target.value))} className="w-full accent-primary h-1" />
              </div>
              <div>
                <div className="flex justify-between font-mono text-[9px] text-muted-foreground mb-0.5">
                  <span>Min Salary</span><span>${profile.salary_min.toLocaleString()}</span>
                </div>
                <input type="range" min="0" max="300000" step="10000" value={profile.salary_min} onChange={e => update('salary_min', parseInt(e.target.value))} className="w-full accent-emerald-500 h-1" />
              </div>
            </div>
          </Section>

          <Section icon={<SlidersHorizontal className="h-3 w-3" />} label="Work Type" color="text-brand-cyan">
            <div className="flex flex-wrap gap-1">
              {['Full-time', 'Part-time', 'Contract', 'Internship', 'Freelance'].map(wt => (
                <button key={wt} onClick={() => toggleArray('work_types', wt)}
                  className={cn('rounded-md border px-2 py-0.5 font-mono text-[10px] font-medium transition-all',
                    profile.work_types.includes(wt)
                      ? 'border-brand-cyan bg-brand-cyan/15 text-brand-cyan'
                      : 'border-border bg-muted text-muted-foreground hover:border-muted-foreground/20')}>{wt}</button>
              ))}
            </div>
          </Section>

          <Section icon={<X className="h-3 w-3" />} label="Exclude Keywords" color="text-destructive">
            <input
              className="h-7 w-full rounded-md border-0 bg-muted px-2 font-mono text-[11px] text-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:ring-1 focus:ring-primary/30"
              value={profile.keywords_exclude.join(', ')}
              onChange={e => update('keywords_exclude', e.target.value.split(',').map(s => s.trim()).filter(Boolean))}
              placeholder="Junior, internship, sales..."
            />
          </Section>
        </div>
      )}

      <div className="flex-shrink-0 px-4 py-3 border-t border-border">
        <button onClick={handleSave} disabled={saving || !profile.target_roles.length}
          className={cn('w-full rounded-lg py-2 font-sans text-xs font-bold transition-all',
            profile.target_roles.length
              ? 'bg-gradient-brand text-primary-foreground shadow-lg shadow-primary/15 hover:shadow-xl hover:shadow-primary/25'
              : 'bg-muted text-muted-foreground cursor-not-allowed')}>
          {saving ? 'Saving...' : !profile.target_roles.length ? 'Select at least one role' : 'Save Settings'}
        </button>
      </div>
    </div>
  )
}

function Section({ icon, label, color, children }: { icon: React.ReactNode; label: string; color: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="flex items-center gap-1.5 mb-1.5">
        <span className={color}>{icon}</span>
        <span className="font-sans text-[11px] font-semibold text-foreground">{label}</span>
      </div>
      {children}
    </div>
  )
}
