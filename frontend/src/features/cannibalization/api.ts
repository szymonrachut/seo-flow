import { keepPreviousData, useQuery } from '@tanstack/react-query'

import { apiRequest } from '../../api/client'
import { queryKeys } from '../../api/queryKeys'
import type {
  CannibalizationClustersQueryParams,
  CannibalizationPageDetails,
  GscDateRangeLabel,
  PaginatedCannibalizationClustersResponse,
} from '../../types/api'
import { buildQueryString } from '../../utils/searchParams'

export async function getCannibalizationClusters(
  jobId: number,
  params: CannibalizationClustersQueryParams,
): Promise<PaginatedCannibalizationClustersResponse> {
  const query = buildQueryString(params)
  return apiRequest<PaginatedCannibalizationClustersResponse>(`/crawl-jobs/${jobId}/cannibalization?${query}`)
}

export async function getCannibalizationPageDetails(
  jobId: number,
  pageId: number,
  gscDateRange: GscDateRangeLabel,
): Promise<CannibalizationPageDetails> {
  const query = buildQueryString({ gsc_date_range: gscDateRange })
  return apiRequest<CannibalizationPageDetails>(`/crawl-jobs/${jobId}/cannibalization/pages/${pageId}?${query}`)
}

export function useCannibalizationClustersQuery(jobId: number, params: CannibalizationClustersQueryParams) {
  const search = buildQueryString(params)

  return useQuery({
    queryKey: queryKeys.jobCannibalization(jobId, search),
    queryFn: () => getCannibalizationClusters(jobId, params),
    placeholderData: keepPreviousData,
  })
}

export function useCannibalizationPageDetailsQuery(
  jobId: number,
  pageId: number | null,
  gscDateRange: GscDateRangeLabel,
) {
  const search = buildQueryString({ gsc_date_range: gscDateRange })

  return useQuery({
    queryKey: queryKeys.jobCannibalizationPage(jobId, pageId ?? 0, search),
    queryFn: () => getCannibalizationPageDetails(jobId, pageId ?? 0, gscDateRange),
    enabled: pageId !== null,
  })
}
