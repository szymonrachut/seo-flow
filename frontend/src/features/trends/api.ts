import { keepPreviousData, useQuery } from '@tanstack/react-query'

import { apiRequest } from '../../api/client'
import { queryKeys } from '../../api/queryKeys'
import type {
  CrawlCompareChangeType,
  GscDateRangeLabel,
  MetricTrend,
  PaginatedCrawlCompareResponse,
  PaginatedGscCompareResponse,
  SortOrder,
  TrendsOverview,
} from '../../types/api'
import { buildQueryString } from '../../utils/searchParams'

export interface CrawlCompareQueryParams {
  baseline_job_id: number
  gsc_date_range: GscDateRangeLabel
  page: number
  page_size: number
  sort_by:
    | 'url'
    | 'change_type'
    | 'issues_resolved_count'
    | 'issues_added_count'
    | 'delta_priority_score'
    | 'delta_word_count'
    | 'delta_schema_count'
    | 'delta_response_time_ms'
    | 'delta_incoming_internal_links'
    | 'delta_incoming_internal_linking_pages'
  sort_order: SortOrder
  change_type?: CrawlCompareChangeType
  resolved_issues_min?: number
  added_issues_min?: number
  url_contains?: string
}

export interface GscCompareQueryParams {
  baseline_gsc_range: GscDateRangeLabel
  target_gsc_range: GscDateRangeLabel
  page: number
  page_size: number
  sort_by: 'url' | 'overall_trend' | 'delta_clicks' | 'delta_impressions' | 'delta_ctr' | 'delta_position' | 'delta_top_queries_count'
  sort_order: SortOrder
  trend?: MetricTrend
  clicks_trend?: MetricTrend
  impressions_trend?: MetricTrend
  ctr_trend?: MetricTrend
  position_trend?: MetricTrend
  top_queries_trend?: MetricTrend
  url_contains?: string
}

export async function getTrendsOverview(jobId: number): Promise<TrendsOverview> {
  return apiRequest<TrendsOverview>(`/crawl-jobs/${jobId}/trends/overview`)
}

export async function getCrawlCompare(
  jobId: number,
  params: CrawlCompareQueryParams,
): Promise<PaginatedCrawlCompareResponse> {
  const query = buildQueryString(params)
  return apiRequest<PaginatedCrawlCompareResponse>(`/crawl-jobs/${jobId}/trends/crawl?${query}`)
}

export async function getGscCompare(
  jobId: number,
  params: GscCompareQueryParams,
): Promise<PaginatedGscCompareResponse> {
  const query = buildQueryString(params)
  return apiRequest<PaginatedGscCompareResponse>(`/crawl-jobs/${jobId}/trends/gsc?${query}`)
}

export function useTrendsOverviewQuery(jobId: number) {
  return useQuery({
    queryKey: queryKeys.jobTrendsOverview(jobId),
    queryFn: () => getTrendsOverview(jobId),
  })
}

export function useCrawlCompareQuery(jobId: number, params: CrawlCompareQueryParams | null, enabled: boolean) {
  const search = params ? buildQueryString(params) : ''

  return useQuery({
    queryKey: queryKeys.jobCrawlCompare(jobId, search),
    queryFn: () => getCrawlCompare(jobId, params as CrawlCompareQueryParams),
    enabled,
    placeholderData: keepPreviousData,
  })
}

export function useGscCompareQuery(jobId: number, params: GscCompareQueryParams | null, enabled: boolean) {
  const search = params ? buildQueryString(params) : ''

  return useQuery({
    queryKey: queryKeys.jobGscCompare(jobId, search),
    queryFn: () => getGscCompare(jobId, params as GscCompareQueryParams),
    enabled,
    placeholderData: keepPreviousData,
  })
}
