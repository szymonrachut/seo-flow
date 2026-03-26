import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { queryKeys } from '../../api/queryKeys'
import { apiRequest } from '../../api/client'
import type {
  GenerateSiteContentGeneratorAssetsInput,
  GenerateSiteContentGeneratorAssetsResponse,
  SiteContentGeneratorAsset,
  SiteCrawlCreateInput,
  SiteCrawlListItem,
  SiteDetail,
  SiteListItem,
} from '../../types/api'
import { buildQueryString } from '../../utils/searchParams'

export interface SiteDetailQueryParams {
  active_crawl_id?: number
  baseline_crawl_id?: number
}

export interface SiteContentGeneratorAssetQueryParams {
  active_crawl_id?: number
}

interface SiteDetailQueryOptions {
  enabled?: boolean
}

function buildSiteDetailSearch(params: SiteDetailQueryParams) {
  return buildQueryString(params)
}

function buildSiteContentGeneratorAssetSearch(params: SiteContentGeneratorAssetQueryParams) {
  return buildQueryString(params)
}

export async function listSites() {
  return apiRequest<SiteListItem[]>('/sites')
}

export async function getSiteDetail(siteId: number, params: SiteDetailQueryParams) {
  const query = buildSiteDetailSearch(params)
  const suffix = query ? `?${query}` : ''
  return apiRequest<SiteDetail>(`/sites/${siteId}${suffix}`)
}

export async function listSiteCrawls(siteId: number) {
  return apiRequest<SiteCrawlListItem[]>(`/sites/${siteId}/crawls`)
}

export async function createSiteCrawl(siteId: number, payload: SiteCrawlCreateInput) {
  return apiRequest<{ id: number; site_id: number }>(`/sites/${siteId}/crawls`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function getSiteContentGeneratorAsset(siteId: number, params: SiteContentGeneratorAssetQueryParams) {
  const query = buildSiteContentGeneratorAssetSearch(params)
  const suffix = query ? `?${query}` : ''
  return apiRequest<SiteContentGeneratorAsset>(`/sites/${siteId}/content-generator-assets${suffix}`)
}

export async function generateSiteContentGeneratorAsset(
  siteId: number,
  payload: GenerateSiteContentGeneratorAssetsInput,
) {
  return apiRequest<GenerateSiteContentGeneratorAssetsResponse>(`/sites/${siteId}/content-generator-assets/generate`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function useSitesQuery() {
  return useQuery({
    queryKey: queryKeys.sitesList,
    queryFn: listSites,
  })
}

export function useSiteDetailQuery(
  siteId: number,
  params: SiteDetailQueryParams,
  options: SiteDetailQueryOptions = {},
) {
  const search = buildSiteDetailSearch(params)

  return useQuery({
    queryKey: queryKeys.siteDetail(siteId, search),
    queryFn: () => getSiteDetail(siteId, params),
    enabled: options.enabled,
  })
}

export function useSiteCrawlsQuery(siteId: number) {
  return useQuery({
    queryKey: queryKeys.siteCrawls(siteId),
    queryFn: () => listSiteCrawls(siteId),
  })
}

export function useSiteContentGeneratorAssetQuery(
  siteId: number,
  params: SiteContentGeneratorAssetQueryParams,
  enabled = true,
) {
  const search = buildSiteContentGeneratorAssetSearch(params)

  return useQuery({
    queryKey: queryKeys.siteContentGeneratorAsset(siteId, search),
    queryFn: () => getSiteContentGeneratorAsset(siteId, params),
    enabled,
  })
}

export function useCreateSiteCrawlMutation(siteId: number) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (payload: SiteCrawlCreateInput) => createSiteCrawl(siteId, payload),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.sitesRoot }),
        queryClient.invalidateQueries({ queryKey: queryKeys.siteCrawls(siteId) }),
        queryClient.invalidateQueries({ queryKey: ['sites', siteId] }),
        queryClient.invalidateQueries({ queryKey: queryKeys.jobsRoot }),
      ])
    },
  })
}

export function useGenerateSiteContentGeneratorAssetMutation(siteId: number) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (payload: GenerateSiteContentGeneratorAssetsInput) =>
      generateSiteContentGeneratorAsset(siteId, payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ['sites', siteId, 'content-generator-assets'],
        refetchType: 'none',
      })
    },
  })
}
