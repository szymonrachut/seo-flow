import { keepPreviousData, useQuery } from '@tanstack/react-query'

import { apiRequest } from '../../api/client'
import { queryKeys } from '../../api/queryKeys'
import type {
  GscDateRangeLabel,
  InternalLinkingIssuesQueryParams,
  InternalLinkingOverview,
  PaginatedInternalLinkingIssuesResponse,
  PaginatedSiteInternalLinkingCompareResponse,
  SortOrder,
} from '../../types/api'
import { buildQueryString } from '../../utils/searchParams'

export async function getInternalLinkingOverview(
  jobId: number,
  gscDateRange: GscDateRangeLabel,
): Promise<InternalLinkingOverview> {
  const query = buildQueryString({ gsc_date_range: gscDateRange })
  return apiRequest<InternalLinkingOverview>(`/crawl-jobs/${jobId}/internal-linking/overview?${query}`)
}

export async function getInternalLinkingIssues(
  jobId: number,
  params: InternalLinkingIssuesQueryParams,
): Promise<PaginatedInternalLinkingIssuesResponse> {
  const query = buildQueryString(params)
  return apiRequest<PaginatedInternalLinkingIssuesResponse>(`/crawl-jobs/${jobId}/internal-linking/issues?${query}`)
}

export function useInternalLinkingOverviewQuery(jobId: number, gscDateRange: GscDateRangeLabel, enabled = true) {
  const search = buildQueryString({ gsc_date_range: gscDateRange })

  return useQuery({
    queryKey: queryKeys.jobInternalLinkingOverview(jobId, search),
    queryFn: () => getInternalLinkingOverview(jobId, gscDateRange),
    enabled,
  })
}

export function useInternalLinkingIssuesQuery(jobId: number, params: InternalLinkingIssuesQueryParams, enabled = true) {
  const search = buildQueryString(params)

  return useQuery({
    queryKey: queryKeys.jobInternalLinkingIssues(jobId, search),
    queryFn: () => getInternalLinkingIssues(jobId, params),
    placeholderData: keepPreviousData,
    enabled,
  })
}

export interface SiteInternalLinkingCompareQueryParams {
  active_crawl_id?: number
  baseline_crawl_id?: number
  gsc_date_range: GscDateRangeLabel
  page: number
  page_size: number
  sort_by:
    | 'url'
    | 'change_type'
    | 'delta_internal_linking_score'
    | 'delta_link_equity_score'
    | 'delta_incoming_follow_linking_pages'
      | 'delta_anchor_diversity_score'
      | 'delta_boilerplate_like_share'
  sort_order: SortOrder
  change_type?: string
  compare_kind?: string
  issue_type?: string
  url_contains?: string
}

export async function getSiteInternalLinkingCompare(
  siteId: number,
  params: SiteInternalLinkingCompareQueryParams,
): Promise<PaginatedSiteInternalLinkingCompareResponse> {
  const query = buildQueryString(params)
  return apiRequest<PaginatedSiteInternalLinkingCompareResponse>(`/sites/${siteId}/internal-linking?${query}`)
}

export function useSiteInternalLinkingCompareQuery(siteId: number, params: SiteInternalLinkingCompareQueryParams, enabled = true) {
  const search = buildQueryString(params)

  return useQuery({
    queryKey: queryKeys.siteInternalLinkingCompare(siteId, search),
    queryFn: () => getSiteInternalLinkingCompare(siteId, params),
    enabled,
    placeholderData: keepPreviousData,
  })
}
