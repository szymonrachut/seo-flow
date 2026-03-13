import { keepPreviousData, useQuery } from '@tanstack/react-query'

import { apiRequest } from '../../api/client'
import { queryKeys } from '../../api/queryKeys'
import type { LinkRecord, LinksQueryParams, PaginatedResponse } from '../../types/api'
import { buildQueryString } from '../../utils/searchParams'

export async function getLinks(
  jobId: number,
  params: LinksQueryParams,
): Promise<PaginatedResponse<LinkRecord>> {
  const query = buildQueryString(params)
  return apiRequest<PaginatedResponse<LinkRecord>>(`/crawl-jobs/${jobId}/links?${query}`)
}

export function useLinksQuery(jobId: number, params: LinksQueryParams) {
  const search = buildQueryString(params)

  return useQuery({
    queryKey: queryKeys.jobLinks(jobId, search),
    queryFn: () => getLinks(jobId, params),
    placeholderData: keepPreviousData,
  })
}
