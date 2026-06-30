export interface RunRecord {
  run_date: string
  total_jobs: number
  unique_jobs: number
  india_jobs: number
  gh_jobs: number
  lever_jobs: number
  workday_jobs: number
  cutshort_jobs: number
  run_time_s: number
}

export interface TopCompany {
  company: string
  count: number
}

export interface TopLocation {
  location: string
  count: number
}

export interface BySource {
  [source: string]: number
}

export interface Stats {
  total: number
  unique: number
  duplicates: number
  india_count: number
  by_source: BySource
  top_companies: TopCompany[]
  top_india_locations: TopLocation[]
  recent_runs: RunRecord[]
  newest_scrape: string | null
  today_jobs: number
  classified: number
  strong: number
  good: number
  profile_matches: number
  profile_strong: number
  profile_good: number
}

import { getAccessToken } from './AuthContext'

const API_BASE = import.meta.env.DEV ? '/api' : '/api'

// ── Auth helper ─────────────────────────────────────────────────────────────
// Reads the cached Supabase access token and attaches it as a Bearer token.
// The token is kept up-to-date by AuthContext via onAuthStateChange.
// The Flask backend validates this JWT server-side using the Supabase JWT secret.

function authHeaders(): Record<string, string> {
  const token = getAccessToken()
  if (token) {
    return { Authorization: `Bearer ${token}` }
  }
  return {}
}

export async function fetchStats(): Promise<Stats> {
  const res = await fetch(`${API_BASE}/stats`, { headers: authHeaders() })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export interface TriggerResponse {
  ok: boolean
  message?: string
  error?: string
}

export async function triggerCollect(): Promise<TriggerResponse> {
  const res = await fetch(`${API_BASE}/run/collect`, {
    method: 'POST',
    headers: authHeaders(),
  })
  return res.json()
}

export function createRunSSE(
  onPhase: (data: { phase: string; message: string }) => void,
  onResult: (data: Record<string, unknown>) => void,
  onError: (data: { stage: string; error: string }) => void,
  onDone: () => void,
): EventSource {
  const es = new EventSource(`${API_BASE}/run/status`)
  es.addEventListener('phase', (e) => { try { onPhase(JSON.parse(e.data)) } catch { /* ok */ } })
  es.addEventListener('result', (e) => { try { onResult(JSON.parse(e.data)) } catch { /* ok */ } })
  es.addEventListener('error', (e: MessageEvent) => { try { onError(JSON.parse(e.data)) } catch { /* ok */ } })
  es.addEventListener('done', () => { es.close(); onDone() })
  es.onerror = () => { es.close(); onDone() }
  return es
}

// ── Jobs API ──────────────────────────────────────────────────────────────

export interface Job {
  id: number
  source: string
  source_id: string | null
  title: string
  company: string
  location: string | null
  url: string
  salary_range: string | null
  posted_at: string | null
  scraped_at: string
  is_india: number
  role_fit: string | null
  match_score: number | null
  profile_score: number | null
  profile_reasons: string | null
}

export interface JobsResponse {
  jobs: Job[]
  count: number
  page: number
  total_pages: number
  sources: string[]
  companies: string[]
}

export async function fetchJobs(filters: Record<string, string | number | undefined> = {}): Promise<JobsResponse> {
  const params = new URLSearchParams()
  Object.entries(filters).forEach(([k, v]) => { if (v !== undefined && v !== '') params.set(k, String(v)) })
  const res = await fetch(`${API_BASE}/jobs?${params}`, { headers: authHeaders() })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

// ── Profile API ───────────────────────────────────────────────────────────

export interface Profile {
  id: number | null
  name: string
  email: string
  target_roles: string[]
  job_title_aliases: string[]
  preferred_locations: string[]
  skills: string[]
  work_types: string[]
  experience_years: number
  remote_only: boolean
  salary_min: number
  preferred_industries: string[]
  preferred_company_stage: string[]
  enabled_sources: string[]
  keywords_include: string[]
  keywords_exclude: string[]
  is_active: boolean
}

export async function fetchProfile(): Promise<Profile | null> {
  const res = await fetch(`${API_BASE}/profile`, { headers: authHeaders() })
  if (res.status === 404) return null
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function saveProfile(data: Record<string, string>): Promise<{ ok: boolean; id: number }> {
  const res = await fetch(`${API_BASE}/profile`, {
    method: 'POST',
    headers: { ...authHeaders(), 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams(data),
  })
  return res.json()
}

export async function deactivateProfile(id: number): Promise<{ ok: boolean }> {
  const res = await fetch(`${API_BASE}/profile/${id}/deactivate`, {
    method: 'POST',
    headers: authHeaders(),
  })
  return res.json()
}

export async function dismissJob(jobId: number): Promise<{ ok: boolean }> {
  const res = await fetch(`${API_BASE}/jobs/${jobId}/dismiss`, {
    method: 'POST',
    headers: authHeaders(),
  })
  return res.json()
}

export async function saveJob(jobId: number): Promise<{ ok: boolean }> {
  const res = await fetch(`${API_BASE}/jobs/${jobId}/save`, {
    method: 'POST',
    headers: authHeaders(),
  })
  return res.json()
}

// ── Pipeline Status API ──────────────────────────────────────────────────

export interface SourceState {
  name: string
  label: string
  status: 'pending' | 'running' | 'completed' | 'error'
  jobs_found: number
  color: string
  gradient: string
  error?: string | null
}

export interface PipelineStatus {
  running: boolean
  phase: string | null
  phase_message: string
  elapsed_seconds: number
  sources: SourceState[]
  total_inserted: number
  total_existing: number
}

export async function fetchPipelineStatus(): Promise<PipelineStatus> {
  const res = await fetch(`${API_BASE}/run/status/pipeline`, { headers: authHeaders() })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

// ── Collection Status API ──────────────────────────────────────────────────

export interface CollectionStatus {
  last_run: RunRecord | null
  total_jobs: number
  new_today: number
  running: boolean
}

export async function fetchCollectionStatus(): Promise<CollectionStatus> {
  const res = await fetch(`${API_BASE}/collection/status`, { headers: authHeaders() })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export interface ProfileStatus {
  has_profile: boolean
  profile_id: number | null
}

export async function fetchProfileStatus(): Promise<ProfileStatus> {
  const res = await fetch(`${API_BASE}/profile/status`, { headers: authHeaders() })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

// ── History API ───────────────────────────────────────────────────────────

export async function fetchRunHistory(): Promise<RunRecord[]> {
  const res = await fetch(`${API_BASE}/history`, { headers: authHeaders() })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}
