export type JobStatus = 'pending' | 'running' | 'finished' | 'failed' | 'stopped'
export type SortOrder = 'asc' | 'desc'
export type RenderMode = 'never' | 'auto' | 'always'
export type GscDateRangeLabel = 'last_28_days' | 'last_90_days'
export type PriorityLevel = 'low' | 'medium' | 'high' | 'critical'
export type ImpactLevel = 'low' | 'medium' | 'high'
export type EffortLevel = 'low' | 'medium' | 'high'
export type OpportunityType =
  | 'QUICK_WINS'
  | 'HIGH_IMPRESSIONS_LOW_CTR'
  | 'TRAFFIC_WITH_TECHNICAL_ISSUES'
  | 'IMPORTANT_BUT_WEAK'
  | 'LOW_HANGING_FRUIT'
  | 'HIGH_RISK_PAGES'
  | 'UNDERLINKED_OPPORTUNITIES'
export type ContentRecommendationType =
  | 'MISSING_SUPPORTING_CONTENT'
  | 'THIN_CLUSTER'
  | 'EXPAND_EXISTING_PAGE'
  | 'MISSING_STRUCTURAL_PAGE_TYPE'
  | 'INTERNAL_LINKING_SUPPORT'
export type ContentGeneratorAssetStatus = 'pending' | 'running' | 'ready' | 'failed'
export type ContentRecommendationSegment =
  | 'create_new_page'
  | 'expand_existing_page'
  | 'strengthen_cluster'
  | 'improve_internal_support'
export type ContentRecommendationOutcomeKind =
  | 'gsc'
  | 'cannibalization'
  | 'issue_flags'
  | 'internal_linking'
  | 'mixed'
  | 'unknown'
export type ContentRecommendationOutcomeStatus =
  | 'improved'
  | 'unchanged'
  | 'pending'
  | 'too_early'
  | 'limited'
  | 'unavailable'
  | 'worsened'
export type ContentRecommendationOutcomeWindow = '7d' | '30d' | '90d' | 'all'
export type ImplementedContentRecommendationStatusFilter = 'all' | ContentRecommendationOutcomeStatus
export type ImplementedContentRecommendationModeFilter = 'all' | ContentRecommendationOutcomeKind
export type ImplementedContentRecommendationSort =
  | 'implemented_at_desc'
  | 'implemented_at_asc'
  | 'outcome'
  | 'recommendation_type'
  | 'title'
export const IMPLEMENTED_CONTENT_RECOMMENDATION_STATUS_ORDER = [
  'improved',
  'unchanged',
  'pending',
  'too_early',
  'limited',
  'unavailable',
  'worsened',
] as const satisfies readonly ContentRecommendationOutcomeStatus[]
export type CompetitiveGapType = 'NEW_TOPIC' | 'EXPAND_EXISTING_TOPIC' | 'MISSING_SUPPORTING_PAGE'
export type CompetitiveGapSegment = 'create_new_page' | 'expand_existing_page' | 'strengthen_cluster'
export type CompetitiveGapSemanticStatus =
  | 'not_started'
  | 'queued'
  | 'running'
  | 'completed'
  | 'ready'
  | 'partial'
  | 'failed'
  | 'stale'
  | 'cancelled'
export type CompetitiveGapSemanticMatchStatus =
  | 'exact_match'
  | 'semantic_match'
  | 'partial_coverage'
  | 'no_meaningful_match'
export type CompetitiveGapCoverageType =
  | 'exact_coverage'
  | 'strong_semantic_coverage'
  | 'partial_coverage'
  | 'wrong_intent_coverage'
  | 'commercial_missing_supporting'
  | 'informational_missing_commercial'
  | 'no_meaningful_coverage'
export type CompetitiveGapDetailType =
  | 'NEW_TOPIC'
  | 'EXPAND_EXISTING_PAGE'
  | 'MISSING_SUPPORTING_CONTENT'
  | 'MISSING_MONEY_PAGE'
  | 'INTENT_MISMATCH'
  | 'FORMAT_GAP'
  | 'GEO_GAP'
export type CompetitiveGapSemanticAnalysisMode = 'not_started' | 'local_only' | 'llm_only' | 'mixed'
export type CompetitiveGapDiagnosticFlag =
  | 'strategy'
  | 'active_crawl'
  | 'competitors'
  | 'competitor_pages'
  | 'competitor_extractions'
  | 'own_pages'
export type CompetitiveGapEmptyStateReason =
  | 'no_active_crawl'
  | 'no_competitors'
  | 'no_competitor_pages'
  | 'no_competitor_extractions'
  | 'no_own_pages'
  | 'filters_excluded_all'
export type CompetitiveGapDataSourceMode = 'legacy' | 'raw_candidates' | 'reviewed'
export type CompetitiveGapDecisionAction = 'keep' | 'remove' | 'merge' | 'rewrite'
export type SemstormResultType = 'organic' | 'paid'
export type SemstormCompetitorsType = 'all' | 'similar'
export type SemstormOpportunityBucket = 'quick_win' | 'core_opportunity' | 'watchlist'
export type SemstormCoverageStatus = 'missing' | 'weak_coverage' | 'covered'
export type SemstormDecisionType = 'create_new_page' | 'expand_existing_page' | 'monitor_only'
export type SemstormGscSignalStatus = 'none' | 'weak' | 'present'
export type SemstormOpportunityStateStatus = 'new' | 'accepted' | 'dismissed' | 'promoted'
export type SemstormPromotionStatus = 'active' | 'archived'
export type SemstormPlanStateStatus = 'planned' | 'in_progress' | 'done' | 'archived'
export type SemstormPlanTargetPageType =
  | 'new_page'
  | 'expand_existing'
  | 'refresh_existing'
  | 'cluster_support'
export type SemstormBriefStateStatus = 'draft' | 'ready' | 'in_execution' | 'completed' | 'archived'
export type SemstormBriefType = 'new_page' | 'expand_existing' | 'refresh_existing' | 'cluster_support'
export type SemstormBriefSearchIntent =
  | 'informational'
  | 'commercial'
  | 'transactional'
  | 'navigational'
  | 'mixed'
export type SemstormImplementationStatus = 'too_early' | 'implemented' | 'evaluated' | 'archived'
export type SemstormOutcomeStatus = 'too_early' | 'no_signal' | 'weak_signal' | 'positive_signal'
export type SemstormBriefEnrichmentStatus = 'completed' | 'failed'
export type SemstormBriefEnrichmentEngineMode = 'mock' | 'llm'
export type CompetitiveGapSortBy =
  | 'priority_score'
  | 'consensus_score'
  | 'competitor_count'
  | 'competitor_coverage_score'
  | 'own_coverage_score'
  | 'strategy_alignment_score'
  | 'business_value_score'
  | 'merged_topic_count'
  | 'confidence'
  | 'topic_label'
  | 'gap_type'
  | 'page_type'
export type PageType =
  | 'home'
  | 'category'
  | 'product'
  | 'service'
  | 'blog_article'
  | 'blog_index'
  | 'contact'
  | 'about'
  | 'faq'
  | 'location'
  | 'legal'
  | 'utility'
  | 'other'
export type PageBucket = 'commercial' | 'informational' | 'utility' | 'trust' | 'other'
export type InternalLinkingIssueType =
  | 'ORPHAN_LIKE'
  | 'WEAKLY_LINKED_IMPORTANT'
  | 'LOW_ANCHOR_DIVERSITY'
  | 'EXACT_MATCH_ANCHOR_CONCENTRATION'
  | 'BOILERPLATE_DOMINATED'
  | 'LOW_LINK_EQUITY'
export type CannibalizationSeverity = 'low' | 'medium' | 'high' | 'critical'
export type CannibalizationRecommendationType =
  | 'MERGE_CANDIDATE'
  | 'SPLIT_INTENT_CANDIDATE'
  | 'REINFORCE_PRIMARY_URL'
  | 'QUERY_CLUSTER_WITHOUT_CLEAR_PRIMARY'
  | 'LOW_VALUE_OVERLAP'
  | 'HIGH_IMPACT_CANNIBALIZATION'
export type CrawlCompareChangeType = 'improved' | 'worsened' | 'unchanged' | 'new' | 'missing'
export type MetricTrend = 'improved' | 'worsened' | 'flat'
export type CompareDeltaTrend = 'improved' | 'worsened' | 'flat'
export type AuditCompareSectionStatus = 'resolved' | 'new' | 'improved' | 'worsened' | 'unchanged'
export type OpportunityCompareHighlight =
  | 'NEW_URL'
  | 'MISSING_URL'
  | 'NEW_OPPORTUNITY'
  | 'RESOLVED_OPPORTUNITY'
  | 'PRIORITY_UP'
  | 'PRIORITY_DOWN'
  | 'ENTERED_ACTIONABLE'
  | 'LEFT_ACTIONABLE'
export type InternalLinkingCompareHighlight =
  | 'NEW_ORPHAN_LIKE'
  | 'RESOLVED_ORPHAN_LIKE'
  | 'WEAKLY_LINKED_IMPROVED'
  | 'WEAKLY_LINKED_WORSENED'
  | 'LINK_EQUITY_IMPROVED'
  | 'LINK_EQUITY_WORSENED'
  | 'LINKING_PAGES_UP'
  | 'LINKING_PAGES_DOWN'
  | 'ANCHOR_DIVERSITY_IMPROVED'
  | 'ANCHOR_DIVERSITY_WORSENED'
  | 'BOILERPLATE_IMPROVED'
  | 'BOILERPLATE_WORSENED'
export type JobsListSortBy =
  | 'id'
  | 'created_at'
  | 'status'
  | 'started_at'
  | 'finished_at'
  | 'total_pages'
  | 'total_internal_links'
  | 'total_external_links'
  | 'total_errors'
export type PagesSortBy =
  | 'url'
  | 'status_code'
  | 'depth'
  | 'page_type'
  | 'page_bucket'
  | 'page_type_confidence'
  | 'title'
  | 'title_length'
  | 'meta_description'
  | 'meta_description_length'
  | 'h1'
  | 'h1_length'
  | 'h1_count'
  | 'h2_count'
  | 'canonical_url'
  | 'robots_meta'
  | 'x_robots_tag'
  | 'word_count'
  | 'was_rendered'
  | 'js_heavy_like'
  | 'schema_count'
  | 'images_count'
  | 'images_missing_alt_count'
  | 'html_size_bytes'
  | 'gsc_clicks'
  | 'gsc_impressions'
  | 'gsc_ctr'
  | 'gsc_position'
  | 'gsc_top_queries_count'
  | 'priority_score'
  | 'fetched_at'
  | 'response_time_ms'
export type StrategyNormalizationStatus = 'not_started' | 'not_processed' | 'ready' | 'failed'
export type CompetitorSyncStatus = 'idle' | 'queued' | 'running' | 'done' | 'failed' | 'not_started'
export type CompetitorSyncRunStatus = 'queued' | 'running' | 'done' | 'failed' | 'stale' | 'cancelled'
export type CompetitorSyncRunStage =
  | 'queued'
  | 'crawling'
  | 'persisting'
  | 'extracting'
  | 'finalizing'
  | 'done'
  | 'failed'
  | 'stale'
  | 'cancelled'
export type ContentRecommendationsSortBy =
  | 'priority_score'
  | 'confidence'
  | 'impact'
  | 'effort'
  | 'cluster_label'
  | 'recommendation_type'
  | 'page_type'
export type LinksSortBy =
  | 'source_url'
  | 'target_url'
  | 'target_domain'
  | 'anchor_text'
  | 'is_internal'
  | 'is_nofollow'

export interface CrawlJobCreateInput {
  root_url: string
  max_urls: number
  max_depth: number
  delay: number
  render_mode: RenderMode
  render_timeout_ms: number
  max_rendered_pages_per_job: number
}

export interface JobsListQueryParams {
  sort_by: JobsListSortBy
  sort_order: SortOrder
  limit: number
  status_filter?: JobStatus
  search?: string
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
  rendered_pages: number
  js_heavy_like_pages: number
  pages_with_render_errors: number
  pages_with_schema: number
  pages_with_x_robots_tag: number
  pages_with_gsc_28d: number
  pages_with_gsc_90d: number
  gsc_opportunities_28d: number
  gsc_opportunities_90d: number
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

export interface SiteSummary {
  total_crawls: number
  pending_crawls: number
  running_crawls: number
  finished_crawls: number
  failed_crawls: number
  stopped_crawls: number
  first_crawl_at: string | null
  last_crawl_at: string | null
}

export interface SiteCrawlListItem extends CrawlJobListItem {
  site_id: number
}

export interface SiteListItem {
  id: number
  domain: string
  root_url: string
  created_at: string
  selected_gsc_property_uri: string | null
  summary: SiteSummary
  latest_crawl: SiteCrawlListItem | null
}

export interface SiteDetail {
  id: number
  domain: string
  root_url: string
  created_at: string
  selected_gsc_property_uri: string | null
  selected_gsc_property_permission_level: string | null
  summary: SiteSummary
  active_crawl_id: number | null
  baseline_crawl_id: number | null
  active_crawl: CrawlJobDetail | null
  baseline_crawl: CrawlJobDetail | null
  crawl_history: SiteCrawlListItem[]
}

export interface SiteContentGeneratorAsset {
  site_id: number
  has_assets: boolean
  can_regenerate: boolean
  active_crawl_id: number | null
  active_crawl_status: JobStatus | null
  status: ContentGeneratorAssetStatus | null
  basis_crawl_job_id: number | null
  surfer_custom_instructions: string | null
  seowriting_details_to_include: string | null
  introductory_hook_brief: string | null
  source_urls: string[]
  source_pages_hash: string | null
  prompt_version: string | null
  llm_provider: string | null
  llm_model: string | null
  generated_at: string | null
  last_error_code: string | null
  last_error_message: string | null
}

export interface GenerateSiteContentGeneratorAssetsInput {
  output_language?: string
}

export interface GenerateSiteContentGeneratorAssetsResponse {
  success: boolean
  generation_triggered: boolean
  asset: SiteContentGeneratorAsset
  error_code: string | null
  error_message: string | null
}

export interface SiteContentRecommendationsContext {
  site_id: number
  site_domain: string
  active_crawl_id: number | null
  baseline_crawl_id: number | null
  gsc_date_range: GscDateRangeLabel
  active_crawl: SiteCompareCrawlContext | null
  baseline_crawl: SiteCompareCrawlContext | null
}

export type ContentRecommendationHelperCompareSignalKey =
  | 'url_presence'
  | 'technical_issues'
  | 'internal_linking_issues'
  | 'linking_pages'
  | 'gsc_clicks'
  | 'gsc_position'
  | 'top_queries'
  | 'cannibalization'

export interface ContentRecommendationUrlImprovementGscContext {
  available: boolean
  impressions: number
  clicks: number
  ctr: number
  position: number | null
  top_queries_count: number
  notes: string[]
}

export interface ContentRecommendationUrlImprovementInternalLinkingContext {
  internal_linking_score: number
  issue_count: number
  issue_types: InternalLinkingIssueType[]
  incoming_internal_links: number
  incoming_internal_linking_pages: number
  link_equity_score: number
  anchor_diversity_score: number
}

export interface ContentRecommendationUrlImprovementCannibalizationContext {
  has_active_signals: boolean
  severity: CannibalizationSeverity | null
  competing_urls_count: number
  common_queries_count: number
  strongest_competing_url: string | null
  shared_top_queries: string[]
}

export interface ContentRecommendationUrlImprovementCompareSignal {
  key: ContentRecommendationHelperCompareSignalKey
  label: string
  status: CrawlCompareChangeType
  detail: string
}

export interface ContentRecommendationUrlImprovementCompareContext {
  baseline_crawl_id: number
  signals: ContentRecommendationUrlImprovementCompareSignal[]
}

export interface ContentRecommendationUrlImprovementHelper {
  target_url: string
  title: string | null
  page_type: PageType
  page_bucket: PageBucket | null
  open_issues: string[]
  improvement_actions: string[]
  supporting_signals: string[]
  gsc_context: ContentRecommendationUrlImprovementGscContext
  internal_linking_context: ContentRecommendationUrlImprovementInternalLinkingContext
  cannibalization_context: ContentRecommendationUrlImprovementCannibalizationContext
  compare_context: ContentRecommendationUrlImprovementCompareContext | null
}

export interface ContentRecommendation {
  id: string
  recommendation_key: string
  recommendation_type: ContentRecommendationType
  segment: ContentRecommendationSegment
  cluster_key: string
  cluster_label: string
  target_page_id: number | null
  target_url: string | null
  page_type: PageType
  target_page_type: PageType
  suggested_page_type: PageType | null
  priority_score: number
  confidence: number
  impact: ImpactLevel
  effort: EffortLevel
  cluster_strength: number
  coverage_gap_score: number
  internal_support_score: number
  rationale: string
  signals: string[]
  reasons: string[]
  prerequisites: string[]
  supporting_urls: string[]
  url_improvement_helper: ContentRecommendationUrlImprovementHelper | null
  was_implemented_before: boolean
  previously_implemented_at: string | null
}

export interface ContentRecommendationOutcomeDetail {
  label: string
  before: string | null
  after: string | null
  change: string | null
}

export interface ImplementedContentRecommendation {
  recommendation_key: string
  recommendation_type: ContentRecommendationType
  segment: ContentRecommendationSegment | null
  target_url: string | null
  normalized_target_url: string | null
  target_title_snapshot: string | null
  suggested_page_type: PageType | null
  cluster_label: string | null
  cluster_key: string | null
  recommendation_text: string
  signals_snapshot: string[]
  reasons_snapshot: string[]
  helper_snapshot: ContentRecommendationUrlImprovementHelper | null
  primary_outcome_kind: ContentRecommendationOutcomeKind
  outcome_status: ContentRecommendationOutcomeStatus
  outcome_summary: string
  outcome_details: ContentRecommendationOutcomeDetail[]
  outcome_window: ContentRecommendationOutcomeWindow
  is_too_early: boolean
  days_since_implemented: number | null
  eligible_for_window: boolean
  implemented_at: string
  implemented_crawl_job_id: number | null
  implemented_baseline_crawl_job_id: number | null
  times_marked_done: number
}

export interface ImplementedContentRecommendationStatusCounts {
  improved: number
  unchanged: number
  pending: number
  too_early: number
  limited: number
  unavailable: number
  worsened: number
}

export interface ImplementedContentRecommendationModeCounts {
  gsc: number
  internal_linking: number
  cannibalization: number
  issue_flags: number
  mixed: number
  unknown: number
}

export interface ImplementedContentRecommendationSummary {
  total_count: number
  status_counts: ImplementedContentRecommendationStatusCounts
  mode_counts: ImplementedContentRecommendationModeCounts
}

export interface ContentRecommendationMarkDoneInput {
  recommendation_key: string
  active_crawl_id?: number
  baseline_crawl_id?: number
  gsc_date_range: GscDateRangeLabel
}

export interface ContentRecommendationMarkDoneResponse {
  recommendation_key: string
  implemented_at: string
  implemented_crawl_job_id: number | null
  implemented_baseline_crawl_job_id: number | null
  primary_outcome_kind: ContentRecommendationOutcomeKind
  times_marked_done: number
}

export interface ContentRecommendationsSummary {
  total_recommendations: number
  implemented_recommendations: number
  high_priority_recommendations: number
  clusters_covered: number
  create_new_page_recommendations: number
  expand_existing_page_recommendations: number
  strengthen_cluster_recommendations: number
  improve_internal_support_recommendations: number
  counts_by_type: Record<ContentRecommendationType, number>
  counts_by_page_type: Record<PageType, number>
}

export interface SiteContentRecommendationsQueryParams {
  active_crawl_id?: number
  baseline_crawl_id?: number
  gsc_date_range: GscDateRangeLabel
  page: number
  page_size: number
  sort_by: ContentRecommendationsSortBy
  sort_order: SortOrder
  recommendation_type?: ContentRecommendationType
  segment?: ContentRecommendationSegment
  page_type?: PageType
  cluster?: string
  confidence_min?: number
  priority_score_min?: number
  implemented_outcome_window: ContentRecommendationOutcomeWindow
  implemented_status_filter: ImplementedContentRecommendationStatusFilter
  implemented_mode_filter: ImplementedContentRecommendationModeFilter
  implemented_search?: string
  implemented_sort: ImplementedContentRecommendationSort
}

export interface PaginatedSiteContentRecommendationsResponse {
  context: SiteContentRecommendationsContext
  summary: ContentRecommendationsSummary
  items: ContentRecommendation[]
  implemented_items: ImplementedContentRecommendation[]
  implemented_total: number
  implemented_summary: ImplementedContentRecommendationSummary
  page: number
  page_size: number
  total_items: number
  total_pages: number
}

export interface NormalizedCompetitiveGapStrategy {
  schema_version: 'competitive_gap_strategy_v1'
  business_summary: string
  target_audiences: string[]
  primary_goals: string[]
  priority_topics: string[]
  supporting_topics: string[]
  priority_page_types: PageType[]
  geographic_focus: string[]
  constraints: string[]
  differentiation_points: string[]
}

export interface CompetitiveGapStrategy {
  id: number
  site_id: number
  raw_user_input: string
  normalized_strategy_json: NormalizedCompetitiveGapStrategy | null
  llm_provider: string | null
  llm_model: string | null
  prompt_version: string | null
  normalization_status: StrategyNormalizationStatus
  last_normalization_attempt_at: string | null
  normalization_fallback_used: boolean
  normalization_debug_code: string | null
  normalization_debug_message: string | null
  normalized_at: string | null
  created_at: string
  updated_at: string
}

export interface SiteCompetitorSyncSummary {
  visited_urls_count: number
  stored_pages_count: number
  extracted_pages_count: number
  skipped_urls_count: number
  skipped_non_html_count: number
  skipped_non_indexable_count: number
  skipped_out_of_scope_count: number
  skipped_filtered_count: number
  skipped_low_value_count: number
  skipped_duplicate_url_count: number
  skipped_fetch_error_count: number
  extraction_created_count: number
  extraction_skipped_unchanged_count: number
  extraction_failed_count: number
  sample_urls_by_reason: Record<string, string[]>
}

export interface SiteCompetitor {
  id: number
  site_id: number
  label: string
  root_url: string
  domain: string
  is_active: boolean
  notes: string | null
  last_sync_run_id: number
  last_sync_status: CompetitorSyncStatus
  last_sync_stage: string
  last_sync_started_at: string | null
  last_sync_finished_at: string | null
  last_sync_error_code: string | null
  last_sync_error: string | null
  last_sync_processed_urls: number
  last_sync_url_limit: number
  last_sync_processed_extraction_pages: number
  last_sync_total_extractable_pages: number
  last_sync_progress_percent: number
  last_sync_summary: SiteCompetitorSyncSummary
  accepted_pages_count?: number
  rejected_pages_count?: number
  semantic_status?: CompetitiveGapSemanticStatus | null
  semantic_analysis_mode?: CompetitiveGapSemanticAnalysisMode | null
  last_semantic_stage?: string | null
  last_semantic_run_started_at?: string | null
  last_semantic_run_finished_at?: string | null
  last_semantic_heartbeat_at?: string | null
  last_semantic_lease_expires_at?: string | null
  last_semantic_error_code?: string | null
  last_semantic_error?: string | null
  semantic_candidates_count?: number
  semantic_run_scope_candidates_count?: number
  semantic_llm_jobs_count?: number
  semantic_resolved_count?: number
  semantic_run_scope_resolved_count?: number
  semantic_progress_percent?: number
  semantic_cache_hits?: number
  semantic_fallback_count?: number
  semantic_llm_merged_urls_count?: number
  semantic_cluster_count?: number
  semantic_low_confidence_count?: number
  semantic_cards_count?: number
  semantic_own_page_profiles_count?: number
  semantic_canonical_pages_count?: number
  semantic_duplicate_pages_count?: number
  semantic_near_duplicate_pages_count?: number
  semantic_version?: string | null
  semantic_cluster_version?: string | null
  semantic_coverage_version?: string | null
  semantic_model?: string | null
  semantic_prompt_version?: string | null
  pages_count: number
  extracted_pages_count: number
  last_extracted_at: string | null
  created_at: string
  updated_at: string
}

export interface SiteCompetitorSyncRun {
  id: number
  site_id: number
  competitor_id: number
  run_id: number
  status: CompetitorSyncRunStatus
  stage: CompetitorSyncRunStage | string
  trigger_source: string
  started_at: string | null
  finished_at: string | null
  last_heartbeat_at: string | null
  lease_expires_at: string | null
  error_code: string | null
  error_message_safe: string | null
  summary_json: SiteCompetitorSyncSummary
  retry_of_run_id: number | null
  processed_urls: number
  url_limit: number
  processed_extraction_pages: number
  total_extractable_pages: number
  progress_percent: number
  created_at: string
  updated_at: string
}

export interface SiteCompetitorSyncAllResponse {
  site_id: number
  queued_competitor_ids: number[]
  already_running_competitor_ids: number[]
  queued_count: number
  queued_runs: SiteCompetitorSyncRun[]
}

export interface SiteContentGapReviewRun {
  id: number
  site_id: number
  basis_crawl_job_id: number
  run_id: number
  status: string
  stage: string
  trigger_source: string
  scope_type: string
  selected_candidate_ids_json: number[]
  candidate_count: number
  candidate_set_hash: string
  candidate_generation_version: string
  own_context_hash: string
  gsc_context_hash: string | null
  context_summary_json: Record<string, unknown>
  output_language: string
  llm_provider: string | null
  llm_model: string | null
  prompt_version: string | null
  schema_version: string | null
  batch_size: number
  batch_count: number
  completed_batch_count: number
  lease_owner: string | null
  lease_expires_at: string | null
  last_heartbeat_at: string | null
  started_at: string | null
  finished_at: string | null
  error_code: string | null
  error_message_safe: string | null
  retry_of_run_id: number | null
  created_at: string
  updated_at: string
}

export type SiteCompetitorReviewStatus = 'accepted' | 'rejected'

export interface SiteCompetitorReviewSummary {
  total_pages: number
  accepted_pages: number
  rejected_pages: number
  current_extractions_count: number
  counts_by_reason: Record<string, number>
}

export interface SiteCompetitorReviewRecord {
  id: number
  url: string
  normalized_url: string
  final_url: string | null
  status_code: number | null
  title: string | null
  meta_description: string | null
  h1: string | null
  page_type: PageType
  page_bucket: string
  page_type_confidence: number
  semantic_eligible: boolean
  semantic_exclusion_reason: string | null
  review_status: SiteCompetitorReviewStatus
  review_reason_code: string
  review_reason_detail: string
  has_current_extraction: boolean
  current_extraction_topic_label: string | null
  current_extraction_confidence: number | null
  last_extracted_at: string | null
  diagnostics: Record<string, unknown>
  fetched_at: string | null
  updated_at: string
}

export interface PaginatedSiteCompetitorReviewResponse extends PaginatedResponse<SiteCompetitorReviewRecord> {
  site_id: number
  competitor_id: number
  review_status: SiteCompetitorReviewStatus | 'all'
  summary: SiteCompetitorReviewSummary
}

export interface CompetitiveGapDataReadiness {
  has_active_crawl: boolean
  has_strategy: boolean
  has_active_competitors: boolean
  gap_ready: boolean
  missing_inputs: CompetitiveGapDiagnosticFlag[]
  active_competitors_count: number
  competitors_with_pages_count: number
  competitors_with_current_extractions_count: number
  total_competitor_pages_count: number
  total_current_extractions_count: number
}

export interface CompetitiveGapSemanticDiagnostics {
  semantic_version: string | null
  cluster_version: string | null
  coverage_version: string | null
  competitor_semantic_cards_count: number
  own_page_semantic_profiles_count: number
  canonical_pages_count: number
  duplicate_pages_count: number
  near_duplicate_pages_count: number
  clusters_count: number
  low_confidence_clusters_count: number
  latest_failure_stage: string | null
  latest_failure_error_code: string | null
  latest_failure_error_message: string | null
  coverage_breakdown: Record<CompetitiveGapCoverageType, number>
}

export interface CompetitiveGapContext {
  site_id: number
  site_domain: string
  active_crawl_id: number | null
  basis_crawl_job_id?: number | null
  gsc_date_range: GscDateRangeLabel
  active_crawl: SiteCompareCrawlContext | null
  strategy_present: boolean
  active_competitor_count: number
  data_readiness: CompetitiveGapDataReadiness
  data_source_mode?: CompetitiveGapDataSourceMode
  is_outdated_for_active_crawl?: boolean
  review_run_status?: string | null
  semantic_diagnostics: CompetitiveGapSemanticDiagnostics
  empty_state_reason: CompetitiveGapEmptyStateReason | null
}

export interface CompetitiveGapCanonicalizationSummary {
  canonical_pages_count: number
  duplicate_pages_count: number
  near_duplicate_pages_count: number
  filtered_leftovers_count: number
}

export interface CompetitiveGapClusterQualitySummary {
  clusters_count: number
  low_confidence_clusters_count: number
  average_cluster_confidence: number
  average_cluster_member_count: number
}

export interface CompetitiveGapRow {
  gap_key: string
  gap_type: CompetitiveGapType
  segment: CompetitiveGapSegment
  topic_key: string
  topic_label: string
  semantic_cluster_key?: string | null
  canonical_topic_label?: string | null
  merged_topic_count?: number | null
  own_match_status?: CompetitiveGapSemanticMatchStatus | null
  coverage_type?: CompetitiveGapCoverageType | null
  coverage_confidence?: number | null
  coverage_rationale?: string | null
  coverage_best_own_urls?: string[]
  mismatch_notes?: string[]
  own_match_source?: string | null
  gap_detail_type?: CompetitiveGapDetailType | null
  target_page_id: number | null
  target_url: string | null
  page_type: PageType
  target_page_type: PageType | null
  suggested_page_type: PageType | null
  cluster_member_count?: number
  cluster_confidence?: number | null
  cluster_intent_profile?: string | null
  cluster_role_summary?: Record<string, number>
  cluster_entities?: string[]
  cluster_geo_scope?: string | null
  supporting_evidence?: string[]
  competitor_ids: number[]
  competitor_count: number
  competitor_urls: string[]
  consensus_score: number
  competitor_coverage_score: number
  own_coverage_score: number
  strategy_alignment_score: number
  business_value_score: number
  priority_score: number
  confidence: number
  rationale: string
  signals: Record<string, unknown>
  decision_action?: CompetitiveGapDecisionAction | null
  reviewed_phrase?: string | null
  reviewed_topic_label?: string | null
  fit_score?: number | null
  remove_reason_text?: string | null
  merge_target_phrase?: string | null
}

export interface CompetitiveGapSummary {
  total_gaps: number
  high_priority_gaps: number
  competitors_considered: number
  topics_covered: number
  counts_by_type: Record<CompetitiveGapType, number>
  counts_by_gap_detail_type: Record<CompetitiveGapDetailType, number>
  counts_by_coverage_type: Record<CompetitiveGapCoverageType, number>
  counts_by_page_type: Record<PageType, number>
  canonicalization_summary: CompetitiveGapCanonicalizationSummary
  cluster_quality_summary: CompetitiveGapClusterQualitySummary
}

export interface SiteCompetitiveGapQueryParams {
  active_crawl_id?: number
  gsc_date_range: GscDateRangeLabel
  page: number
  page_size: number
  sort_by: CompetitiveGapSortBy
  sort_order: SortOrder
  gap_type?: CompetitiveGapType
  segment?: CompetitiveGapSegment
  competitor_id?: number
  page_type?: PageType
  own_match_status?: CompetitiveGapSemanticMatchStatus
  topic?: string
  priority_score_min?: number
  consensus_min?: number
}

export interface PaginatedCompetitiveGapResponse {
  context: CompetitiveGapContext
  summary: CompetitiveGapSummary
  items: CompetitiveGapRow[]
  page: number
  page_size: number
  total_items: number
  total_pages: number
}

export interface CompetitiveGapExplanationRequest {
  gap_key: string
  active_crawl_id: number
  gsc_date_range: GscDateRangeLabel
  gap_signature?: string
}

export type CompetitiveGapSemanticRerunMode = 'incremental' | 'full'

export interface CompetitiveGapSemanticRerunRequest {
  mode: CompetitiveGapSemanticRerunMode
  active_crawl_id?: number
}

export interface CompetitiveGapSemanticRerunResponse {
  site_id: number
  mode?: CompetitiveGapSemanticRerunMode
  active_crawl_id?: number | null
  queued_count?: number
  queued_competitor_ids?: number[]
  already_running_competitor_ids?: number[]
  skipped_competitor_ids?: number[]
  message?: string | null
}

export interface CompetitiveGapExplanationResponse {
  gap_key: string
  gap_signature: string
  explanation: string
  bullets: string[]
  used_llm: boolean
  fallback_used: boolean
  fallback_reason: string | null
  llm_provider: string | null
  llm_model: string | null
  prompt_version: string
}

export interface SemstormDiscoveryRunCreateInput {
  max_competitors: number
  max_keywords_per_competitor: number
  result_type: SemstormResultType
  include_basic_stats: boolean
  competitors_type?: SemstormCompetitorsType
}

export interface SemstormKeywordBasicStats {
  keywords: number
  keywords_top: number
  traffic: number
  traffic_potential: number
  search_volume: number
  search_volume_top: number
}

export interface SemstormTopQuery {
  keyword: string
  position: number | null
  position_change: number | null
  url: string | null
  traffic: number | null
  traffic_change: number | null
  volume: number | null
  competitors: number | null
  cpc: number | null
  trends: number[]
}

export interface SemstormCompetitorDiscovery {
  rank: number | null
  domain: string
  common_keywords: number
  traffic: number
  queries_count: number
  basic_stats: SemstormKeywordBasicStats | null
  top_queries: SemstormTopQuery[]
}

export interface SemstormDiscoveryRunParams {
  max_competitors: number
  max_keywords_per_competitor: number
  result_type: SemstormResultType
  include_basic_stats: boolean
  competitors_type: SemstormCompetitorsType
}

export interface SemstormDiscoveryRunSummary {
  total_competitors: number
  total_queries: number
  unique_keywords: number
  created_at: string
}

export interface SemstormDiscoveryRunListItem {
  id: number
  site_id: number
  run_id: number
  status: 'running' | 'completed' | 'failed'
  stage: 'discovering' | 'completed' | 'failed'
  source_domain: string
  params: SemstormDiscoveryRunParams
  summary: SemstormDiscoveryRunSummary
  error_code: string | null
  error_message_safe: string | null
  started_at: string | null
  finished_at: string | null
  created_at: string
  updated_at: string
}

export interface SemstormDiscoveryRun extends SemstormDiscoveryRunListItem {
  competitors: SemstormCompetitorDiscovery[]
}

export interface SemstormMatchedPage {
  page_id: number
  url: string
  title: string | null
  match_signals: string[]
}

export interface SemstormGscSummary {
  clicks: number
  impressions: number
  ctr: number | null
  avg_position: number | null
}

export interface SemstormOpportunityItem {
  keyword: string
  competitor_count: number
  best_position: number | null
  max_traffic: number
  max_volume: number
  avg_cpc: number | null
  bucket: SemstormOpportunityBucket
  decision_type: SemstormDecisionType
  opportunity_score_v1: number
  opportunity_score_v2: number
  coverage_status: SemstormCoverageStatus
  coverage_score_v1: number
  matched_pages_count: number
  best_match_page: SemstormMatchedPage | null
  gsc_signal_status: SemstormGscSignalStatus
  gsc_summary: SemstormGscSummary | null
  state_status: SemstormOpportunityStateStatus
  state_note: string | null
  can_promote: boolean
  can_dismiss: boolean
  can_accept: boolean
  sample_competitors: string[]
}

export interface SemstormOpportunitiesSummary {
  total_items: number
  bucket_counts: Partial<Record<SemstormOpportunityBucket, number>>
  decision_type_counts: Partial<Record<SemstormDecisionType, number>>
  coverage_status_counts: Partial<Record<SemstormCoverageStatus, number>>
  state_counts: Partial<Record<SemstormOpportunityStateStatus, number>>
  total_competitors: number
  total_queries: number
  unique_keywords: number
  created_at: string
}

export interface SemstormOpportunitiesResponse {
  site_id: number
  run_id: number
  source_domain: string
  active_crawl_id: number | null
  summary: SemstormOpportunitiesSummary
  items: SemstormOpportunityItem[]
}

export interface SemstormOpportunitiesQueryParams {
  run_id?: number
  coverage_status?: SemstormCoverageStatus
  bucket?: SemstormOpportunityBucket
  decision_type?: SemstormDecisionType
  state_status?: SemstormOpportunityStateStatus
  has_gsc_signal?: boolean
  only_actionable?: boolean
  limit?: number
}

export interface SemstormOpportunityActionInput {
  run_id?: number
  keywords: string[]
  note?: string
}

export interface SemstormOpportunityActionSkippedItem {
  keyword: string
  reason: string
}

export interface SemstormPromotedItem {
  id: number
  site_id: number
  opportunity_key: string
  source_run_id: number
  keyword: string
  normalized_keyword: string
  bucket: SemstormOpportunityBucket
  decision_type: SemstormDecisionType
  opportunity_score_v2: number
  coverage_status: SemstormCoverageStatus
  best_match_page_url: string | null
  gsc_signal_status: SemstormGscSignalStatus
  promotion_status: SemstormPromotionStatus
  has_plan: boolean
  plan_id: number | null
  plan_state_status: SemstormPlanStateStatus | null
  created_at: string
  updated_at: string
}

export interface SemstormCreatePlanDefaultsInput {
  target_page_type?: SemstormPlanTargetPageType
}

export interface SemstormCreatePlanInput {
  promoted_item_ids: number[]
  defaults?: SemstormCreatePlanDefaultsInput
}

export interface SemstormCreatePlanSkippedItem {
  promoted_item_id: number
  keyword: string | null
  reason: string
}

export interface SemstormPlanItem {
  id: number
  site_id: number
  promoted_item_id: number
  keyword: string
  normalized_keyword: string
  source_run_id: number
  state_status: SemstormPlanStateStatus
  decision_type_snapshot: SemstormDecisionType
  bucket_snapshot: SemstormOpportunityBucket
  coverage_status_snapshot: SemstormCoverageStatus
  opportunity_score_v2_snapshot: number
  best_match_page_url_snapshot: string | null
  gsc_signal_status_snapshot: SemstormGscSignalStatus
  plan_title: string | null
  plan_note: string | null
  target_page_type: SemstormPlanTargetPageType
  proposed_slug: string | null
  proposed_primary_keyword: string | null
  proposed_secondary_keywords: string[]
  has_brief: boolean
  brief_id: number | null
  brief_state_status: SemstormBriefStateStatus | null
  created_at: string
  updated_at: string
}

export interface SemstormCreatePlanResponse {
  site_id: number
  requested_count: number
  created_count: number
  updated_count: number
  skipped_count: number
  items: SemstormPlanItem[]
  skipped: SemstormCreatePlanSkippedItem[]
}

export interface SemstormPlansSummary {
  total_count: number
  state_counts: Partial<Record<SemstormPlanStateStatus, number>>
  target_page_type_counts: Partial<Record<SemstormPlanTargetPageType, number>>
}

export interface SemstormPlansResponse {
  site_id: number
  summary: SemstormPlansSummary
  items: SemstormPlanItem[]
}

export interface SemstormPlansQueryParams {
  state_status?: SemstormPlanStateStatus
  target_page_type?: SemstormPlanTargetPageType
  search?: string
  limit?: number
}

export interface SemstormPlanStatusUpdateInput {
  state_status: SemstormPlanStateStatus
}

export interface SemstormPlanUpdateInput {
  state_status?: SemstormPlanStateStatus
  plan_title?: string | null
  plan_note?: string | null
  target_page_type?: SemstormPlanTargetPageType
  proposed_slug?: string | null
  proposed_primary_keyword?: string | null
  proposed_secondary_keywords?: string[]
}

export interface SemstormCreateBriefInput {
  plan_item_ids: number[]
}

export interface SemstormCreateBriefSkippedItem {
  plan_item_id: number
  brief_title: string | null
  reason: string
}

export interface SemstormBriefListItem {
  id: number
  site_id: number
  plan_item_id: number
  brief_title: string | null
  primary_keyword: string
  brief_type: SemstormBriefType
  search_intent: SemstormBriefSearchIntent
  state_status: SemstormBriefStateStatus
  execution_status: SemstormBriefStateStatus
  assignee: string | null
  execution_note: string | null
  ready_at: string | null
  started_at: string | null
  completed_at: string | null
  archived_at: string | null
  implementation_status: SemstormImplementationStatus | null
  implemented_at: string | null
  last_outcome_checked_at: string | null
  recommended_page_title: string | null
  proposed_url_slug: string | null
  decision_type_snapshot: SemstormDecisionType | null
  bucket_snapshot: SemstormOpportunityBucket | null
  coverage_status_snapshot: SemstormCoverageStatus | null
  gsc_signal_status_snapshot: SemstormGscSignalStatus | null
  opportunity_score_v2_snapshot: number
  created_at: string
  updated_at: string
}

export interface SemstormBriefItem extends SemstormBriefListItem {
  secondary_keywords: string[]
  target_url_existing: string | null
  implementation_url_override: string | null
  evaluation_note: string | null
  recommended_h1: string | null
  content_goal: string | null
  angle_summary: string | null
  sections: string[]
  internal_link_targets: string[]
  source_notes: string[]
}

export interface SemstormCreateBriefResponse {
  site_id: number
  requested_count: number
  created_count: number
  updated_count: number
  skipped_count: number
  items: SemstormBriefItem[]
  skipped: SemstormCreateBriefSkippedItem[]
}

export interface SemstormBriefsSummary {
  total_count: number
  state_counts: Partial<Record<SemstormBriefStateStatus, number>>
  brief_type_counts: Partial<Record<SemstormBriefType, number>>
  intent_counts: Partial<Record<SemstormBriefSearchIntent, number>>
}

export interface SemstormBriefsResponse {
  site_id: number
  summary: SemstormBriefsSummary
  items: SemstormBriefListItem[]
}

export interface SemstormBriefsQueryParams {
  state_status?: SemstormBriefStateStatus
  brief_type?: SemstormBriefType
  search_intent?: SemstormBriefSearchIntent
  search?: string
  limit?: number
}

export interface SemstormBriefStatusUpdateInput {
  state_status: SemstormBriefStateStatus
}

export interface SemstormBriefExecutionStatusUpdateInput {
  execution_status: SemstormBriefStateStatus
}

export interface SemstormBriefUpdateInput {
  state_status?: SemstormBriefStateStatus
  brief_title?: string | null
  brief_type?: SemstormBriefType
  primary_keyword?: string | null
  secondary_keywords?: string[]
  search_intent?: SemstormBriefSearchIntent
  target_url_existing?: string | null
  proposed_url_slug?: string | null
  recommended_page_title?: string | null
  recommended_h1?: string | null
  content_goal?: string | null
  angle_summary?: string | null
  sections?: string[]
  internal_link_targets?: string[]
  source_notes?: string[]
}

export interface SemstormBriefExecutionUpdateInput {
  assignee?: string | null
  execution_note?: string | null
}

export interface SemstormBriefImplementationStatusUpdateInput {
  implementation_status: 'implemented' | 'archived'
  evaluation_note?: string | null
  implementation_url_override?: string | null
}

export interface SemstormExecutionItem {
  brief_id: number
  plan_item_id: number
  brief_title: string | null
  primary_keyword: string
  brief_type: SemstormBriefType
  search_intent: SemstormBriefSearchIntent
  execution_status: SemstormBriefStateStatus
  assignee: string | null
  execution_note: string | null
  implementation_status: SemstormImplementationStatus | null
  implemented_at: string | null
  recommended_page_title: string | null
  proposed_url_slug: string | null
  ready_at: string | null
  started_at: string | null
  completed_at: string | null
  archived_at: string | null
  decision_type_snapshot: SemstormDecisionType | null
  bucket_snapshot: SemstormOpportunityBucket | null
  coverage_status_snapshot: SemstormCoverageStatus | null
  gsc_signal_status_snapshot: SemstormGscSignalStatus | null
  opportunity_score_v2_snapshot: number
  updated_at: string
}

export interface SemstormExecutionSummary {
  total_count: number
  execution_status_counts: Partial<Record<SemstormBriefStateStatus, number>>
  ready_count: number
  in_execution_count: number
  completed_count: number
}

export interface SemstormExecutionResponse {
  site_id: number
  summary: SemstormExecutionSummary
  items: SemstormExecutionItem[]
}

export interface SemstormExecutionQueryParams {
  execution_status?: SemstormBriefStateStatus
  assignee?: string
  brief_type?: SemstormBriefType
  search?: string
  limit?: number
}

export interface SemstormImplementedItem {
  brief_id: number
  plan_item_id: number
  brief_title: string | null
  primary_keyword: string
  brief_type: SemstormBriefType
  execution_status: SemstormBriefStateStatus
  implementation_status: SemstormImplementationStatus
  implemented_at: string | null
  evaluation_note: string | null
  implementation_url_override: string | null
  outcome_status: SemstormOutcomeStatus
  page_present_in_active_crawl: boolean
  matched_page: SemstormMatchedPage | null
  gsc_signal_status: SemstormGscSignalStatus
  gsc_summary: SemstormGscSummary | null
  query_match_count: number
  notes: string[]
  decision_type_snapshot: SemstormDecisionType | null
  coverage_status_snapshot: SemstormCoverageStatus | null
  opportunity_score_v2_snapshot: number
  updated_at: string
  last_outcome_checked_at: string | null
}

export interface SemstormImplementedSummary {
  total_count: number
  implementation_status_counts: Partial<Record<SemstormImplementationStatus, number>>
  outcome_status_counts: Partial<Record<SemstormOutcomeStatus, number>>
  too_early_count: number
  positive_signal_count: number
}

export interface SemstormImplementedResponse {
  site_id: number
  active_crawl_id: number | null
  window_days: number
  summary: SemstormImplementedSummary
  items: SemstormImplementedItem[]
}

export interface SemstormImplementedQueryParams {
  implementation_status?: SemstormImplementationStatus
  outcome_status?: SemstormOutcomeStatus
  brief_type?: SemstormBriefType
  search?: string
  window_days?: number
  limit?: number
}

export interface SemstormBriefEnrichmentSuggestions {
  improved_brief_title: string | null
  improved_page_title: string | null
  improved_h1: string | null
  improved_angle_summary: string | null
  improved_sections: string[]
  improved_internal_link_targets: string[]
  editorial_notes: string[]
  risk_flags: string[]
}

export interface SemstormBriefEnrichmentRun {
  id: number
  site_id: number
  brief_item_id: number
  status: SemstormBriefEnrichmentStatus
  engine_mode: SemstormBriefEnrichmentEngineMode
  model_name: string | null
  input_hash: string
  suggestions: SemstormBriefEnrichmentSuggestions
  error_code: string | null
  error_message_safe: string | null
  is_applied: boolean
  applied_at: string | null
  created_at: string
  updated_at: string
}

export interface SemstormBriefEnrichmentRunsSummary {
  total_count: number
  completed_count: number
  failed_count: number
  applied_count: number
}

export interface SemstormBriefEnrichmentRunsResponse {
  site_id: number
  brief_id: number
  summary: SemstormBriefEnrichmentRunsSummary
  items: SemstormBriefEnrichmentRun[]
}

export interface SemstormBriefEnrichmentApplyResponse {
  site_id: number
  brief_id: number
  run_id: number
  applied: boolean
  skipped_reason: string | null
  applied_fields: string[]
  brief: SemstormBriefItem
  enrichment_run: SemstormBriefEnrichmentRun
}

export interface SemstormOpportunityActionResponse {
  action: 'accept' | 'dismiss' | 'promote'
  site_id: number
  run_id: number
  note: string | null
  requested_count: number
  updated_count: number
  promoted_count: number
  state_status: Exclude<SemstormOpportunityStateStatus, 'new'>
  updated_keywords: string[]
  promoted_items: SemstormPromotedItem[]
  skipped_count: number
  skipped: SemstormOpportunityActionSkippedItem[]
}

export interface SemstormPromotedItemsSummary {
  total_items: number
  promotion_status_counts: Partial<Record<SemstormPromotionStatus, number>>
}

export interface SemstormPromotedItemsResponse {
  site_id: number
  summary: SemstormPromotedItemsSummary
  items: SemstormPromotedItem[]
}

export interface SiteCompareCrawlContext {
  id: number
  status: JobStatus
  created_at: string
  started_at: string | null
  finished_at: string | null
  root_url: string | null
}

export interface SiteCompareContext {
  site_id: number
  site_domain: string
  active_crawl_id: number | null
  baseline_crawl_id: number | null
  compare_available: boolean
  compare_unavailable_reason: string | null
  active_crawl: SiteCompareCrawlContext | null
  baseline_crawl: SiteCompareCrawlContext | null
}

export interface SiteCrawlCreateInput {
  root_url?: string
  max_urls: number
  max_depth: number
  delay: number
  render_mode: RenderMode
  render_timeout_ms: number
  max_rendered_pages_per_job: number
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
  title_length: number | null
  meta_description: string | null
  meta_description_length: number | null
  h1: string | null
  h1_length: number | null
  h1_count: number | null
  h2_count: number | null
  canonical_url: string | null
  canonical_target_url: string | null
  canonical_target_status_code: number | null
  robots_meta: string | null
  x_robots_tag: string | null
  content_type: string | null
  word_count: number | null
  content_text_hash: string | null
  images_count: number | null
  images_missing_alt_count: number | null
  html_size_bytes: number | null
  was_rendered: boolean
  render_attempted: boolean
  fetch_mode_used: string | null
  js_heavy_like: boolean
  render_reason: string | null
  render_error_message: string | null
  schema_present: boolean
  schema_count: number | null
  schema_types_json: string[] | null
  schema_types_text: string
  page_type: PageType
  page_bucket: PageBucket
  page_type_confidence: number
  page_type_version: string
  page_type_rationale: string | null
  has_render_error: boolean
  has_x_robots_tag: boolean
  response_time_ms: number | null
  is_internal: boolean
  depth: number
  fetched_at: string | null
  error_message: string | null
  title_missing: boolean
  meta_description_missing: boolean
  h1_missing: boolean
  title_too_short: boolean
  title_too_long: boolean
  meta_description_too_short: boolean
  meta_description_too_long: boolean
  multiple_h1: boolean
  missing_h2: boolean
  canonical_missing: boolean
  self_canonical: boolean
  canonical_to_other_url: boolean
  canonical_to_non_200: boolean
  canonical_to_redirect: boolean
  noindex_like: boolean
  non_indexable_like: boolean
  thin_content: boolean
  duplicate_title: boolean
  duplicate_meta_description: boolean
  duplicate_content: boolean
  missing_alt_images: boolean
  no_images: boolean
  oversized: boolean
  clicks_28d: number | null
  impressions_28d: number | null
  ctr_28d: number | null
  position_28d: number | null
  gsc_fetched_at_28d: string | null
  top_queries_count_28d: number
  has_gsc_28d: boolean
  clicks_90d: number | null
  impressions_90d: number | null
  ctr_90d: number | null
  position_90d: number | null
  gsc_fetched_at_90d: string | null
  top_queries_count_90d: number
  has_gsc_90d: boolean
  has_technical_issue: boolean
  technical_issue_count: number
  incoming_internal_links: number
  incoming_internal_linking_pages: number
  priority_score: number
  priority_level: PriorityLevel
  priority_rationale: string
  traffic_component: number
  issue_component: number
  opportunity_component: number
  internal_linking_component: number
  opportunity_count: number
  primary_opportunity_type: OpportunityType | null
  opportunity_types: OpportunityType[]
  has_cannibalization: boolean
  cannibalization_cluster_id: string | null
  cannibalization_severity: CannibalizationSeverity | null
  cannibalization_impact_level: ImpactLevel | null
  cannibalization_recommendation_type: CannibalizationRecommendationType | null
  cannibalization_rationale: string | null
  cannibalization_competing_urls_count: number
  cannibalization_strongest_competing_url: string | null
  cannibalization_strongest_competing_page_id: number | null
  cannibalization_dominant_competing_url: string | null
  cannibalization_dominant_competing_page_id: number | null
  cannibalization_common_queries_count: number
  cannibalization_weighted_overlap_by_impressions: number
  cannibalization_weighted_overlap_by_clicks: number
  cannibalization_overlap_ratio: number
  cannibalization_overlap_strength: number
  cannibalization_shared_top_queries: string[]
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
  target_status_code?: number | null
  final_url?: string | null
  redirect_hops?: number | null
  target_canonical_url?: string | null
  target_noindex_like?: boolean
  target_non_indexable_like?: boolean
  target_canonicalized?: boolean
  broken_internal?: boolean
  redirecting_internal?: boolean
  unresolved_internal?: boolean
  to_noindex_like?: boolean
  to_canonicalized?: boolean
  redirect_chain?: boolean
  created_at: string
}

export interface PagesQueryParams {
  page: number
  page_size: number
  sort_by: PagesSortBy
  sort_order: SortOrder
  gsc_date_range: GscDateRangeLabel
  url_contains?: string
  title_contains?: string
  page_type?: PageType
  page_bucket?: PageBucket
  page_type_confidence_min?: number
  page_type_confidence_max?: number
  has_title?: boolean
  has_meta_description?: boolean
  has_h1?: boolean
  status_code?: number
  status_code_min?: number
  status_code_max?: number
  canonical_missing?: boolean
  robots_meta_contains?: string
  noindex_like?: boolean
  non_indexable_like?: boolean
  title_exact?: string
  meta_description_exact?: string
  content_text_hash_exact?: string
  title_too_short?: boolean
  title_too_long?: boolean
  meta_too_short?: boolean
  meta_too_long?: boolean
  multiple_h1?: boolean
  missing_h2?: boolean
  self_canonical?: boolean
  canonical_to_other_url?: boolean
  canonical_to_non_200?: boolean
  canonical_to_redirect?: boolean
  thin_content?: boolean
  duplicate_content?: boolean
  missing_alt_images?: boolean
  no_images?: boolean
  oversized?: boolean
  was_rendered?: boolean
  js_heavy_like?: boolean
  schema_present?: boolean
  schema_type?: string
  has_render_error?: boolean
  has_x_robots_tag?: boolean
  has_technical_issue?: boolean
  has_gsc_data?: boolean
  has_cannibalization?: boolean
  priority_level?: PriorityLevel
  opportunity_type?: OpportunityType
  priority_score_min?: number
  priority_score_max?: number
  gsc_clicks_min?: number
  gsc_clicks_max?: number
  gsc_impressions_min?: number
  gsc_impressions_max?: number
  gsc_ctr_min?: number
  gsc_ctr_max?: number
  gsc_position_min?: number
  gsc_position_max?: number
  gsc_top_queries_min?: number
}

export interface PaginatedPagesResponse extends PaginatedResponse<PageRecord> {
  available_status_codes?: number[]
  has_gsc_integration?: boolean
}

export interface PageTaxonomySummary {
  crawl_job_id: number
  page_type_version: string
  total_pages: number
  classified_pages: number
  counts_by_page_type: Record<PageType, number>
  counts_by_page_bucket: Record<PageBucket, number>
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
  broken_internal?: boolean
  redirecting_internal?: boolean
  unresolved_internal?: boolean
  to_noindex_like?: boolean
  to_canonicalized?: boolean
  redirect_chain?: boolean
}

export interface PageIssue {
  page_id: number
  url: string
  normalized_url: string
  final_url?: string | null
  status_code: number | null
  title?: string | null
  title_length?: number | null
  meta_description?: string | null
  meta_description_length?: number | null
  h1?: string | null
  h1_count?: number | null
  h2_count?: number | null
  canonical_url?: string | null
  canonical_target_url?: string | null
  canonical_target_status_code?: number | null
  canonical_target_final_url?: string | null
  robots_meta?: string | null
  x_robots_tag?: string | null
  word_count?: number | null
  content_text_hash?: string | null
  images_count?: number | null
  images_missing_alt_count?: number | null
  html_size_bytes?: number | null
  was_rendered?: boolean
  js_heavy_like?: boolean
  render_reason?: string | null
  render_error_message?: string | null
  schema_present?: boolean
  schema_count?: number | null
  schema_types_json?: string[]
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
  redirect_hops?: number | null
  target_canonical_url?: string | null
  target_noindex_like?: boolean
  target_non_indexable_like?: boolean
  signals: string[]
}

export interface AuditSummary {
  total_pages: number
  pages_missing_title: number
  pages_title_too_short: number
  pages_title_too_long: number
  pages_missing_meta_description: number
  pages_meta_description_too_short: number
  pages_meta_description_too_long: number
  pages_missing_h1: number
  pages_multiple_h1: number
  pages_missing_h2: number
  pages_missing_canonical: number
  pages_self_canonical: number
  pages_canonical_to_other_url: number
  pages_canonical_to_non_200: number
  pages_canonical_to_redirect: number
  pages_noindex_like: number
  pages_non_indexable_like: number
  pages_duplicate_title_groups: number
  pages_duplicate_meta_description_groups: number
  pages_thin_content: number
  pages_duplicate_content_groups: number
  pages_with_missing_alt_images: number
  pages_with_no_images: number
  oversized_pages: number
  js_heavy_like_pages: number
  rendered_pages: number
  pages_with_render_errors: number
  pages_with_schema: number
  pages_missing_schema: number
  pages_with_x_robots_tag: number
  pages_with_schema_types_summary: number
  broken_internal_links: number
  unresolved_internal_targets: number
  redirecting_internal_links: number
  internal_links_to_noindex_like_pages: number
  internal_links_to_canonicalized_pages: number
  redirect_chains_internal: number
}

export interface AuditReport {
  crawl_job_id: number
  summary: AuditSummary
  pages_missing_title: PageIssue[]
  pages_title_too_short: PageIssue[]
  pages_title_too_long: PageIssue[]
  pages_missing_meta_description: PageIssue[]
  pages_meta_description_too_short: PageIssue[]
  pages_meta_description_too_long: PageIssue[]
  pages_missing_h1: PageIssue[]
  pages_multiple_h1: PageIssue[]
  pages_missing_h2: PageIssue[]
  pages_missing_canonical: PageIssue[]
  pages_self_canonical: PageIssue[]
  pages_canonical_to_other_url: PageIssue[]
  pages_canonical_to_non_200: PageIssue[]
  pages_canonical_to_redirect: PageIssue[]
  pages_noindex_like: PageIssue[]
  pages_non_indexable_like: PageIssue[]
  pages_duplicate_title: DuplicateValueGroup[]
  pages_duplicate_meta_description: DuplicateValueGroup[]
  pages_thin_content: PageIssue[]
  pages_duplicate_content: DuplicateValueGroup[]
  pages_with_missing_alt_images: PageIssue[]
  pages_with_no_images: PageIssue[]
  oversized_pages: PageIssue[]
  js_heavy_like_pages: PageIssue[]
  rendered_pages: PageIssue[]
  pages_with_render_errors: PageIssue[]
  pages_with_schema: PageIssue[]
  pages_missing_schema: PageIssue[]
  pages_with_x_robots_tag: PageIssue[]
  pages_with_schema_types_summary: DuplicateValueGroup[]
  broken_internal_links: LinkIssue[]
  unresolved_internal_targets: LinkIssue[]
  redirecting_internal_links: LinkIssue[]
  internal_links_to_noindex_like_pages: LinkIssue[]
  internal_links_to_canonicalized_pages: LinkIssue[]
  redirect_chains_internal: LinkIssue[]
}

export interface GscPropertyOption {
  property_uri: string
  permission_level: string | null
  matches_site: boolean
  is_selected: boolean
}

export interface GscImportRangeSummary {
  date_range_label: GscDateRangeLabel
  imported_url_metrics: number
  imported_top_queries: number
  pages_with_top_queries: number
  failed_pages: number
  errors: string[]
}

export interface GscImportResponse {
  crawl_job_id: number
  property_uri: string
  imported_at: string
  ranges: GscImportRangeSummary[]
}

export interface GscRangeCoverage {
  date_range_label: GscDateRangeLabel
  imported_pages: number
  pages_with_impressions: number
  pages_with_clicks: number
  pages_with_top_queries: number
  total_top_queries: number
  opportunities_with_impressions: number
  opportunities_with_clicks: number
  last_imported_at: string | null
}

export interface GscSummary {
  crawl_job_id: number
  site_id: number
  auth_connected: boolean
  selected_property_uri: string | null
  selected_property_permission_level: string | null
  available_date_ranges: GscDateRangeLabel[]
  ranges: GscRangeCoverage[]
}

export interface GscActiveCrawlContext {
  id: number
  site_id: number
  status: JobStatus
  root_url: string | null
  created_at: string
  started_at: string | null
  finished_at: string | null
}

export interface SiteGscSummary {
  site_id: number
  site_domain: string
  site_root_url: string
  auth_connected: boolean
  selected_property_uri: string | null
  selected_property_permission_level: string | null
  available_date_ranges: GscDateRangeLabel[]
  active_crawl_id: number | null
  active_crawl_has_gsc_data: boolean
  active_crawl: GscActiveCrawlContext | null
  ranges: GscRangeCoverage[]
}

export interface GscTopQueryRecord {
  id: number
  page_id: number | null
  url: string
  date_range_label: GscDateRangeLabel
  query: string
  clicks: number
  impressions: number
  ctr: number | null
  position: number | null
  fetched_at: string
}

export interface OpportunityAssignment {
  type: OpportunityType
  opportunity_score: number
  impact_level: ImpactLevel
  effort_level: EffortLevel
  rationale: string
}

export interface OpportunityPagePreview {
  page_id: number
  url: string
  priority_score: number
  priority_level: PriorityLevel
  priority_rationale: string
  primary_opportunity_type: OpportunityType | null
  opportunity_count: number
  opportunity_types: OpportunityType[]
  clicks: number
  impressions: number
  ctr: number
  position: number | null
  incoming_internal_links: number
  incoming_internal_linking_pages: number
  opportunities: OpportunityAssignment[]
  opportunity_score: number | null
  impact_level: ImpactLevel | null
  effort_level: EffortLevel | null
  rationale: string
}

export interface OpportunityGroup {
  type: OpportunityType
  count: number
  top_priority_score: number
  top_opportunity_score: number
  top_pages: OpportunityPagePreview[]
}

export interface OpportunitiesSummary {
  crawl_job_id: number
  gsc_date_range: GscDateRangeLabel
  total_pages: number
  pages_with_opportunities: number
  high_priority_pages: number
  critical_priority_pages: number
  groups: OpportunityGroup[]
  top_priority_pages: OpportunityPagePreview[]
}

export interface AnchorSample {
  anchor_text: string
  links: number
  linking_pages: number
  exact_match: boolean
  boilerplate_likely: boolean
}

export interface InternalLinkingOverview {
  crawl_job_id: number
  gsc_date_range: GscDateRangeLabel
  total_internal_pages: number
  issue_pages: number
  orphan_like_pages: number
  weakly_linked_important_pages: number
  low_anchor_diversity_pages: number
  exact_match_anchor_concentration_pages: number
  boilerplate_dominated_pages: number
  low_link_equity_pages: number
  median_link_equity_score: number
  average_anchor_diversity_score: number
  average_body_like_share: number
}

export interface InternalLinkingIssueRow {
  page_id: number
  url: string
  normalized_url: string
  priority_score: number
  priority_level: PriorityLevel
  priority_rationale: string
  primary_opportunity_type: OpportunityType | null
  opportunity_types: OpportunityType[]
  technical_issue_count: number
  clicks: number
  impressions: number
  ctr: number
  position: number | null
  incoming_internal_links: number
  incoming_internal_linking_pages: number
  incoming_follow_links: number
  incoming_follow_linking_pages: number
  incoming_nofollow_links: number
  body_like_links: number
  body_like_linking_pages: number
  boilerplate_like_links: number
  boilerplate_like_linking_pages: number
  body_like_share: number
  boilerplate_like_share: number
  unique_anchor_count: number
  anchor_diversity_score: number
  exact_match_anchor_count: number
  exact_match_anchor_ratio: number
  link_equity_score: number
  link_equity_rank: number
  internal_linking_score: number
  issue_count: number
  orphan_like: boolean
  weakly_linked_important: boolean
  low_anchor_diversity: boolean
  exact_match_anchor_concentration: boolean
  boilerplate_dominated: boolean
  low_link_equity: boolean
  issue_types: InternalLinkingIssueType[]
  primary_issue_type: InternalLinkingIssueType
  top_anchor_samples: AnchorSample[]
  rationale: string
}

export interface InternalLinkingIssuesQueryParams {
  gsc_date_range: GscDateRangeLabel
  page: number
  page_size: number
  sort_by:
    | 'url'
    | 'internal_linking_score'
    | 'priority_score'
    | 'link_equity_score'
    | 'link_equity_rank'
    | 'incoming_follow_links'
    | 'incoming_follow_linking_pages'
    | 'body_like_share'
    | 'boilerplate_like_share'
    | 'anchor_diversity_score'
    | 'exact_match_anchor_ratio'
    | 'issue_count'
  sort_order: SortOrder
  issue_type?: InternalLinkingIssueType
  priority_level?: PriorityLevel
  opportunity_type?: OpportunityType
  url_contains?: string
}

export interface PaginatedInternalLinkingIssuesResponse extends PaginatedResponse<InternalLinkingIssueRow> {
  crawl_job_id: number
  gsc_date_range: GscDateRangeLabel
}

export interface CannibalizationClusterCandidateUrl {
  page_id: number
  url: string
  priority_score: number
  priority_level: PriorityLevel
  primary_opportunity_type: OpportunityType | null
  clicks: number
  impressions: number
  position: number | null
  query_count: number
  shared_query_count: number
  exclusive_query_count: number
  click_share: number
  impression_share: number
  avg_shared_position: number | null
  strongest_competing_url: string | null
  is_dominant: boolean
}

export interface CannibalizationCluster {
  cluster_id: string
  urls_count: number
  shared_queries_count: number
  shared_query_impressions: number
  shared_query_clicks: number
  weighted_overlap: number
  severity: CannibalizationSeverity
  impact_level: ImpactLevel
  recommendation_type: CannibalizationRecommendationType
  has_clear_primary: boolean
  dominant_url: string | null
  dominant_url_page_id: number | null
  dominant_url_confidence: number
  dominant_url_score: number
  sample_queries: string[]
  candidate_urls: CannibalizationClusterCandidateUrl[]
  rationale: string
}

export interface CannibalizationSummary {
  crawl_job_id: number
  gsc_date_range: GscDateRangeLabel
  total_candidate_pages: number
  pages_in_conflicts: number
  clusters_count: number
  critical_clusters: number
  high_severity_clusters: number
  high_impact_clusters: number
  no_clear_primary_clusters: number
  merge_candidates: number
  split_intent_candidates: number
  reinforce_primary_candidates: number
  low_value_overlap_clusters: number
  average_weighted_overlap: number
}

export interface CannibalizationClustersQueryParams {
  gsc_date_range: GscDateRangeLabel
  page: number
  page_size: number
  sort_by:
    | 'severity'
    | 'impact_level'
    | 'weighted_overlap'
    | 'shared_queries_count'
    | 'shared_query_impressions'
    | 'shared_query_clicks'
    | 'urls_count'
    | 'dominant_url_confidence'
    | 'recommendation_type'
    | 'cluster_id'
  sort_order: SortOrder
  severity?: CannibalizationSeverity
  impact_level?: ImpactLevel
  recommendation_type?: CannibalizationRecommendationType
  has_clear_primary?: boolean
  url_contains?: string
}

export interface PaginatedCannibalizationClustersResponse {
  summary: CannibalizationSummary
  items: CannibalizationCluster[]
  page: number
  page_size: number
  total_items: number
  total_pages: number
}

export interface CannibalizationOverlapRow {
  competing_page_id: number
  competing_url: string
  common_queries_count: number
  weighted_overlap_by_impressions: number
  weighted_overlap_by_clicks: number
  overlap_ratio: number
  pair_overlap_score: number
  shared_query_impressions: number
  shared_query_clicks: number
  shared_top_queries: string[]
  dominant_url: string | null
  dominance_score: number
  dominance_confidence: number
  competitor_priority_score: number
  competitor_priority_level: PriorityLevel
  competitor_primary_opportunity_type: OpportunityType | null
  competitor_clicks: number
  competitor_impressions: number
  competitor_position: number | null
}

export interface CannibalizationPageDetails {
  crawl_job_id: number
  gsc_date_range: GscDateRangeLabel
  page_id: number
  url: string
  normalized_url: string
  has_cannibalization: boolean
  cluster_id: string | null
  severity: CannibalizationSeverity | null
  impact_level: ImpactLevel | null
  recommendation_type: CannibalizationRecommendationType | null
  rationale: string | null
  competing_urls_count: number
  strongest_competing_url: string | null
  strongest_competing_page_id: number | null
  common_queries_count: number
  weighted_overlap_by_impressions: number
  weighted_overlap_by_clicks: number
  overlap_ratio: number
  overlap_strength: number
  shared_top_queries: string[]
  dominant_competing_url: string | null
  dominant_competing_page_id: number | null
  overlaps: CannibalizationOverlapRow[]
}

export interface GscTopQueriesPageContext {
  id: number
  url: string
  normalized_url: string
  title?: string | null
  clicks_28d: number | null
  impressions_28d: number | null
  ctr_28d: number | null
  position_28d: number | null
  clicks_90d: number | null
  impressions_90d: number | null
  ctr_90d: number | null
  position_90d: number | null
  has_technical_issue: boolean
  technical_issue_count: number
  top_queries_count_28d: number
  top_queries_count_90d: number
}

export interface PaginatedGscTopQueriesResponse extends PaginatedResponse<GscTopQueryRecord> {
  page_context: GscTopQueriesPageContext | null
}

export interface TrendJobOption {
  id: number
  status: JobStatus
  created_at: string
  started_at: string | null
  finished_at: string | null
  root_url: string | null
}

export interface TrendsOverview {
  crawl_job_id: number
  site_id: number
  site_domain: string
  default_baseline_job_id: number | null
  baseline_candidates: TrendJobOption[]
  available_gsc_ranges: GscDateRangeLabel[]
}

export interface CrawlCompareSummary {
  baseline_job_id: number
  target_job_id: number
  gsc_date_range: GscDateRangeLabel
  shared_urls: number
  new_urls: number
  missing_urls: number
  improved_urls: number
  worsened_urls: number
  unchanged_urls: number
  resolved_issues_total: number
  added_issues_total: number
}

export interface CrawlCompareRow {
  url: string
  normalized_url: string
  baseline_page_id: number | null
  target_page_id: number | null
  new_in_target: boolean
  missing_in_target: boolean
  present_in_both: boolean
  change_type: CrawlCompareChangeType
  issues_resolved_count: number
  issues_added_count: number
  resolved_issues: string[]
  added_issues: string[]
  changed_fields: string[]
  change_rationale: string
  baseline_status_code: number | null
  target_status_code: number | null
  status_code_changed: boolean
  baseline_title: string | null
  target_title: string | null
  title_changed: boolean
  baseline_meta_description: string | null
  target_meta_description: string | null
  meta_description_changed: boolean
  baseline_h1: string | null
  target_h1: string | null
  h1_changed: boolean
  baseline_canonical_url: string | null
  target_canonical_url: string | null
  canonical_url_changed: boolean
  baseline_noindex_like: boolean | null
  target_noindex_like: boolean | null
  noindex_like_changed: boolean
  baseline_non_indexable_like: boolean | null
  target_non_indexable_like: boolean | null
  baseline_title_length: number | null
  target_title_length: number | null
  baseline_meta_description_length: number | null
  target_meta_description_length: number | null
  baseline_h1_count: number | null
  target_h1_count: number | null
  baseline_word_count: number | null
  target_word_count: number | null
  baseline_images_missing_alt_count: number | null
  target_images_missing_alt_count: number | null
  baseline_schema_count: number | null
  target_schema_count: number | null
  baseline_html_size_bytes: number | null
  target_html_size_bytes: number | null
  baseline_was_rendered: boolean | null
  target_was_rendered: boolean | null
  baseline_js_heavy_like: boolean | null
  target_js_heavy_like: boolean | null
  baseline_response_time_ms: number | null
  target_response_time_ms: number | null
  baseline_incoming_internal_links: number | null
  target_incoming_internal_links: number | null
  baseline_incoming_internal_linking_pages: number | null
  target_incoming_internal_linking_pages: number | null
  baseline_priority_score: number | null
  target_priority_score: number | null
  baseline_priority_level: PriorityLevel | null
  target_priority_level: PriorityLevel | null
  baseline_opportunity_count: number | null
  target_opportunity_count: number | null
  baseline_primary_opportunity_type: OpportunityType | null
  target_primary_opportunity_type: OpportunityType | null
  baseline_opportunity_types: OpportunityType[]
  target_opportunity_types: OpportunityType[]
  delta_priority_score: number | null
  delta_word_count: number | null
  delta_schema_count: number | null
  delta_response_time_ms: number | null
  delta_incoming_internal_links: number | null
  delta_incoming_internal_linking_pages: number | null
}

export interface PaginatedCrawlCompareResponse extends PaginatedResponse<CrawlCompareRow> {
  baseline_job: TrendJobOption
  target_job: TrendJobOption
  summary: CrawlCompareSummary
}

export interface SitePagesCompareSummary {
  active_urls: number
  baseline_urls: number
  shared_urls: number
  new_urls: number
  missing_urls: number
  changed_urls: number
  improved_urls: number
  worsened_urls: number
  unchanged_urls: number
  status_changed_urls: number
  title_changed_urls: number
  meta_description_changed_urls: number
  h1_changed_urls: number
  canonical_changed_urls: number
  noindex_changed_urls: number
  priority_improved_urls: number
  priority_worsened_urls: number
  internal_linking_improved_urls: number
  internal_linking_worsened_urls: number
  content_growth_urls: number
  content_drop_urls: number
}

export interface SitePagesCompareRow {
  url: string
  normalized_url: string
  active_page_id: number | null
  baseline_page_id: number | null
  change_type: CrawlCompareChangeType
  changed_fields: string[]
  change_rationale: string
  active_status_code: number | null
  baseline_status_code: number | null
  status_code_changed: boolean
  active_title: string | null
  baseline_title: string | null
  title_changed: boolean
  active_meta_description: string | null
  baseline_meta_description: string | null
  meta_description_changed: boolean
  active_h1: string | null
  baseline_h1: string | null
  h1_changed: boolean
  active_canonical_url: string | null
  baseline_canonical_url: string | null
  canonical_changed: boolean
  active_noindex_like: boolean | null
  baseline_noindex_like: boolean | null
  noindex_changed: boolean
  active_word_count: number | null
  baseline_word_count: number | null
  delta_word_count: number | null
  word_count_trend: CompareDeltaTrend | null
  active_response_time_ms: number | null
  baseline_response_time_ms: number | null
  delta_response_time_ms: number | null
  response_time_trend: CompareDeltaTrend | null
  active_incoming_internal_links: number | null
  baseline_incoming_internal_links: number | null
  delta_incoming_internal_links: number | null
  active_incoming_internal_linking_pages: number | null
  baseline_incoming_internal_linking_pages: number | null
  delta_incoming_internal_linking_pages: number | null
  internal_linking_trend: CompareDeltaTrend | null
  active_priority_score: number | null
  baseline_priority_score: number | null
  delta_priority_score: number | null
  priority_trend: CompareDeltaTrend | null
  active_priority_level: PriorityLevel | null
  baseline_priority_level: PriorityLevel | null
  active_primary_opportunity_type: OpportunityType | null
}

export interface PaginatedSitePagesCompareResponse extends PaginatedResponse<SitePagesCompareRow> {
  context: SiteCompareContext
  gsc_date_range: GscDateRangeLabel
  summary: SitePagesCompareSummary
}

export interface AuditCompareSummary {
  total_sections: number
  resolved_sections: number
  new_sections: number
  improved_sections: number
  worsened_sections: number
  unchanged_sections: number
  resolved_issues_total: number
  new_issues_total: number
  active_issues_total: number
  baseline_issues_total: number
}

export interface AuditCompareSection {
  key: string
  area: 'pages' | 'links' | 'duplicates'
  active_count: number
  baseline_count: number
  delta: number
  status: AuditCompareSectionStatus
  resolved_items_count: number
  new_items_count: number
  sample_resolved_items: string[]
  sample_new_items: string[]
}

export interface SiteAuditCompare {
  context: SiteCompareContext
  summary: AuditCompareSummary
  sections: AuditCompareSection[]
}

export interface SiteOpportunitiesCompareSummary {
  total_urls: number
  active_urls_with_opportunities: number
  active_actionable_urls: number
  new_opportunity_urls: number
  resolved_opportunity_urls: number
  priority_up_urls: number
  priority_down_urls: number
  entered_actionable_urls: number
  left_actionable_urls: number
}

export interface SiteOpportunitiesCompareRow {
  url: string
  normalized_url: string
  active_page_id: number | null
  baseline_page_id: number | null
  change_type: CrawlCompareChangeType
  highlights: OpportunityCompareHighlight[]
  active_priority_score: number | null
  baseline_priority_score: number | null
  delta_priority_score: number | null
  active_priority_level: PriorityLevel | null
  baseline_priority_level: PriorityLevel | null
  active_opportunity_count: number
  baseline_opportunity_count: number
  active_primary_opportunity_type: OpportunityType | null
  baseline_primary_opportunity_type: OpportunityType | null
  active_opportunity_types: OpportunityType[]
  baseline_opportunity_types: OpportunityType[]
  new_opportunity_types: OpportunityType[]
  resolved_opportunity_types: OpportunityType[]
  entered_actionable: boolean
  left_actionable: boolean
  change_rationale: string
}

export interface PaginatedSiteOpportunitiesCompareResponse extends PaginatedResponse<SiteOpportunitiesCompareRow> {
  context: SiteCompareContext
  gsc_date_range: GscDateRangeLabel
  actionable_priority_score_threshold: number
  summary: SiteOpportunitiesCompareSummary
}

export interface SiteInternalLinkingCompareSummary {
  total_urls: number
  issue_urls_in_active: number
  new_orphan_like_urls: number
  resolved_orphan_like_urls: number
  weakly_linked_improved_urls: number
  weakly_linked_worsened_urls: number
  link_equity_improved_urls: number
  link_equity_worsened_urls: number
  linking_pages_up_urls: number
  linking_pages_down_urls: number
  anchor_diversity_improved_urls: number
  anchor_diversity_worsened_urls: number
  boilerplate_improved_urls: number
  boilerplate_worsened_urls: number
}

export interface SiteInternalLinkingCompareRow {
  url: string
  normalized_url: string
  active_page_id: number | null
  baseline_page_id: number | null
  change_type: CrawlCompareChangeType
  highlights: InternalLinkingCompareHighlight[]
  active_issue_types: InternalLinkingIssueType[]
  baseline_issue_types: InternalLinkingIssueType[]
  new_issue_types: InternalLinkingIssueType[]
  resolved_issue_types: InternalLinkingIssueType[]
  active_internal_linking_score: number | null
  baseline_internal_linking_score: number | null
  delta_internal_linking_score: number | null
  active_link_equity_score: number | null
  baseline_link_equity_score: number | null
  delta_link_equity_score: number | null
  active_incoming_follow_linking_pages: number | null
  baseline_incoming_follow_linking_pages: number | null
  delta_incoming_follow_linking_pages: number | null
  active_anchor_diversity_score: number | null
  baseline_anchor_diversity_score: number | null
  delta_anchor_diversity_score: number | null
  active_boilerplate_like_share: number | null
  baseline_boilerplate_like_share: number | null
  delta_boilerplate_like_share: number | null
  active_orphan_like: boolean | null
  baseline_orphan_like: boolean | null
  active_weakly_linked_important: boolean | null
  baseline_weakly_linked_important: boolean | null
  change_rationale: string
}

export interface PaginatedSiteInternalLinkingCompareResponse extends PaginatedResponse<SiteInternalLinkingCompareRow> {
  context: SiteCompareContext
  gsc_date_range: GscDateRangeLabel
  summary: SiteInternalLinkingCompareSummary
}

export interface GscCompareTotals {
  clicks: number
  impressions: number
  ctr: number
  position: number | null
  top_queries_count: number
}

export interface GscCompareSummary {
  crawl_job_id: number
  baseline_gsc_range: GscDateRangeLabel
  target_gsc_range: GscDateRangeLabel
  baseline: GscCompareTotals
  target: GscCompareTotals
  delta_clicks: number
  delta_impressions: number
  delta_ctr: number
  delta_position: number | null
  delta_top_queries_count: number
  improved_urls: number
  worsened_urls: number
  flat_urls: number
}

export interface GscCompareRow {
  page_id: number
  url: string
  normalized_url: string
  has_baseline_data: boolean
  has_target_data: boolean
  baseline_clicks: number
  target_clicks: number
  delta_clicks: number
  baseline_impressions: number
  target_impressions: number
  delta_impressions: number
  baseline_ctr: number
  target_ctr: number
  delta_ctr: number
  baseline_position: number | null
  target_position: number | null
  delta_position: number | null
  baseline_top_queries_count: number
  target_top_queries_count: number
  delta_top_queries_count: number
  overall_trend: MetricTrend
  clicks_trend: MetricTrend
  impressions_trend: MetricTrend
  ctr_trend: MetricTrend
  position_trend: MetricTrend
  top_queries_trend: MetricTrend
  rationale: string
  has_technical_issue: boolean
  priority_score: number
  priority_level: PriorityLevel
  primary_opportunity_type: OpportunityType | null
}

export interface PaginatedGscCompareResponse extends PaginatedResponse<GscCompareRow> {
  summary: GscCompareSummary
}
