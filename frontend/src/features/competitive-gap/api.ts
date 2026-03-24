import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiRequest } from '../../api/client'
import { queryKeys } from '../../api/queryKeys'
import type {
  CompetitiveGapExplanationRequest,
  CompetitiveGapExplanationResponse,
  CompetitiveGapSemanticRerunRequest,
  CompetitiveGapSemanticRerunResponse,
  CompetitiveGapStrategy,
  NormalizedCompetitiveGapStrategy,
  PaginatedCompetitiveGapResponse,
  PaginatedSiteCompetitorReviewResponse,
  SiteCompetitiveGapQueryParams,
  SiteContentGapReviewRun,
  SiteCompetitor,
  SiteCompetitorReviewStatus,
  SiteCompetitorSyncRun,
  SiteCompetitorSyncAllResponse,
} from '../../types/api'
import { buildQueryString } from '../../utils/searchParams'

export type { SiteCompetitiveGapQueryParams } from '../../types/api'

export interface CompetitiveGapStrategyUpsertInput {
  raw_user_input: string
  normalized_strategy_json?: NormalizedCompetitiveGapStrategy | null
}

export interface SiteCompetitorCreateInput {
  root_url: string
  label?: string
  notes?: string
  is_active?: boolean
}

export interface SiteCompetitorUpdateInput {
  root_url?: string
  label?: string
  notes?: string
  is_active?: boolean
}

export interface SiteCompetitorReviewQueryParams {
  review_status?: SiteCompetitorReviewStatus | 'all'
  page?: number
  page_size?: number
}

function buildSiteCompetitiveGapSearch(params: SiteCompetitiveGapQueryParams) {
  return buildQueryString(params)
}

export async function getSiteCompetitiveGapStrategy(siteId: number) {
  return apiRequest<CompetitiveGapStrategy | null>(`/sites/${siteId}/competitive-content-gap/strategy`)
}

export async function upsertSiteCompetitiveGapStrategy(
  siteId: number,
  payload: CompetitiveGapStrategyUpsertInput,
) {
  return apiRequest<CompetitiveGapStrategy>(`/sites/${siteId}/competitive-content-gap/strategy`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export async function deleteSiteCompetitiveGapStrategy(siteId: number) {
  return apiRequest<void>(`/sites/${siteId}/competitive-content-gap/strategy`, {
    method: 'DELETE',
  })
}

export async function getSiteCompetitiveGapCompetitors(siteId: number) {
  return apiRequest<SiteCompetitor[]>(`/sites/${siteId}/competitive-content-gap/competitors`)
}

export async function createSiteCompetitiveGapCompetitor(siteId: number, payload: SiteCompetitorCreateInput) {
  return apiRequest<SiteCompetitor>(`/sites/${siteId}/competitive-content-gap/competitors`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function updateSiteCompetitiveGapCompetitor(
  siteId: number,
  competitorId: number,
  payload: SiteCompetitorUpdateInput,
) {
  return apiRequest<SiteCompetitor>(`/sites/${siteId}/competitive-content-gap/competitors/${competitorId}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export async function deleteSiteCompetitiveGapCompetitor(siteId: number, competitorId: number) {
  return apiRequest<void>(`/sites/${siteId}/competitive-content-gap/competitors/${competitorId}`, {
    method: 'DELETE',
  })
}

export async function syncSiteCompetitiveGapCompetitor(siteId: number, competitorId: number) {
  return apiRequest<SiteCompetitor>(`/sites/${siteId}/competitive-content-gap/competitors/${competitorId}/sync`, {
    method: 'POST',
  })
}

export async function resetSiteCompetitiveGapCompetitorSync(siteId: number, competitorId: number) {
  return apiRequest<SiteCompetitor>(`/sites/${siteId}/competitive-content-gap/competitors/${competitorId}/reset-sync`, {
    method: 'POST',
  })
}

export async function getSiteCompetitiveGapCompetitorSyncRuns(siteId: number, competitorId: number, limit = 5) {
  const query = buildQueryString({ limit })
  const suffix = query ? `?${query}` : ''
  return apiRequest<SiteCompetitorSyncRun[]>(
    `/sites/${siteId}/competitive-content-gap/competitors/${competitorId}/sync-runs${suffix}`,
  )
}

export async function getSiteCompetitiveGapReviewRuns(siteId: number, limit = 5) {
  const query = buildQueryString({ limit })
  const suffix = query ? `?${query}` : ''
  return apiRequest<SiteContentGapReviewRun[]>(`/sites/${siteId}/competitive-content-gap/review-runs${suffix}`)
}

export async function retrySiteCompetitiveGapReviewRun(siteId: number, runId: number) {
  return apiRequest<SiteContentGapReviewRun>(`/sites/${siteId}/competitive-content-gap/review-runs/${runId}/retry`, {
    method: 'POST',
  })
}

export async function getSiteCompetitiveGapCompetitorReview(
  siteId: number,
  competitorId: number,
  params: SiteCompetitorReviewQueryParams = {},
) {
  const query = buildQueryString({
    review_status: params.review_status,
    page: params.page,
    page_size: params.page_size,
  })
  const suffix = query ? `?${query}` : ''
  return apiRequest<PaginatedSiteCompetitorReviewResponse>(
    `/sites/${siteId}/competitive-content-gap/competitors/${competitorId}/page-review${suffix}`,
  )
}

export async function retrySiteCompetitiveGapCompetitorSync(siteId: number, competitorId: number) {
  return apiRequest<SiteCompetitor>(`/sites/${siteId}/competitive-content-gap/competitors/${competitorId}/retry-sync`, {
    method: 'POST',
  })
}

export async function syncAllSiteCompetitiveGapCompetitors(siteId: number) {
  return apiRequest<SiteCompetitorSyncAllResponse>(`/sites/${siteId}/competitive-content-gap/competitors/sync-all`, {
    method: 'POST',
  })
}

export async function getSiteCompetitiveGap(siteId: number, params: SiteCompetitiveGapQueryParams) {
  const query = buildSiteCompetitiveGapSearch(params)
  const suffix = query ? `?${query}` : ''
  return apiRequest<PaginatedCompetitiveGapResponse>(`/sites/${siteId}/competitive-content-gap${suffix}`)
}

export async function createCompetitiveGapExplanation(
  siteId: number,
  payload: CompetitiveGapExplanationRequest,
) {
  return apiRequest<CompetitiveGapExplanationResponse>(`/sites/${siteId}/competitive-content-gap/explanation`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function rerunSiteCompetitiveGapSemanticMatching(
  siteId: number,
  payload: CompetitiveGapSemanticRerunRequest,
) {
  return apiRequest<CompetitiveGapSemanticRerunResponse>(
    `/sites/${siteId}/competitive-content-gap/semantic/re-run`,
    {
      method: 'POST',
      body: JSON.stringify(payload),
    },
  )
}

export function useSiteCompetitiveGapStrategyQuery(siteId: number) {
  return useQuery({
    queryKey: queryKeys.siteCompetitiveGapStrategy(siteId),
    queryFn: () => getSiteCompetitiveGapStrategy(siteId),
  })
}

export function useSiteCompetitiveGapCompetitorsQuery(siteId: number) {
  return useQuery({
    queryKey: queryKeys.siteCompetitiveGapCompetitors(siteId),
    queryFn: () => getSiteCompetitiveGapCompetitors(siteId),
  })
}

export function useSiteCompetitiveGapCompetitorSyncRunsQuery(
  siteId: number,
  competitorId: number,
  limit = 5,
  enabled = true,
  refetchInterval: number | false = false,
) {
  return useQuery({
    queryKey: queryKeys.siteCompetitiveGapCompetitorSyncRuns(siteId, competitorId, limit),
    queryFn: () => getSiteCompetitiveGapCompetitorSyncRuns(siteId, competitorId, limit),
    enabled,
    refetchInterval,
  })
}

export function useSiteCompetitiveGapReviewRunsQuery(
  siteId: number,
  limit = 5,
  enabled = true,
  refetchInterval: number | false = false,
) {
  return useQuery({
    queryKey: queryKeys.siteCompetitiveGapReviewRuns(siteId, limit),
    queryFn: () => getSiteCompetitiveGapReviewRuns(siteId, limit),
    enabled,
    refetchInterval,
  })
}

export function useSiteCompetitiveGapCompetitorReviewQuery(
  siteId: number,
  competitorId: number,
  params: SiteCompetitorReviewQueryParams,
  enabled = true,
) {
  const search = buildQueryString({
    review_status: params.review_status,
    page: params.page,
    page_size: params.page_size,
  })
  return useQuery({
    queryKey: ['sites', siteId, 'competitive-gap', 'competitors', competitorId, 'page-review', search],
    queryFn: () => getSiteCompetitiveGapCompetitorReview(siteId, competitorId, params),
    enabled,
  })
}

export function useSiteCompetitiveGapQuery(siteId: number, params: SiteCompetitiveGapQueryParams, enabled = true) {
  const search = buildSiteCompetitiveGapSearch(params)

  return useQuery({
    queryKey: queryKeys.siteCompetitiveGap(siteId, search),
    queryFn: () => getSiteCompetitiveGap(siteId, params),
    enabled,
  })
}

export function useUpsertSiteCompetitiveGapStrategyMutation(siteId: number) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (payload: CompetitiveGapStrategyUpsertInput) => upsertSiteCompetitiveGapStrategy(siteId, payload),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.siteCompetitiveGapStrategy(siteId) }),
        queryClient.invalidateQueries({ queryKey: ['sites', siteId, 'competitive-gap'] }),
      ])
    },
  })
}

export function useDeleteSiteCompetitiveGapStrategyMutation(siteId: number) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: () => deleteSiteCompetitiveGapStrategy(siteId),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.siteCompetitiveGapStrategy(siteId) }),
        queryClient.invalidateQueries({ queryKey: ['sites', siteId, 'competitive-gap'] }),
      ])
    },
  })
}

export function useCreateSiteCompetitiveGapCompetitorMutation(siteId: number) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (payload: SiteCompetitorCreateInput) => createSiteCompetitiveGapCompetitor(siteId, payload),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.siteCompetitiveGapCompetitors(siteId) }),
        queryClient.invalidateQueries({ queryKey: ['sites', siteId, 'competitive-gap'] }),
      ])
    },
  })
}

export function useUpdateSiteCompetitiveGapCompetitorMutation(siteId: number) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ competitorId, payload }: { competitorId: number; payload: SiteCompetitorUpdateInput }) =>
      updateSiteCompetitiveGapCompetitor(siteId, competitorId, payload),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.siteCompetitiveGapCompetitors(siteId) }),
        queryClient.invalidateQueries({ queryKey: ['sites', siteId, 'competitive-gap'] }),
      ])
    },
  })
}

export function useDeleteSiteCompetitiveGapCompetitorMutation(siteId: number) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (competitorId: number) => deleteSiteCompetitiveGapCompetitor(siteId, competitorId),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.siteCompetitiveGapCompetitors(siteId) }),
        queryClient.invalidateQueries({ queryKey: ['sites', siteId, 'competitive-gap'] }),
      ])
    },
  })
}

export function useSyncSiteCompetitiveGapCompetitorMutation(siteId: number) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (competitorId: number) => syncSiteCompetitiveGapCompetitor(siteId, competitorId),
    onSuccess: async (_data, competitorId) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.siteCompetitiveGapCompetitors(siteId) }),
        queryClient.invalidateQueries({ queryKey: queryKeys.siteCompetitiveGapCompetitorSyncRuns(siteId, competitorId, 5) }),
        queryClient.invalidateQueries({ queryKey: ['sites', siteId, 'competitive-gap'] }),
      ])
    },
  })
}

export function useResetSiteCompetitiveGapCompetitorSyncMutation(siteId: number) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (competitorId: number) => resetSiteCompetitiveGapCompetitorSync(siteId, competitorId),
    onSuccess: async (_data, competitorId) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.siteCompetitiveGapCompetitors(siteId) }),
        queryClient.invalidateQueries({ queryKey: queryKeys.siteCompetitiveGapCompetitorSyncRuns(siteId, competitorId, 5) }),
        queryClient.invalidateQueries({ queryKey: ['sites', siteId, 'competitive-gap'] }),
      ])
    },
  })
}

export function useRetrySiteCompetitiveGapCompetitorSyncMutation(siteId: number) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (competitorId: number) => retrySiteCompetitiveGapCompetitorSync(siteId, competitorId),
    onSuccess: async (_data, competitorId) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.siteCompetitiveGapCompetitors(siteId) }),
        queryClient.invalidateQueries({ queryKey: queryKeys.siteCompetitiveGapCompetitorSyncRuns(siteId, competitorId, 5) }),
        queryClient.invalidateQueries({ queryKey: ['sites', siteId, 'competitive-gap'] }),
      ])
    },
  })
}

export function useRetrySiteCompetitiveGapReviewRunMutation(siteId: number) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (runId: number) => retrySiteCompetitiveGapReviewRun(siteId, runId),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.siteCompetitiveGapReviewRuns(siteId, 5) }),
        queryClient.invalidateQueries({ queryKey: ['sites', siteId, 'competitive-gap'] }),
      ])
    },
  })
}

export function useSyncAllSiteCompetitiveGapCompetitorsMutation(siteId: number) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: () => syncAllSiteCompetitiveGapCompetitors(siteId),
    onSuccess: async (data) => {
      const syncRunInvalidations = data.queued_competitor_ids.map((competitorId) =>
        queryClient.invalidateQueries({ queryKey: queryKeys.siteCompetitiveGapCompetitorSyncRuns(siteId, competitorId, 5) }),
      )
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.siteCompetitiveGapCompetitors(siteId) }),
        queryClient.invalidateQueries({ queryKey: ['sites', siteId, 'competitive-gap'] }),
        ...syncRunInvalidations,
      ])
    },
  })
}

export function useCompetitiveGapExplanationMutation(siteId: number) {
  return useMutation({
    mutationFn: (payload: CompetitiveGapExplanationRequest) => createCompetitiveGapExplanation(siteId, payload),
  })
}

export function useRerunSiteCompetitiveGapSemanticMatchingMutation(siteId: number) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (payload: CompetitiveGapSemanticRerunRequest) => rerunSiteCompetitiveGapSemanticMatching(siteId, payload),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.siteCompetitiveGapCompetitors(siteId) }),
        queryClient.invalidateQueries({ queryKey: ['sites', siteId, 'competitive-gap'] }),
      ])
    },
  })
}
