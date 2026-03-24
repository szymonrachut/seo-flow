import { useQuery } from '@tanstack/react-query'

import { apiRequest } from '../../api/client'
import { queryKeys } from '../../api/queryKeys'
import type {
  GscDateRangeLabel,
  OpportunitiesSummary,
  OpportunityType,
  PaginatedSiteOpportunitiesCompareResponse,
  PriorityLevel,
  SortOrder,
} from '../../types/api'
import { buildQueryString } from '../../utils/searchParams'

export interface OpportunitiesQueryParams {
  gsc_date_range: GscDateRangeLabel
  priority_level?: PriorityLevel
  opportunity_type?: OpportunityType
  priority_score_min?: number
  priority_score_max?: number
  sort_by: 'count' | 'top_priority_score' | 'top_opportunity_score' | 'type'
  sort_order: SortOrder
  top_pages_limit: number
}

export async function getOpportunities(
  jobId: number,
  params: OpportunitiesQueryParams,
): Promise<OpportunitiesSummary> {
  const query = buildQueryString(params)
  return apiRequest<OpportunitiesSummary>(`/crawl-jobs/${jobId}/opportunities?${query}`)
}

export function useOpportunitiesQuery(jobId: number, params: OpportunitiesQueryParams, enabled = true) {
  const search = buildQueryString(params)

  return useQuery({
    queryKey: queryKeys.jobOpportunities(jobId, search),
    queryFn: () => getOpportunities(jobId, params),
    enabled,
  })
}

export interface SiteOpportunitiesCompareQueryParams {
  active_crawl_id?: number
  baseline_crawl_id?: number
  gsc_date_range: GscDateRangeLabel
  page: number
  page_size: number
  sort_by: 'url' | 'change_type' | 'active_priority_score' | 'delta_priority_score' | 'active_opportunity_count'
  sort_order: SortOrder
  change_kind?: string
  opportunity_type?: string
  url_contains?: string
}

export async function getSiteOpportunitiesCompare(
  siteId: number,
  params: SiteOpportunitiesCompareQueryParams,
): Promise<PaginatedSiteOpportunitiesCompareResponse> {
  const query = buildQueryString(params)
  return apiRequest<PaginatedSiteOpportunitiesCompareResponse>(`/sites/${siteId}/opportunities?${query}`)
}

export function useSiteOpportunitiesCompareQuery(siteId: number, params: SiteOpportunitiesCompareQueryParams, enabled = true) {
  const search = buildQueryString(params)

  return useQuery({
    queryKey: queryKeys.siteOpportunitiesCompare(siteId, search),
    queryFn: () => getSiteOpportunitiesCompare(siteId, params),
    enabled,
  })
}
