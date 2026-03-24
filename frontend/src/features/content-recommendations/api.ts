import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { queryKeys } from '../../api/queryKeys'
import { apiRequest } from '../../api/client'
import type {
  ContentRecommendationMarkDoneInput,
  ContentRecommendationMarkDoneResponse,
  PaginatedSiteContentRecommendationsResponse,
  SiteContentRecommendationsQueryParams,
} from '../../types/api'
import { buildQueryString } from '../../utils/searchParams'

export type { SiteContentRecommendationsQueryParams } from '../../types/api'

function buildSiteContentRecommendationsSearch(params: SiteContentRecommendationsQueryParams) {
  return buildQueryString(params)
}

export async function getSiteContentRecommendations(
  siteId: number,
  params: SiteContentRecommendationsQueryParams,
) {
  const query = buildSiteContentRecommendationsSearch(params)
  const suffix = query ? `?${query}` : ''
  return apiRequest<PaginatedSiteContentRecommendationsResponse>(
    `/sites/${siteId}/content-recommendations${suffix}`,
  )
}

export async function markSiteContentRecommendationDone(
  siteId: number,
  input: ContentRecommendationMarkDoneInput,
) {
  return apiRequest<ContentRecommendationMarkDoneResponse>(`/sites/${siteId}/content-recommendations/mark-done`, {
    method: 'POST',
    body: JSON.stringify(input),
  })
}

export function useSiteContentRecommendationsQuery(
  siteId: number,
  params: SiteContentRecommendationsQueryParams,
  enabled = true,
) {
  const search = buildSiteContentRecommendationsSearch(params)

  return useQuery({
    queryKey: queryKeys.siteContentRecommendations(siteId, search),
    queryFn: () => getSiteContentRecommendations(siteId, params),
    enabled,
  })
}

export function useMarkSiteContentRecommendationDoneMutation(siteId: number) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (input: ContentRecommendationMarkDoneInput) => markSiteContentRecommendationDone(siteId, input),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ['sites', siteId, 'content-recommendations'],
      })
    },
  })
}
