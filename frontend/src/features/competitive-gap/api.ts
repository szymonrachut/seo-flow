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
  SemstormDiscoveryRun,
  SemstormDiscoveryRunCreateInput,
  SemstormDiscoveryRunListItem,
  SemstormCreatePlanInput,
  SemstormCreatePlanResponse,
  SemstormCreateBriefInput,
  SemstormCreateBriefResponse,
  SemstormOpportunityActionInput,
  SemstormOpportunityActionResponse,
  SemstormOpportunitiesQueryParams,
  SemstormOpportunitiesResponse,
  SemstormBriefsQueryParams,
  SemstormBriefsResponse,
  SemstormBriefItem,
  SemstormBriefEnrichmentApplyResponse,
  SemstormBriefEnrichmentRun,
  SemstormBriefEnrichmentRunsResponse,
  SemstormBriefExecutionStatusUpdateInput,
  SemstormBriefImplementationStatusUpdateInput,
  SemstormBriefExecutionUpdateInput,
  SemstormBriefStatusUpdateInput,
  SemstormBriefUpdateInput,
  SemstormImplementedQueryParams,
  SemstormImplementedResponse,
  SemstormPlansQueryParams,
  SemstormPlansResponse,
  SemstormPlanItem,
  SemstormPlanStatusUpdateInput,
  SemstormPlanUpdateInput,
  SemstormPromotedItemsResponse,
  SemstormExecutionQueryParams,
  SemstormExecutionResponse,
} from '../../types/api'
import { buildQueryString } from '../../utils/searchParams'

export type {
  SiteCompetitiveGapQueryParams,
  SemstormDiscoveryRunCreateInput,
  SemstormOpportunitiesQueryParams,
  SemstormBriefsQueryParams,
  SemstormPlansQueryParams,
  SemstormExecutionQueryParams,
  SemstormImplementedQueryParams,
} from '../../types/api'

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

function buildSiteCompetitiveGapSemstormOpportunitiesSearch(params: SemstormOpportunitiesQueryParams) {
  return buildQueryString(params)
}

function buildSiteCompetitiveGapSemstormPlansSearch(params: SemstormPlansQueryParams) {
  return buildQueryString(params)
}

function buildSiteCompetitiveGapSemstormBriefsSearch(params: SemstormBriefsQueryParams) {
  return buildQueryString(params)
}

function buildSiteCompetitiveGapSemstormExecutionSearch(params: SemstormExecutionQueryParams) {
  return buildQueryString(params)
}

function buildSiteCompetitiveGapSemstormImplementedSearch(params: SemstormImplementedQueryParams) {
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

export async function createSiteCompetitiveGapSemstormDiscoveryRun(
  siteId: number,
  payload: SemstormDiscoveryRunCreateInput,
) {
  return apiRequest<SemstormDiscoveryRun>(`/sites/${siteId}/competitive-content-gap/semstorm/discovery-runs`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function getSiteCompetitiveGapSemstormDiscoveryRuns(siteId: number) {
  return apiRequest<SemstormDiscoveryRunListItem[]>(
    `/sites/${siteId}/competitive-content-gap/semstorm/discovery-runs`,
  )
}

export async function getSiteCompetitiveGapSemstormDiscoveryRun(siteId: number, runId: number) {
  return apiRequest<SemstormDiscoveryRun>(
    `/sites/${siteId}/competitive-content-gap/semstorm/discovery-runs/${runId}`,
  )
}

export async function getSiteCompetitiveGapSemstormOpportunities(
  siteId: number,
  params: SemstormOpportunitiesQueryParams = {},
) {
  const query = buildSiteCompetitiveGapSemstormOpportunitiesSearch(params)
  const suffix = query ? `?${query}` : ''
  return apiRequest<SemstormOpportunitiesResponse>(
    `/sites/${siteId}/competitive-content-gap/semstorm/opportunities${suffix}`,
  )
}

export async function acceptSiteCompetitiveGapSemstormOpportunities(
  siteId: number,
  payload: SemstormOpportunityActionInput,
) {
  return apiRequest<SemstormOpportunityActionResponse>(
    `/sites/${siteId}/competitive-content-gap/semstorm/opportunities/actions/accept`,
    {
      method: 'POST',
      body: JSON.stringify(payload),
    },
  )
}

export async function dismissSiteCompetitiveGapSemstormOpportunities(
  siteId: number,
  payload: SemstormOpportunityActionInput,
) {
  return apiRequest<SemstormOpportunityActionResponse>(
    `/sites/${siteId}/competitive-content-gap/semstorm/opportunities/actions/dismiss`,
    {
      method: 'POST',
      body: JSON.stringify(payload),
    },
  )
}

export async function promoteSiteCompetitiveGapSemstormOpportunities(
  siteId: number,
  payload: SemstormOpportunityActionInput,
) {
  return apiRequest<SemstormOpportunityActionResponse>(
    `/sites/${siteId}/competitive-content-gap/semstorm/opportunities/actions/promote`,
    {
      method: 'POST',
      body: JSON.stringify(payload),
    },
  )
}

export async function getSiteCompetitiveGapSemstormPromoted(siteId: number) {
  return apiRequest<SemstormPromotedItemsResponse>(
    `/sites/${siteId}/competitive-content-gap/semstorm/promoted`,
  )
}

export async function createSiteCompetitiveGapSemstormPlans(
  siteId: number,
  payload: SemstormCreatePlanInput,
) {
  return apiRequest<SemstormCreatePlanResponse>(
    `/sites/${siteId}/competitive-content-gap/semstorm/promoted/actions/create-plan`,
    {
      method: 'POST',
      body: JSON.stringify(payload),
    },
  )
}

export async function getSiteCompetitiveGapSemstormPlans(
  siteId: number,
  params: SemstormPlansQueryParams = {},
) {
  const query = buildSiteCompetitiveGapSemstormPlansSearch(params)
  const suffix = query ? `?${query}` : ''
  return apiRequest<SemstormPlansResponse>(
    `/sites/${siteId}/competitive-content-gap/semstorm/plans${suffix}`,
  )
}

export async function getSiteCompetitiveGapSemstormPlan(siteId: number, planId: number) {
  return apiRequest<SemstormPlanItem>(
    `/sites/${siteId}/competitive-content-gap/semstorm/plans/${planId}`,
  )
}

export async function updateSiteCompetitiveGapSemstormPlanStatus(
  siteId: number,
  planId: number,
  payload: SemstormPlanStatusUpdateInput,
) {
  return apiRequest<SemstormPlanItem>(
    `/sites/${siteId}/competitive-content-gap/semstorm/plans/${planId}/status`,
    {
      method: 'POST',
      body: JSON.stringify(payload),
    },
  )
}

export async function updateSiteCompetitiveGapSemstormPlan(
  siteId: number,
  planId: number,
  payload: SemstormPlanUpdateInput,
) {
  return apiRequest<SemstormPlanItem>(
    `/sites/${siteId}/competitive-content-gap/semstorm/plans/${planId}`,
    {
      method: 'PUT',
      body: JSON.stringify(payload),
    },
  )
}

export async function createSiteCompetitiveGapSemstormBriefs(
  siteId: number,
  payload: SemstormCreateBriefInput,
) {
  return apiRequest<SemstormCreateBriefResponse>(
    `/sites/${siteId}/competitive-content-gap/semstorm/plans/actions/create-brief`,
    {
      method: 'POST',
      body: JSON.stringify(payload),
    },
  )
}

export async function getSiteCompetitiveGapSemstormBriefs(
  siteId: number,
  params: SemstormBriefsQueryParams = {},
) {
  const query = buildSiteCompetitiveGapSemstormBriefsSearch(params)
  const suffix = query ? `?${query}` : ''
  return apiRequest<SemstormBriefsResponse>(
    `/sites/${siteId}/competitive-content-gap/semstorm/briefs${suffix}`,
  )
}

export async function getSiteCompetitiveGapSemstormBrief(siteId: number, briefId: number) {
  return apiRequest<SemstormBriefItem>(
    `/sites/${siteId}/competitive-content-gap/semstorm/briefs/${briefId}`,
  )
}

export async function getSiteCompetitiveGapSemstormExecution(
  siteId: number,
  params: SemstormExecutionQueryParams = {},
) {
  const query = buildSiteCompetitiveGapSemstormExecutionSearch(params)
  const suffix = query ? `?${query}` : ''
  return apiRequest<SemstormExecutionResponse>(
    `/sites/${siteId}/competitive-content-gap/semstorm/execution${suffix}`,
  )
}

export async function getSiteCompetitiveGapSemstormImplemented(
  siteId: number,
  params: SemstormImplementedQueryParams = {},
) {
  const query = buildSiteCompetitiveGapSemstormImplementedSearch(params)
  const suffix = query ? `?${query}` : ''
  return apiRequest<SemstormImplementedResponse>(
    `/sites/${siteId}/competitive-content-gap/semstorm/implemented${suffix}`,
  )
}

export async function updateSiteCompetitiveGapSemstormBriefStatus(
  siteId: number,
  briefId: number,
  payload: SemstormBriefStatusUpdateInput,
) {
  return apiRequest<SemstormBriefItem>(
    `/sites/${siteId}/competitive-content-gap/semstorm/briefs/${briefId}/status`,
    {
      method: 'POST',
      body: JSON.stringify(payload),
    },
  )
}

export async function updateSiteCompetitiveGapSemstormBriefExecutionStatus(
  siteId: number,
  briefId: number,
  payload: SemstormBriefExecutionStatusUpdateInput,
) {
  return apiRequest<SemstormBriefItem>(
    `/sites/${siteId}/competitive-content-gap/semstorm/briefs/${briefId}/execution-status`,
    {
      method: 'POST',
      body: JSON.stringify(payload),
    },
  )
}

export async function updateSiteCompetitiveGapSemstormBrief(
  siteId: number,
  briefId: number,
  payload: SemstormBriefUpdateInput,
) {
  return apiRequest<SemstormBriefItem>(
    `/sites/${siteId}/competitive-content-gap/semstorm/briefs/${briefId}`,
    {
      method: 'PUT',
      body: JSON.stringify(payload),
    },
  )
}

export async function updateSiteCompetitiveGapSemstormBriefExecution(
  siteId: number,
  briefId: number,
  payload: SemstormBriefExecutionUpdateInput,
) {
  return apiRequest<SemstormBriefItem>(
    `/sites/${siteId}/competitive-content-gap/semstorm/briefs/${briefId}/execution`,
    {
      method: 'PUT',
      body: JSON.stringify(payload),
    },
  )
}

export async function updateSiteCompetitiveGapSemstormBriefImplementationStatus(
  siteId: number,
  briefId: number,
  payload: SemstormBriefImplementationStatusUpdateInput,
) {
  return apiRequest<SemstormBriefItem>(
    `/sites/${siteId}/competitive-content-gap/semstorm/briefs/${briefId}/implementation-status`,
    {
      method: 'POST',
      body: JSON.stringify(payload),
    },
  )
}

export async function enrichSiteCompetitiveGapSemstormBrief(siteId: number, briefId: number) {
  return apiRequest<SemstormBriefEnrichmentRun>(
    `/sites/${siteId}/competitive-content-gap/semstorm/briefs/${briefId}/enrich`,
    {
      method: 'POST',
    },
  )
}

export async function getSiteCompetitiveGapSemstormBriefEnrichmentRuns(siteId: number, briefId: number) {
  return apiRequest<SemstormBriefEnrichmentRunsResponse>(
    `/sites/${siteId}/competitive-content-gap/semstorm/briefs/${briefId}/enrichment-runs`,
  )
}

export async function applySiteCompetitiveGapSemstormBriefEnrichment(
  siteId: number,
  briefId: number,
  runId: number,
) {
  return apiRequest<SemstormBriefEnrichmentApplyResponse>(
    `/sites/${siteId}/competitive-content-gap/semstorm/briefs/${briefId}/enrichment-runs/${runId}/apply`,
    {
      method: 'POST',
    },
  )
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

export function useSiteCompetitiveGapSemstormDiscoveryRunsQuery(siteId: number, enabled = true) {
  return useQuery({
    queryKey: queryKeys.siteCompetitiveGapSemstormDiscoveryRuns(siteId),
    queryFn: () => getSiteCompetitiveGapSemstormDiscoveryRuns(siteId),
    enabled,
  })
}

export function useSiteCompetitiveGapSemstormDiscoveryRunQuery(
  siteId: number,
  runId: number | null,
  enabled = true,
) {
  return useQuery({
    queryKey: queryKeys.siteCompetitiveGapSemstormDiscoveryRun(siteId, runId ?? 0),
    queryFn: () => getSiteCompetitiveGapSemstormDiscoveryRun(siteId, runId ?? 0),
    enabled: enabled && runId !== null,
  })
}

export function useSiteCompetitiveGapSemstormOpportunitiesQuery(
  siteId: number,
  params: SemstormOpportunitiesQueryParams,
  enabled = true,
) {
  const search = buildSiteCompetitiveGapSemstormOpportunitiesSearch(params)

  return useQuery({
    queryKey: queryKeys.siteCompetitiveGapSemstormOpportunities(siteId, search),
    queryFn: () => getSiteCompetitiveGapSemstormOpportunities(siteId, params),
    enabled,
  })
}

export function useSiteCompetitiveGapSemstormPromotedQuery(siteId: number, enabled = true) {
  return useQuery({
    queryKey: queryKeys.siteCompetitiveGapSemstormPromoted(siteId),
    queryFn: () => getSiteCompetitiveGapSemstormPromoted(siteId),
    enabled,
  })
}

export function useSiteCompetitiveGapSemstormPlansQuery(
  siteId: number,
  params: SemstormPlansQueryParams,
  enabled = true,
) {
  const search = buildSiteCompetitiveGapSemstormPlansSearch(params)

  return useQuery({
    queryKey: queryKeys.siteCompetitiveGapSemstormPlans(siteId, search),
    queryFn: () => getSiteCompetitiveGapSemstormPlans(siteId, params),
    enabled,
  })
}

export function useSiteCompetitiveGapSemstormPlanQuery(
  siteId: number,
  planId: number | null,
  enabled = true,
) {
  return useQuery({
    queryKey: queryKeys.siteCompetitiveGapSemstormPlan(siteId, planId ?? 0),
    queryFn: () => getSiteCompetitiveGapSemstormPlan(siteId, planId ?? 0),
    enabled: enabled && planId !== null,
  })
}

export function useSiteCompetitiveGapSemstormBriefsQuery(
  siteId: number,
  params: SemstormBriefsQueryParams,
  enabled = true,
) {
  const search = buildSiteCompetitiveGapSemstormBriefsSearch(params)

  return useQuery({
    queryKey: queryKeys.siteCompetitiveGapSemstormBriefs(siteId, search),
    queryFn: () => getSiteCompetitiveGapSemstormBriefs(siteId, params),
    enabled,
  })
}

export function useSiteCompetitiveGapSemstormBriefQuery(
  siteId: number,
  briefId: number | null,
  enabled = true,
) {
  return useQuery({
    queryKey: queryKeys.siteCompetitiveGapSemstormBrief(siteId, briefId ?? 0),
    queryFn: () => getSiteCompetitiveGapSemstormBrief(siteId, briefId ?? 0),
    enabled: enabled && briefId !== null,
  })
}

export function useSiteCompetitiveGapSemstormExecutionQuery(
  siteId: number,
  params: SemstormExecutionQueryParams,
  enabled = true,
) {
  const search = buildSiteCompetitiveGapSemstormExecutionSearch(params)
  return useQuery({
    queryKey: queryKeys.siteCompetitiveGapSemstormExecution(siteId, search),
    queryFn: () => getSiteCompetitiveGapSemstormExecution(siteId, params),
    enabled,
  })
}

export function useSiteCompetitiveGapSemstormImplementedQuery(
  siteId: number,
  params: SemstormImplementedQueryParams,
  enabled = true,
) {
  const search = buildSiteCompetitiveGapSemstormImplementedSearch(params)
  return useQuery({
    queryKey: queryKeys.siteCompetitiveGapSemstormImplemented(siteId, search),
    queryFn: () => getSiteCompetitiveGapSemstormImplemented(siteId, params),
    enabled,
  })
}

export function useSiteCompetitiveGapSemstormBriefEnrichmentRunsQuery(
  siteId: number,
  briefId: number | null,
  enabled = true,
) {
  return useQuery({
    queryKey: queryKeys.siteCompetitiveGapSemstormBriefEnrichmentRuns(siteId, briefId ?? 0),
    queryFn: () => getSiteCompetitiveGapSemstormBriefEnrichmentRuns(siteId, briefId ?? 0),
    enabled: enabled && briefId !== null,
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

export function useCreateSiteCompetitiveGapSemstormDiscoveryRunMutation(siteId: number) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (payload: SemstormDiscoveryRunCreateInput) =>
      createSiteCompetitiveGapSemstormDiscoveryRun(siteId, payload),
    onSuccess: async (data) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.siteCompetitiveGapSemstormDiscoveryRuns(siteId) }),
        queryClient.invalidateQueries({ queryKey: ['sites', siteId, 'competitive-gap', 'semstorm', 'opportunities'] }),
        queryClient.invalidateQueries({
          queryKey: queryKeys.siteCompetitiveGapSemstormDiscoveryRun(siteId, data.run_id),
        }),
        queryClient.invalidateQueries({
          queryKey: queryKeys.siteCompetitiveGapSemstormPromoted(siteId),
        }),
      ])
    },
  })
}

function useSemstormOpportunityActionMutation(
  siteId: number,
  mutationFn: (payload: SemstormOpportunityActionInput) => Promise<SemstormOpportunityActionResponse>,
) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn,
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['sites', siteId, 'competitive-gap', 'semstorm', 'opportunities'] }),
        queryClient.invalidateQueries({ queryKey: queryKeys.siteCompetitiveGapSemstormPromoted(siteId) }),
      ])
    },
  })
}

export function useAcceptSiteCompetitiveGapSemstormOpportunitiesMutation(siteId: number) {
  return useSemstormOpportunityActionMutation(siteId, (payload) =>
    acceptSiteCompetitiveGapSemstormOpportunities(siteId, payload),
  )
}

export function useDismissSiteCompetitiveGapSemstormOpportunitiesMutation(siteId: number) {
  return useSemstormOpportunityActionMutation(siteId, (payload) =>
    dismissSiteCompetitiveGapSemstormOpportunities(siteId, payload),
  )
}

export function usePromoteSiteCompetitiveGapSemstormOpportunitiesMutation(siteId: number) {
  return useSemstormOpportunityActionMutation(siteId, (payload) =>
    promoteSiteCompetitiveGapSemstormOpportunities(siteId, payload),
  )
}

export function useCreateSiteCompetitiveGapSemstormPlansMutation(siteId: number) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (payload: SemstormCreatePlanInput) => createSiteCompetitiveGapSemstormPlans(siteId, payload),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.siteCompetitiveGapSemstormPromoted(siteId) }),
        queryClient.invalidateQueries({ queryKey: ['sites', siteId, 'competitive-gap', 'semstorm', 'plans'] }),
        queryClient.invalidateQueries({ queryKey: ['sites', siteId, 'competitive-gap', 'semstorm', 'briefs'] }),
      ])
    },
  })
}

export function useUpdateSiteCompetitiveGapSemstormPlanStatusMutation(siteId: number) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ planId, payload }: { planId: number; payload: SemstormPlanStatusUpdateInput }) =>
      updateSiteCompetitiveGapSemstormPlanStatus(siteId, planId, payload),
    onSuccess: async (data) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['sites', siteId, 'competitive-gap', 'semstorm', 'plans'] }),
        queryClient.invalidateQueries({ queryKey: queryKeys.siteCompetitiveGapSemstormPlan(siteId, data.id) }),
        queryClient.invalidateQueries({ queryKey: queryKeys.siteCompetitiveGapSemstormPromoted(siteId) }),
        queryClient.invalidateQueries({ queryKey: ['sites', siteId, 'competitive-gap', 'semstorm', 'briefs'] }),
      ])
    },
  })
}

export function useUpdateSiteCompetitiveGapSemstormPlanMutation(siteId: number) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ planId, payload }: { planId: number; payload: SemstormPlanUpdateInput }) =>
      updateSiteCompetitiveGapSemstormPlan(siteId, planId, payload),
    onSuccess: async (data) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['sites', siteId, 'competitive-gap', 'semstorm', 'plans'] }),
        queryClient.invalidateQueries({ queryKey: queryKeys.siteCompetitiveGapSemstormPlan(siteId, data.id) }),
        queryClient.invalidateQueries({ queryKey: queryKeys.siteCompetitiveGapSemstormPromoted(siteId) }),
        queryClient.invalidateQueries({ queryKey: ['sites', siteId, 'competitive-gap', 'semstorm', 'briefs'] }),
      ])
    },
  })
}

export function useCreateSiteCompetitiveGapSemstormBriefsMutation(siteId: number) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (payload: SemstormCreateBriefInput) => createSiteCompetitiveGapSemstormBriefs(siteId, payload),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['sites', siteId, 'competitive-gap', 'semstorm', 'plans'] }),
        queryClient.invalidateQueries({ queryKey: ['sites', siteId, 'competitive-gap', 'semstorm', 'briefs'] }),
      ])
    },
  })
}

export function useUpdateSiteCompetitiveGapSemstormBriefStatusMutation(siteId: number) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ briefId, payload }: { briefId: number; payload: SemstormBriefStatusUpdateInput }) =>
      updateSiteCompetitiveGapSemstormBriefStatus(siteId, briefId, payload),
    onSuccess: async (data) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['sites', siteId, 'competitive-gap', 'semstorm', 'briefs'] }),
        queryClient.invalidateQueries({ queryKey: ['sites', siteId, 'competitive-gap', 'semstorm', 'execution'] }),
        queryClient.invalidateQueries({ queryKey: ['sites', siteId, 'competitive-gap', 'semstorm', 'implemented'] }),
        queryClient.invalidateQueries({ queryKey: queryKeys.siteCompetitiveGapSemstormBrief(siteId, data.id) }),
        queryClient.invalidateQueries({ queryKey: ['sites', siteId, 'competitive-gap', 'semstorm', 'plans'] }),
      ])
    },
  })
}

export function useUpdateSiteCompetitiveGapSemstormBriefExecutionStatusMutation(siteId: number) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ briefId, payload }: { briefId: number; payload: SemstormBriefExecutionStatusUpdateInput }) =>
      updateSiteCompetitiveGapSemstormBriefExecutionStatus(siteId, briefId, payload),
    onSuccess: async (data) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['sites', siteId, 'competitive-gap', 'semstorm', 'briefs'] }),
        queryClient.invalidateQueries({ queryKey: ['sites', siteId, 'competitive-gap', 'semstorm', 'execution'] }),
        queryClient.invalidateQueries({ queryKey: ['sites', siteId, 'competitive-gap', 'semstorm', 'implemented'] }),
        queryClient.invalidateQueries({ queryKey: queryKeys.siteCompetitiveGapSemstormBrief(siteId, data.id) }),
        queryClient.invalidateQueries({ queryKey: ['sites', siteId, 'competitive-gap', 'semstorm', 'plans'] }),
      ])
    },
  })
}

export function useUpdateSiteCompetitiveGapSemstormBriefMutation(siteId: number) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ briefId, payload }: { briefId: number; payload: SemstormBriefUpdateInput }) =>
      updateSiteCompetitiveGapSemstormBrief(siteId, briefId, payload),
    onSuccess: async (data) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['sites', siteId, 'competitive-gap', 'semstorm', 'briefs'] }),
        queryClient.invalidateQueries({ queryKey: ['sites', siteId, 'competitive-gap', 'semstorm', 'execution'] }),
        queryClient.invalidateQueries({ queryKey: ['sites', siteId, 'competitive-gap', 'semstorm', 'implemented'] }),
        queryClient.invalidateQueries({ queryKey: queryKeys.siteCompetitiveGapSemstormBrief(siteId, data.id) }),
        queryClient.invalidateQueries({ queryKey: ['sites', siteId, 'competitive-gap', 'semstorm', 'plans'] }),
      ])
    },
  })
}

export function useUpdateSiteCompetitiveGapSemstormBriefExecutionMutation(siteId: number) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ briefId, payload }: { briefId: number; payload: SemstormBriefExecutionUpdateInput }) =>
      updateSiteCompetitiveGapSemstormBriefExecution(siteId, briefId, payload),
    onSuccess: async (data) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['sites', siteId, 'competitive-gap', 'semstorm', 'briefs'] }),
        queryClient.invalidateQueries({ queryKey: ['sites', siteId, 'competitive-gap', 'semstorm', 'execution'] }),
        queryClient.invalidateQueries({ queryKey: ['sites', siteId, 'competitive-gap', 'semstorm', 'implemented'] }),
        queryClient.invalidateQueries({ queryKey: queryKeys.siteCompetitiveGapSemstormBrief(siteId, data.id) }),
      ])
    },
  })
}

export function useUpdateSiteCompetitiveGapSemstormBriefImplementationStatusMutation(siteId: number) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ briefId, payload }: { briefId: number; payload: SemstormBriefImplementationStatusUpdateInput }) =>
      updateSiteCompetitiveGapSemstormBriefImplementationStatus(siteId, briefId, payload),
    onSuccess: async (data) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['sites', siteId, 'competitive-gap', 'semstorm', 'briefs'] }),
        queryClient.invalidateQueries({ queryKey: ['sites', siteId, 'competitive-gap', 'semstorm', 'execution'] }),
        queryClient.invalidateQueries({ queryKey: ['sites', siteId, 'competitive-gap', 'semstorm', 'implemented'] }),
        queryClient.invalidateQueries({ queryKey: queryKeys.siteCompetitiveGapSemstormBrief(siteId, data.id) }),
      ])
    },
  })
}

export function useCreateSiteCompetitiveGapSemstormBriefEnrichmentMutation(siteId: number) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (briefId: number) => enrichSiteCompetitiveGapSemstormBrief(siteId, briefId),
    onSuccess: async (data) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['sites', siteId, 'competitive-gap', 'semstorm', 'briefs'] }),
        queryClient.invalidateQueries({ queryKey: ['sites', siteId, 'competitive-gap', 'semstorm', 'execution'] }),
        queryClient.invalidateQueries({ queryKey: ['sites', siteId, 'competitive-gap', 'semstorm', 'implemented'] }),
        queryClient.invalidateQueries({ queryKey: queryKeys.siteCompetitiveGapSemstormBrief(siteId, data.brief_item_id) }),
        queryClient.invalidateQueries({
          queryKey: queryKeys.siteCompetitiveGapSemstormBriefEnrichmentRuns(siteId, data.brief_item_id),
        }),
      ])
    },
  })
}

export function useApplySiteCompetitiveGapSemstormBriefEnrichmentMutation(siteId: number) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ briefId, runId }: { briefId: number; runId: number }) =>
      applySiteCompetitiveGapSemstormBriefEnrichment(siteId, briefId, runId),
    onSuccess: async (data) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['sites', siteId, 'competitive-gap', 'semstorm', 'briefs'] }),
        queryClient.invalidateQueries({ queryKey: ['sites', siteId, 'competitive-gap', 'semstorm', 'execution'] }),
        queryClient.invalidateQueries({ queryKey: ['sites', siteId, 'competitive-gap', 'semstorm', 'implemented'] }),
        queryClient.invalidateQueries({ queryKey: queryKeys.siteCompetitiveGapSemstormBrief(siteId, data.brief.id) }),
        queryClient.invalidateQueries({
          queryKey: queryKeys.siteCompetitiveGapSemstormBriefEnrichmentRuns(siteId, data.brief.id),
        }),
        queryClient.invalidateQueries({ queryKey: ['sites', siteId, 'competitive-gap', 'semstorm', 'plans'] }),
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
