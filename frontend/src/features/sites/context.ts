import { useOutletContext } from 'react-router-dom'

import type { SiteDetail } from '../../types/api'

export interface SiteWorkspaceContextValue {
  site: SiteDetail
  activeCrawlId: number | null
  baselineCrawlId: number | null
  updateCrawlContext: (updates: { active_crawl_id?: number; baseline_crawl_id?: number }) => void
}

export function useSiteWorkspaceContext() {
  return useOutletContext<SiteWorkspaceContextValue>()
}
