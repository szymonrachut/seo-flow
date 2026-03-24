import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiRequest } from '../../api/client'
import { queryKeys } from '../../api/queryKeys'
import type {
  GscImportResponse,
  GscPropertyOption,
  GscSummary,
  PaginatedGscTopQueriesResponse,
  SiteGscSummary,
} from '../../types/api'
import { buildQueryString } from '../../utils/searchParams'

interface GscImportPayload {
  date_ranges: Array<'last_28_days' | 'last_90_days'>
  top_queries_limit?: number
}

interface GscTopQueriesParams {
  page_id?: number
  date_range_label: 'last_28_days' | 'last_90_days'
  page: number
  page_size: number
  sort_by: 'query' | 'clicks' | 'impressions' | 'ctr' | 'position' | 'url'
  sort_order: 'asc' | 'desc'
  query_contains?: string
  query_excludes?: string
  clicks_min?: number
  impressions_min?: number
  ctr_max?: number
  position_min?: number
}

interface SiteGscSummaryParams {
  active_crawl_id?: number
}

export async function getGscSummary(jobId: number): Promise<GscSummary> {
  return apiRequest<GscSummary>(`/crawl-jobs/${jobId}/gsc/summary`)
}

export async function getSiteGscSummary(siteId: number, params: SiteGscSummaryParams): Promise<SiteGscSummary> {
  const query = buildQueryString(params)
  const suffix = query ? `?${query}` : ''
  return apiRequest<SiteGscSummary>(`/sites/${siteId}/gsc/summary${suffix}`)
}

export async function getGscProperties(jobId: number): Promise<GscPropertyOption[]> {
  return apiRequest<GscPropertyOption[]>(`/crawl-jobs/${jobId}/gsc/properties`)
}

export async function getSiteGscProperties(siteId: number): Promise<GscPropertyOption[]> {
  return apiRequest<GscPropertyOption[]>(`/sites/${siteId}/gsc/properties`)
}

export async function selectGscProperty(jobId: number, propertyUri: string) {
  return apiRequest(`/crawl-jobs/${jobId}/gsc/property`, {
    method: 'PUT',
    body: JSON.stringify({ property_uri: propertyUri }),
  })
}

export async function selectSiteGscProperty(siteId: number, propertyUri: string) {
  return apiRequest(`/sites/${siteId}/gsc/property`, {
    method: 'PUT',
    body: JSON.stringify({ property_uri: propertyUri }),
  })
}

export async function importGscData(jobId: number, payload: GscImportPayload): Promise<GscImportResponse> {
  return apiRequest<GscImportResponse>(`/crawl-jobs/${jobId}/gsc/import`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function importSiteGscData(
  siteId: number,
  payload: GscImportPayload,
  params: SiteGscSummaryParams,
): Promise<GscImportResponse> {
  const query = buildQueryString(params)
  const suffix = query ? `?${query}` : ''
  return apiRequest<GscImportResponse>(`/sites/${siteId}/gsc/import${suffix}`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function getGscTopQueries(
  jobId: number,
  params: GscTopQueriesParams,
): Promise<PaginatedGscTopQueriesResponse> {
  const query = buildQueryString(params)
  return apiRequest<PaginatedGscTopQueriesResponse>(`/crawl-jobs/${jobId}/gsc/top-queries?${query}`)
}

export function useGscSummaryQuery(jobId: number) {
  return useQuery({
    queryKey: queryKeys.jobGscSummary(jobId),
    queryFn: () => getGscSummary(jobId),
  })
}

export function useSiteGscSummaryQuery(siteId: number, params: SiteGscSummaryParams, enabled = true) {
  const search = buildQueryString(params)

  return useQuery({
    queryKey: queryKeys.siteGscSummary(siteId, search),
    queryFn: () => getSiteGscSummary(siteId, params),
    enabled,
  })
}

export function useGscPropertiesQuery(jobId: number, enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.jobGscProperties(jobId),
    queryFn: () => getGscProperties(jobId),
    enabled,
  })
}

export function useSiteGscPropertiesQuery(siteId: number, enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.siteGscProperties(siteId),
    queryFn: () => getSiteGscProperties(siteId),
    enabled,
  })
}

export function useSelectGscPropertyMutation(jobId: number) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (propertyUri: string) => selectGscProperty(jobId, propertyUri),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.jobGscSummary(jobId) }),
        queryClient.invalidateQueries({ queryKey: queryKeys.jobGscProperties(jobId) }),
      ])
    },
  })
}

export function useSelectSiteGscPropertyMutation(siteId: number) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (propertyUri: string) => selectSiteGscProperty(siteId, propertyUri),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.sitesRoot }),
        queryClient.invalidateQueries({ queryKey: queryKeys.siteGscProperties(siteId) }),
        queryClient.invalidateQueries({ queryKey: ['sites', siteId] }),
      ])
    },
  })
}

export function useImportGscDataMutation(jobId: number) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (payload: GscImportPayload) => importGscData(jobId, payload),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.jobGscSummary(jobId) }),
        queryClient.invalidateQueries({ queryKey: ['crawl-jobs', jobId, 'pages'] }),
        queryClient.invalidateQueries({ queryKey: ['crawl-jobs', jobId, 'gsc', 'top-queries'] }),
        queryClient.invalidateQueries({ queryKey: ['crawl-jobs', jobId, 'opportunities'] }),
        queryClient.invalidateQueries({ queryKey: ['crawl-jobs', jobId, 'trends'] }),
        queryClient.invalidateQueries({ queryKey: queryKeys.jobDetail(jobId) }),
      ])
    },
  })
}

export function useImportSiteGscDataMutation(siteId: number, activeCrawlId: number | null) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (payload: GscImportPayload) =>
      importSiteGscData(siteId, payload, {
        active_crawl_id: activeCrawlId ?? undefined,
      }),
    onSuccess: async () => {
      const invalidations = [
        queryClient.invalidateQueries({ queryKey: queryKeys.sitesRoot }),
        queryClient.invalidateQueries({ queryKey: ['sites', siteId] }),
      ]

      if (activeCrawlId) {
        invalidations.push(
          queryClient.invalidateQueries({ queryKey: ['crawl-jobs', activeCrawlId, 'pages'] }),
          queryClient.invalidateQueries({ queryKey: ['crawl-jobs', activeCrawlId, 'gsc', 'top-queries'] }),
          queryClient.invalidateQueries({ queryKey: ['crawl-jobs', activeCrawlId, 'opportunities'] }),
          queryClient.invalidateQueries({ queryKey: ['crawl-jobs', activeCrawlId, 'trends'] }),
          queryClient.invalidateQueries({ queryKey: queryKeys.jobDetail(activeCrawlId) }),
        )
      }

      await Promise.all(invalidations)
    },
  })
}

export function useGscTopQueriesQuery(jobId: number, params: GscTopQueriesParams, enabled: boolean) {
  const search = buildQueryString(params)

  return useQuery({
    queryKey: queryKeys.jobGscTopQueries(jobId, search),
    queryFn: () => getGscTopQueries(jobId, params),
    enabled,
  })
}
