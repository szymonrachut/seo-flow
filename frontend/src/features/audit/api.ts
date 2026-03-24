import { useQuery } from '@tanstack/react-query'

import { apiRequest } from '../../api/client'
import { queryKeys } from '../../api/queryKeys'
import type { AuditReport, SiteAuditCompare } from '../../types/api'
import { buildQueryString } from '../../utils/searchParams'

interface AuditQueryOptions {
  enabled?: boolean
}

export async function getAuditReport(jobId: number): Promise<AuditReport> {
  return apiRequest<AuditReport>(`/crawl-jobs/${jobId}/audit`)
}

export function useAuditQuery(jobId: number, options: AuditQueryOptions = {}) {
  return useQuery({
    queryKey: queryKeys.jobAudit(jobId),
    queryFn: () => getAuditReport(jobId),
    enabled: options.enabled,
  })
}

export interface SiteAuditCompareQueryParams {
  active_crawl_id?: number
  baseline_crawl_id?: number
  status?: string
}

export async function getSiteAuditCompare(siteId: number, params: SiteAuditCompareQueryParams): Promise<SiteAuditCompare> {
  const query = buildQueryString(params)
  const suffix = query ? `?${query}` : ''
  return apiRequest<SiteAuditCompare>(`/sites/${siteId}/audit${suffix}`)
}

export function useSiteAuditCompareQuery(siteId: number, params: SiteAuditCompareQueryParams, enabled = true) {
  const search = buildQueryString(params)

  return useQuery({
    queryKey: queryKeys.siteAuditCompare(siteId, search),
    queryFn: () => getSiteAuditCompare(siteId, params),
    enabled,
  })
}
