export type JobStatus = 'pending' | 'running' | 'finished' | 'failed' | 'stopped'
export type SortOrder = 'asc' | 'desc'
export type JobsListSortBy = 'id' | 'created_at'
export type PagesSortBy =
  | 'url'
  | 'status_code'
  | 'depth'
  | 'title'
  | 'fetched_at'
  | 'response_time_ms'
export type LinksSortBy = 'source_url' | 'target_url' | 'target_domain' | 'is_internal' | 'is_nofollow'

export interface CrawlJobCreateInput {
  root_url: string
  max_urls: number
  max_depth: number
  delay: number
}

export interface JobsListQueryParams {
  sort_by: JobsListSortBy
  sort_order: SortOrder
  limit: number
}

export interface CrawlJobListItem {
  id: number
  status: JobStatus
  root_url: string | null
  created_at: string
  started_at: string | null
  finished_at: string | null
  total_pages: number
  total_internal_links: number
  total_external_links: number
  total_errors: number
}

export interface CrawlJobSummaryCounts {
  total_pages: number
  total_links: number
  total_internal_links: number
  total_external_links: number
  pages_missing_title: number
  pages_missing_meta_description: number
  pages_missing_h1: number
  pages_non_indexable_like: number
  broken_internal_links: number
  redirecting_internal_links: number
}

export interface CrawlJobProgress {
  visited_pages: number
  queued_urls: number
  discovered_links: number
  internal_links: number
  external_links: number
  errors_count: number
}

export interface CrawlJobDetail {
  id: number
  site_id: number
  status: JobStatus
  created_at: string
  started_at: string | null
  finished_at: string | null
  settings_json: Record<string, unknown>
  stats_json: Record<string, unknown>
  summary_counts: CrawlJobSummaryCounts
  progress: CrawlJobProgress
}

export interface PaginatedResponse<T> {
  items: T[]
  page: number
  page_size: number
  total_items: number
  total_pages: number
}

export interface PageRecord {
  id: number
  crawl_job_id: number
  url: string
  normalized_url: string
  final_url: string | null
  status_code: number | null
  title: string | null
  meta_description: string | null
  h1: string | null
  canonical_url: string | null
  robots_meta: string | null
  content_type: string | null
  response_time_ms: number | null
  is_internal: boolean
  depth: number
  fetched_at: string | null
  error_message: string | null
  created_at: string
}

export interface LinkRecord {
  id: number
  crawl_job_id: number
  source_page_id: number
  source_url: string
  target_url: string
  target_normalized_url: string | null
  target_domain: string | null
  anchor_text: string | null
  rel_attr: string | null
  is_nofollow: boolean
  is_internal: boolean
  created_at: string
}

export interface PagesQueryParams {
  page: number
  page_size: number
  sort_by: PagesSortBy
  sort_order: SortOrder
  has_title?: boolean
  has_meta_description?: boolean
  has_h1?: boolean
  status_code_min?: number
  status_code_max?: number
  canonical_missing?: boolean
  robots_meta_contains?: string
  non_indexable_like?: boolean
}

export interface LinksQueryParams {
  page: number
  page_size: number
  sort_by: LinksSortBy
  sort_order: SortOrder
  is_internal?: boolean
  is_nofollow?: boolean
  target_domain?: string
  has_anchor?: boolean
}

export interface PageIssue {
  page_id: number
  url: string
  normalized_url: string
  status_code: number | null
  title?: string | null
  meta_description?: string | null
  h1?: string | null
}

export interface DuplicateValueGroup {
  value: string
  count: number
  pages: PageIssue[]
}

export interface LinkIssue {
  link_id: number
  source_url: string
  target_url: string
  target_normalized_url: string | null
  target_status_code?: number | null
  final_url?: string | null
}

export interface NonIndexableLikeSignal {
  page_id: number
  url: string
  normalized_url: string
  status_code: number | null
  robots_meta: string | null
  signals: string[]
}

export interface AuditSummary {
  total_pages: number
  pages_missing_title: number
  pages_missing_meta_description: number
  pages_missing_h1: number
  pages_duplicate_title_groups: number
  pages_duplicate_meta_description_groups: number
  broken_internal_links: number
  unresolved_internal_targets: number
  redirecting_internal_links: number
  non_indexable_like_signals: number
}

export interface AuditReport {
  crawl_job_id: number
  summary: AuditSummary
  pages_missing_title: PageIssue[]
  pages_missing_meta_description: PageIssue[]
  pages_missing_h1: PageIssue[]
  pages_duplicate_title: DuplicateValueGroup[]
  pages_duplicate_meta_description: DuplicateValueGroup[]
  broken_internal_links: LinkIssue[]
  unresolved_internal_targets: LinkIssue[]
  redirecting_internal_links: LinkIssue[]
  non_indexable_like_signals: NonIndexableLikeSignal[]
}
