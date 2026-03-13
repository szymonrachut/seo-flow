import { useQuery } from '@tanstack/react-query'

import { apiRequest } from '../../api/client'
import { queryKeys } from '../../api/queryKeys'
import type { AuditReport } from '../../types/api'

export async function getAuditReport(jobId: number): Promise<AuditReport> {
  return apiRequest<AuditReport>(`/crawl-jobs/${jobId}/audit`)
}

export function useAuditQuery(jobId: number) {
  return useQuery({
    queryKey: queryKeys.jobAudit(jobId),
    queryFn: () => getAuditReport(jobId),
  })
}
