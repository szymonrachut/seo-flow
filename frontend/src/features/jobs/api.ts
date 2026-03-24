import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiRequest } from '../../api/client'
import { queryKeys } from '../../api/queryKeys'
import type {
  CrawlJobCreateInput,
  CrawlJobDetail,
  CrawlJobListItem,
  JobStatus,
  JobsListQueryParams,
} from '../../types/api'
import { buildQueryString } from '../../utils/searchParams'

function isActiveStatus(status: JobStatus) {
  return status === 'pending' || status === 'running'
}

export async function listCrawlJobs(params: JobsListQueryParams): Promise<CrawlJobListItem[]> {
  const query = buildQueryString(params)
  const suffix = query ? `?${query}` : ''
  return apiRequest<CrawlJobListItem[]>(`/crawl-jobs${suffix}`)
}

export async function createCrawlJob(payload: CrawlJobCreateInput): Promise<{ id: number; site_id: number }> {
  return apiRequest<{ id: number; site_id: number }>('/crawl-jobs', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function getCrawlJob(jobId: number): Promise<CrawlJobDetail> {
  return apiRequest<CrawlJobDetail>(`/crawl-jobs/${jobId}`)
}

export async function stopCrawlJob(jobId: number): Promise<CrawlJobDetail> {
  return apiRequest<CrawlJobDetail>(`/crawl-jobs/${jobId}/stop`, {
    method: 'POST',
  })
}

export function useCrawlJobsQuery(params: JobsListQueryParams) {
  const search = buildQueryString(params)

  return useQuery({
    queryKey: queryKeys.jobsList(search),
    queryFn: () => listCrawlJobs(params),
    refetchInterval: (query) =>
      query.state.data?.some((job) => isActiveStatus(job.status)) ? 5000 : false,
  })
}

export function useCrawlJobDetailQuery(jobId: number) {
  return useQuery({
    queryKey: queryKeys.jobDetail(jobId),
    queryFn: () => getCrawlJob(jobId),
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return status && isActiveStatus(status) ? 4000 : false
    },
  })
}

export function useCreateCrawlJobMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: createCrawlJob,
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.jobsRoot }),
        queryClient.invalidateQueries({ queryKey: queryKeys.sitesRoot }),
      ])
    },
  })
}

export function useStopCrawlJobMutation(jobId: number) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: () => stopCrawlJob(jobId),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.jobsRoot }),
        queryClient.invalidateQueries({ queryKey: queryKeys.jobDetail(jobId) }),
      ])
    },
  })
}
