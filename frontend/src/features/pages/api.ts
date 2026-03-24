import { keepPreviousData, useQuery } from '@tanstack/react-query'

import { apiRequest } from '../../api/client'
import { queryKeys } from '../../api/queryKeys'
import type {
  GscDateRangeLabel,
  PageTaxonomySummary,
  PaginatedPagesResponse,
  PaginatedSitePagesCompareResponse,
  PagesQueryParams,
  SortOrder,
} from '../../types/api'
import { buildQueryString } from '../../utils/searchParams'

export async function getPages(
  jobId: number,
  params: PagesQueryParams,
): Promise<PaginatedPagesResponse> {
  const query = buildQueryString(params)
  return apiRequest<PaginatedPagesResponse>(`/crawl-jobs/${jobId}/pages?${query}`)
}

interface UsePagesQueryOptions {
  enabled?: boolean
}

export function usePagesQuery(jobId: number, params: PagesQueryParams, options: UsePagesQueryOptions = {}) {
  const search = buildQueryString(params)

  return useQuery({
    queryKey: queryKeys.jobPages(jobId, search),
    queryFn: () => getPages(jobId, params),
    placeholderData: keepPreviousData,
    enabled: options.enabled,
  })
}

export async function getPageTaxonomySummary(jobId: number): Promise<PageTaxonomySummary> {
  return apiRequest<PageTaxonomySummary>(`/crawl-jobs/${jobId}/page-taxonomy/summary`)
}

interface UsePageTaxonomySummaryQueryOptions {
  enabled?: boolean
}

export function usePageTaxonomySummaryQuery(jobId: number, options: UsePageTaxonomySummaryQueryOptions = {}) {
  return useQuery({
    queryKey: queryKeys.jobPageTaxonomySummary(jobId),
    queryFn: () => getPageTaxonomySummary(jobId),
    enabled: options.enabled,
  })
}

export interface SitePagesCompareQueryParams {
  active_crawl_id?: number
  baseline_crawl_id?: number
  gsc_date_range: GscDateRangeLabel
  page: number
  page_size: number
  sort_by:
    | 'url'
    | 'change_type'
    | 'active_status_code'
    | 'delta_priority_score'
    | 'active_priority_score'
    | 'delta_word_count'
    | 'delta_response_time_ms'
    | 'delta_incoming_internal_links'
    | 'delta_incoming_internal_linking_pages'
    | 'priority_trend'
    | 'word_count_trend'
    | 'response_time_trend'
    | 'internal_linking_trend'
  sort_order: SortOrder
  change_type?: string
  changed?: boolean
  status_changed?: boolean
  title_changed?: boolean
  meta_description_changed?: boolean
  h1_changed?: boolean
  canonical_changed?: boolean
  noindex_changed?: boolean
  priority_trend?: string
  internal_linking_trend?: string
  content_trend?: string
  response_time_trend?: string
  url_contains?: string
}

export async function getSitePagesCompare(
  siteId: number,
  params: SitePagesCompareQueryParams,
): Promise<PaginatedSitePagesCompareResponse> {
  const query = buildQueryString(params)
  return apiRequest<PaginatedSitePagesCompareResponse>(`/sites/${siteId}/pages?${query}`)
}

export function useSitePagesCompareQuery(siteId: number, params: SitePagesCompareQueryParams, enabled = true) {
  const search = buildQueryString(params)

  return useQuery({
    queryKey: queryKeys.sitePagesCompare(siteId, search),
    queryFn: () => getSitePagesCompare(siteId, params),
    placeholderData: keepPreviousData,
    enabled,
  })
}
