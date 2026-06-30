import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  fetchStats,
  fetchJobs,
  fetchProfile,
  fetchPipelineStatus,
  fetchCollectionStatus,
  fetchProfileStatus,
  fetchRunHistory,
  saveProfile,
  deactivateProfile,
  dismissJob,
  saveJob,
  triggerCollect,
  type JobsResponse,
  type Profile,
  type PipelineStatus,
  type CollectionStatus,
  type ProfileStatus,
} from './api'

// ═══════════════════════════════════════════════════════════════════════════
// Query Keys
// ═══════════════════════════════════════════════════════════════════════════

export const queryKeys = {
  stats: ['stats'] as const,
  jobs: (filters: Record<string, string | number | undefined>) => ['jobs', filters] as const,
  profile: ['profile'] as const,
  pipelineStatus: ['pipeline-status'] as const,
  collectionStatus: ['collection-status'] as const,
  profileStatus: ['profile-status'] as const,
  runHistory: ['run-history'] as const,
}

// ═══════════════════════════════════════════════════════════════════════════
// Queries
// ═══════════════════════════════════════════════════════════════════════════

export function useStats() {
  return useQuery({
    queryKey: queryKeys.stats,
    queryFn: fetchStats,
    staleTime: 5 * 60 * 1000, // 5 min
    refetchOnWindowFocus: false,
  })
}

export function useJobs(filters: Record<string, string | number | undefined> = {}) {
  return useQuery({
    queryKey: queryKeys.jobs(filters),
    queryFn: ({ signal }) => fetchJobs(filters, signal),
    staleTime: 2 * 60 * 1000, // 2 min
    placeholderData: (prev) => prev, // Keep previous data while fetching
  })
}

export function useProfile() {
  return useQuery({
    queryKey: queryKeys.profile,
    queryFn: fetchProfile,
    staleTime: 10 * 60 * 1000, // 10 min
  })
}

export function usePipelineStatus(enabled: boolean = true) {
  return useQuery({
    queryKey: queryKeys.pipelineStatus,
    queryFn: fetchPipelineStatus,
    refetchInterval: enabled ? 2000 : false, // Poll every 2s when active
    staleTime: 1000,
  })
}

export function useCollectionStatus() {
  return useQuery({
    queryKey: queryKeys.collectionStatus,
    queryFn: fetchCollectionStatus,
    refetchInterval: 5 * 60 * 1000, // Every 5 min
    staleTime: 60 * 1000,
  })
}

export function useProfileStatus() {
  return useQuery({
    queryKey: queryKeys.profileStatus,
    queryFn: fetchProfileStatus,
    staleTime: 10 * 60 * 1000,
  })
}

export function useRunHistory() {
  return useQuery({
    queryKey: queryKeys.runHistory,
    queryFn: fetchRunHistory,
    staleTime: 10 * 60 * 1000,
  })
}

// ═══════════════════════════════════════════════════════════════════════════
// Mutations
// ═══════════════════════════════════════════════════════════════════════════

export function useSaveProfile() {
  const client = useQueryClient()

  return useMutation({
    mutationFn: saveProfile,
    onSuccess: () => {
      client.invalidateQueries({ queryKey: queryKeys.profile })
      client.invalidateQueries({ queryKey: queryKeys.profileStatus })
    },
  })
}

export function useDeactivateProfile() {
  const client = useQueryClient()

  return useMutation({
    mutationFn: deactivateProfile,
    onSuccess: () => {
      client.invalidateQueries({ queryKey: queryKeys.profile })
      client.invalidateQueries({ queryKey: queryKeys.profileStatus })
    },
  })
}

export function useDismissJob() {
  const client = useQueryClient()

  return useMutation({
    mutationFn: dismissJob,
    onSuccess: () => {
      // Invalidate all job queries to reflect dismissal
      client.invalidateQueries({ queryKey: ['jobs'] })
    },
  })
}

export function useSaveJob() {
  const client = useQueryClient()

  return useMutation({
    mutationFn: saveJob,
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ['jobs'] })
    },
  })
}

export function useTriggerCollect() {
  const client = useQueryClient()

  return useMutation({
    mutationFn: triggerCollect,
    onSuccess: () => {
      // Start polling pipeline status
      client.invalidateQueries({ queryKey: queryKeys.pipelineStatus })
      client.invalidateQueries({ queryKey: queryKeys.collectionStatus })
    },
  })
}
