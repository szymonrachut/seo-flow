import { keepPreviousData, useQuery } from '@tanstack/react-query'

import { apiRequest } from '../../api/client'
import { queryKeys } from '../../api/queryKeys'
import type { PageRecord, PaginatedResponse, PagesQueryParams } from '../../types/api'
import { buildQueryString } from '../../utils/searchParams'

export async function getPages(
  jobId: number,
  params: PagesQueryParams,
): Promise<PaginatedResponse<PageRecord>> {
  const query = buildQueryString(params)
  return apiRequest<PaginatedResponse<PageRecord>>(`/crawl-jobs/${jobId}/pages?${query}`)
}

export function usePagesQuery(jobId: number, params: PagesQueryParams) {
  const search = buildQueryString(params)

  return useQuery({
    queryKey: queryKeys.jobPages(jobId, search),
    queryFn: () => getPages(jobId, params),
    placeholderData: keepPreviousData,
  })
}
