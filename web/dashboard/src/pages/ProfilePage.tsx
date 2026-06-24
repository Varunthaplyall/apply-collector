import { useState, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { cn } from '../lib/utils'
import { fetchProfile, saveProfile, deactivateProfile, Profile } from '../lib/api'
import { useToast } from '../lib/ToastContext'
import {
  User, Save, Trash2, Loader2, CheckCircle2,
  Target, MapPin, Building2, Filter, Briefcase, Sparkles,
} from 'lucide-react'

const ALL_SOURCES = ['greenhouse', 'lever', 'workday', 'linkedin', 'cutshort', 'wellfound', 'adzuna', 'remoteok', 'remotive', 'himalayas', 'yc_jobs', 'arbeitnow', 'iimjobs', 'jsearch']

// Generic role categories — broad enough for any industry
const ROLE_CATEGORIES = [
  // Engineering & Technology
  'Software Engineer', 'Senior Software Engineer', 'Engineering Manager', 'Data Scientist',
  'DevOps Engineer', 'QA Engineer', 'Security Engineer', 'IT Support',
  // Product & Design
  'Product Manager', 'Product Designer', 'UX Designer', 'UI Designer', 'Technical Writer',
  // Marketing & Sales
  'Marketing Manager', 'Sales Representative', 'Account Executive', 'Content Writer',
  'SEO Specialist', 'Social Media Manager', 'Brand Manager',
  // Finance & Operations
  'Accountant', 'Financial Analyst', 'Operations Manager', 'Project Manager',
  'Business Analyst', 'HR Manager', 'Recruiter', 'Office Manager',
  // Healthcare
  'Nurse', 'Doctor', 'Pharmacist', 'Medical Assistant', 'Lab Technician',
  // Education
  'Teacher', 'Professor', 'Teaching Assistant', 'Curriculum Designer',
  // Other / Custom
  'Customer Support', 'Administrative Assistant', 'Consultant', 'Freelancer',
]

// Broad industry categories
const INDUSTRIES = [
  'Technology', 'Healthcare', 'Finance & Banking', 'Education', 'Retail & E-commerce',
  'Manufacturing', 'Construction', 'Media & Entertainment', 'Government',
  'Nonprofit', 'Consulting', 'Legal', 'Real Estate', 'Hospitality & Tourism',
  'Transportation', 'Energy', 'Agriculture', 'Pharmaceuticals',
]

const defaultProfile: Profile = {
  id: null, name: '', email: '', target_roles: [], job_title_aliases: [],
  preferred_locations: [], skills: [], work_types: [], experience_years: 5,
  remote_only: false, salary_min: 0, preferred_industries: [],
  preferred_company_stage: [], enabled_sources: ALL_SOURCES,
  keywords_include: [], keywords_exclude: [], is_active: false,
}

export default function ProfilePage() {
  const { addToast } = useToast()
  const [profile, setProfile] = useState<Profile>(defaultProfile)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadProfile = useCallback(async () => {
    setLoading(true)
    try {
      const data = await fetchProfile()
      if (data) setProfile(data)
    } catch {
      // Stay with defaults
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadProfile() }, [loadProfile])

  const update = (key: keyof Profile, value: unknown) => {
    setProfile(p => ({ ...p, [key]: value }))
  }

  const toggleArray = (key: keyof Profile, item: string) => {
    setProfile(p => {
      const arr = p[key] as string[]
      return { ...p, [key]: arr.includes(item) ? arr.filter(i => i !== item) : [...arr, item] }
    })
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setError(null)
    try {
      const formData: Record<string, string> = {}
      if (profile.id) formData.id = String(profile.id)
      formData.name = profile.name
      formData.email = profile.email
      formData.target_roles = profile.target_roles.join(',')
      formData.job_title_aliases = profile.job_title_aliases.join(',')
      formData.preferred_locations = profile.preferred_locations.join(',')
      formData.skills = profile.skills.join(',')
      formData.work_types = profile.work_types.join(',')
      formData.experience_years_min = String(profile.experience_years)
      formData.experience_years_max = String(Math.min(profile.experience_years + 10, 30))
      formData.remote_preference = profile.remote_only ? 'REMOTE' : 'ANY'
      formData.min_salary = String(profile.salary_min)
      formData.salary_currency = 'USD'
      formData.preferred_industries = profile.preferred_industries.join(',')
      formData.preferred_sources = profile.enabled_sources.join(',')
      formData.include_keywords = profile.keywords_include.join(',')
      formData.exclude_keywords = profile.keywords_exclude.join(',')
      formData.experience_level = 'MID'
      formData.education_level = 'ANY'

      await saveProfile(formData)
      setSaved(true)
      addToast('success', 'Profile Saved', 'Your preferences have been updated')
      setTimeout(() => setSaved(false), 3000)
      await loadProfile()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save')
      addToast('error', 'Save Failed', err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setSaving(false)
    }
  }

  const handleDeactivate = async () => {
    if (!profile.id) return
    await deactivateProfile(profile.id)
    setProfile(defaultProfile)
    addToast('info', 'Profile Deactivated', 'Your profile has been deactivated')
  }

  if (loading) {
    return (
      <main className="mx-auto max-w-[780px] px-4 sm:px-6 lg:px-8 pb-16">
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="mt-8 space-y-4"
        >
          <div className="shimmer-bg h-8 w-48 rounded-lg" />
          {Array.from({ length: 6 }).map((_, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.06 }}
              className="shimmer-bg h-20 rounded-xl"
            />
          ))}
        </motion.div>
      </main>
    )
  }

  return (
    <main className="mx-auto max-w-[780px] px-4 sm:px-6 lg:px-8 pb-16">
      <motion.section
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        className="mb-6 mt-8"
      >
        <div className="mb-2 flex items-center gap-3">
          <motion.div
            initial={{ scaleY: 0 }}
            animate={{ scaleY: 1 }}
            transition={{ duration: 0.4 }}
            className="h-8 w-1 rounded-full bg-gradient-brand origin-bottom"
          />
          <h2 className="font-display text-2xl font-bold tracking-tight text-foreground sm:text-3xl">
            Candidate Profile
          </h2>
          <AnimatePresence>
            {profile.is_active && (
              <motion.span
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.8 }}
                className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2.5 py-0.5 font-mono text-[10px] font-bold text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400"
              >
                <CheckCircle2 className="h-3 w-3" /> Active
              </motion.span>
            )}
          </AnimatePresence>
        </div>
        <p className="text-sm text-muted-foreground">
          Set your target roles and preferences. The pipeline will find and score jobs matched to what you're looking for.
        </p>
      </motion.section>

      <motion.form
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        onSubmit={handleSubmit}
        className="space-y-6"
      >
        {/* Basic Info */}
        <motion.fieldset
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.25 }}
          className="rounded-xl border bg-card p-5 shadow-sm sm:p-6"
        >
          <legend className="flex items-center gap-2 font-display text-base font-bold tracking-tight text-foreground">
            <div className="flex h-6 w-6 items-center justify-center rounded-lg bg-brand-blue/10">
              <User className="h-3.5 w-3.5 text-brand-blue" />
            </div>
            Basic Info
          </legend>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <Field label="Name" required>
              <input className="h-10 w-full rounded-xl border bg-background px-3 font-mono text-sm transition-all duration-200 focus:border-brand-blue focus:outline-none focus:ring-2 focus:ring-brand-blue/20" value={profile.name} onChange={e => update('name', e.target.value)} placeholder="Your full name" />
            </Field>
            <Field label="Email">
              <input className="h-10 w-full rounded-xl border bg-background px-3 font-mono text-sm transition-all duration-200 focus:border-brand-blue focus:outline-none focus:ring-2 focus:ring-brand-blue/20" type="email" value={profile.email} onChange={e => update('email', e.target.value)} placeholder="you@example.com" />
            </Field>
          </div>
        </motion.fieldset>

        {/* Target Roles */}
        <motion.fieldset
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="rounded-xl border bg-card p-5 shadow-sm sm:p-6"
        >
          <legend className="flex items-center gap-2 font-display text-base font-bold tracking-tight text-foreground">
            <div className="flex h-6 w-6 items-center justify-center rounded-lg bg-brand-violet/10">
              <Target className="h-3.5 w-3.5 text-brand-violet" />
            </div>
            Target Roles
          </legend>
          <p className="mt-1 text-xs text-muted-foreground mb-3">Select the roles you're targeting <span className="text-destructive">*</span></p>
          <div className="flex flex-wrap gap-2">
            {ROLE_CATEGORIES.map(role => (
              <motion.button
                key={role}
                type="button"
                whileHover={{ scale: 1.04 }}
                whileTap={{ scale: 0.96 }}
                onClick={() => toggleArray('target_roles', role)}
                className={cn(
                  'rounded-xl border px-3 py-1.5 text-xs font-medium transition-all duration-200',
                  profile.target_roles.includes(role)
                    ? 'border-brand-violet bg-brand-violet text-primary-foreground shadow-sm'
                    : 'border-border bg-background text-muted-foreground hover:border-brand-violet/50 hover:text-foreground',
                )}
              >
                {role}
              </motion.button>
            ))}
          </div>
          {profile.target_roles.length === 0 && (
            <p className="mt-2 text-xs text-muted-foreground italic">
              Or type a custom role below
            </p>
          )}
          <div className="mt-3">
            <input
              className="h-10 w-full rounded-xl border bg-background px-3 font-mono text-sm transition-all duration-200 focus:border-brand-blue focus:outline-none focus:ring-2 focus:ring-brand-blue/20"
              value={profile.target_roles.join(', ')}
              onChange={e => update('target_roles', e.target.value.split(',').map(s => s.trim()).filter(Boolean))}
              placeholder="Or type custom roles, comma-separated (e.g. Architect, Lawyer, Chef)"
            />
          </div>
        </motion.fieldset>

        {/* Locations */}
        <motion.fieldset
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.35 }}
          className="rounded-xl border bg-card p-5 shadow-sm sm:p-6"
        >
          <legend className="flex items-center gap-2 font-display text-base font-bold tracking-tight text-foreground">
            <div className="flex h-6 w-6 items-center justify-center rounded-lg bg-emerald-100 dark:bg-emerald-900/30">
              <MapPin className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400" />
            </div>
            Preferred Locations
          </legend>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <Field label="Location cities/states (comma-separated)">
              <input className="h-10 w-full rounded-xl border bg-background px-3 font-mono text-sm transition-all duration-200 focus:border-brand-blue focus:outline-none focus:ring-2 focus:ring-brand-blue/20" value={profile.preferred_locations.join(', ')} onChange={e => update('preferred_locations', e.target.value.split(',').map(s => s.trim()).filter(Boolean))} placeholder="Bengaluru, Remote India, Mumbai" />
            </Field>
            <div className="flex items-end gap-4">
              <label className="flex items-center gap-2 rounded-xl border bg-background px-3 h-10 cursor-pointer hover:bg-secondary/50 transition-colors">
                <input type="checkbox" checked={profile.remote_only} onChange={e => update('remote_only', e.target.checked)} className="accent-brand-blue" />
                <span className="font-mono text-xs font-medium">Remote only</span>
              </label>
            </div>
          </div>
        </motion.fieldset>

        {/* Preferences */}
        <motion.fieldset
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
          className="rounded-xl border bg-card p-5 shadow-sm sm:p-6"
        >
          <legend className="flex items-center gap-2 font-display text-base font-bold tracking-tight text-foreground">
            <div className="flex h-6 w-6 items-center justify-center rounded-lg bg-amber-100 dark:bg-amber-900/30">
              <Briefcase className="h-3.5 w-3.5 text-amber-600 dark:text-amber-400" />
            </div>
            Job Preferences
          </legend>

          <div className="mt-4">
            <p className="mb-2 text-xs text-muted-foreground font-semibold uppercase tracking-wider">Work Type</p>
            <div className="flex flex-wrap gap-2">
              {['Full-time', 'Part-time', 'Contract', 'Internship', 'Freelance'].map(wt => (
                <motion.button
                  key={wt}
                  type="button"
                  whileHover={{ scale: 1.04 }}
                  whileTap={{ scale: 0.96 }}
                  onClick={() => toggleArray('work_types', wt)}
                  className={cn(
                    'rounded-xl border px-3 py-1.5 text-xs font-medium transition-all duration-200',
                    profile.work_types.includes(wt)
                      ? 'border-brand-amber bg-brand-amber text-primary-foreground shadow-sm'
                      : 'border-border bg-background text-muted-foreground hover:border-brand-amber/50 hover:text-foreground',
                  )}
                >
                  {wt}
                </motion.button>
              ))}
            </div>
          </div>

          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <Field label={`Min Experience: ${profile.experience_years} years`}>
              <input type="range" min="0" max="20" value={profile.experience_years} onChange={e => update('experience_years', parseInt(e.target.value))} className="w-full accent-brand-blue" />
            </Field>
            <Field label={`Min Salary: $${profile.salary_min.toLocaleString()}`}>
              <input type="range" min="0" max="300000" step="10000" value={profile.salary_min} onChange={e => update('salary_min', parseInt(e.target.value))} className="w-full accent-brand-emerald" />
            </Field>
          </div>

          {/* Industries */}
          <div className="mt-4">
            <p className="mb-2 text-xs text-muted-foreground font-semibold uppercase tracking-wider">Industries</p>
            <div className="flex flex-wrap gap-2">
              {INDUSTRIES.map(ind => (
                <motion.button
                  key={ind}
                  type="button"
                  whileHover={{ scale: 1.04 }}
                  whileTap={{ scale: 0.96 }}
                  onClick={() => toggleArray('preferred_industries', ind)}
                  className={cn(
                    'rounded-xl border px-3 py-1.5 text-xs font-medium transition-all duration-200',
                    profile.preferred_industries.includes(ind)
                      ? 'border-brand-cyan bg-brand-cyan text-primary-foreground shadow-sm'
                      : 'border-border bg-background text-muted-foreground hover:border-brand-cyan/50 hover:text-foreground',
                  )}
                >
                  {ind}
                </motion.button>
              ))}
            </div>
          </div>
        </motion.fieldset>

        {/* Sources */}
        <motion.fieldset
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.45 }}
          className="rounded-xl border bg-card p-5 shadow-sm sm:p-6"
        >
          <legend className="flex items-center gap-2 font-display text-base font-bold tracking-tight text-foreground">
            <div className="flex h-6 w-6 items-center justify-center rounded-lg bg-rose-100 dark:bg-rose-900/30">
              <Filter className="h-3.5 w-3.5 text-rose-600 dark:text-rose-400" />
            </div>
            Enabled Sources
          </legend>
          <div className="mt-4 flex flex-wrap gap-2">
            {ALL_SOURCES.map(src => (
              <motion.button
                key={src}
                type="button"
                whileHover={{ scale: 1.04 }}
                whileTap={{ scale: 0.96 }}
                onClick={() => toggleArray('enabled_sources', src)}
                className={cn(
                  'rounded-xl border px-3 py-1.5 text-xs font-medium transition-all duration-200 font-mono',
                  profile.enabled_sources.includes(src)
                    ? 'border-primary bg-gradient-brand text-primary-foreground shadow-sm'
                    : 'border-border bg-background text-muted-foreground hover:border-brand-blue/50 hover:text-foreground',
                )}
              >
                {src}
              </motion.button>
            ))}
          </div>
        </motion.fieldset>

        {/* Actions */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5 }}
          className="flex items-center gap-3"
        >
          <motion.button
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.97 }}
            type="submit"
            disabled={saving}
            className="inline-flex items-center gap-2 rounded-xl bg-gradient-brand px-6 py-2.5 font-display text-sm font-bold text-primary-foreground shadow-lg shadow-brand-blue/25 transition-shadow hover:shadow-xl hover:shadow-brand-blue/30 disabled:opacity-50"
          >
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
            {saving ? 'Saving...' : 'Save Profile'}
          </motion.button>
          <AnimatePresence>
            {saved && (
              <motion.span
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -8 }}
                className="inline-flex items-center gap-1 font-mono text-xs font-semibold text-emerald-600 dark:text-emerald-400"
              >
                <CheckCircle2 className="h-3.5 w-3.5" /> Saved!
              </motion.span>
            )}
          </AnimatePresence>
          {error && <span className="font-mono text-xs text-destructive">{error}</span>}
          {profile.id && (
            <motion.button
              whileHover={{ scale: 1.03 }}
              whileTap={{ scale: 0.97 }}
              type="button"
              onClick={handleDeactivate}
              className="ml-auto inline-flex items-center gap-2 rounded-xl border border-destructive/30 px-4 py-2.5 font-mono text-xs font-semibold text-destructive transition-all hover:bg-destructive/10"
            >
              <Trash2 className="h-3.5 w-3.5" /> Deactivate
            </motion.button>
          )}
        </motion.div>
      </motion.form>
    </main>
  )
}

function Field({ label, required, children }: { label: string; required?: boolean; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <label className="font-mono text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
        {label}{required && <span className="text-destructive ml-0.5">*</span>}
      </label>
      {children}
    </div>
  )
}
