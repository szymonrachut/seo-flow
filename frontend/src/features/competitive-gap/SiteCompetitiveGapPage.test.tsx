import { QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { I18nextProvider } from 'react-i18next'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { afterEach, describe, expect, test, vi } from 'vitest'

import i18n from '../../i18n'
import { createTestQueryClient, jsonResponse } from '../../test/testUtils'
import type {
  CompetitiveGapDiagnosticFlag,
  CompetitiveGapEmptyStateReason,
  PaginatedCompetitiveGapResponse,
  SiteContentGapReviewRun,
} from '../../types/api'
import { SiteWorkspaceLayout } from '../sites/SiteWorkspaceLayout'
import {
  SiteCompetitiveGapCompetitorsPage,
  SiteCompetitiveGapOverviewPage,
  SiteCompetitiveGapPage,
  SiteCompetitiveGapResultsPage,
  SiteCompetitiveGapSyncPage,
  SiteCompetitiveGapStrategyPage,
} from './SiteCompetitiveGapPage'

afterEach(() => {
  vi.useRealTimers()
  vi.restoreAllMocks()
})

const sitePayload = {
  id: 5,
  domain: 'example.com',
  root_url: 'https://example.com',
  created_at: '2026-03-10T12:00:00Z',
  selected_gsc_property_uri: 'sc-domain:example.com',
  selected_gsc_property_permission_level: 'siteOwner',
  summary: {
    total_crawls: 2,
    pending_crawls: 0,
    running_crawls: 0,
    finished_crawls: 2,
    failed_crawls: 0,
    stopped_crawls: 0,
    first_crawl_at: '2026-03-13T12:00:00Z',
    last_crawl_at: '2026-03-14T12:00:00Z',
  },
  active_crawl_id: 11,
  baseline_crawl_id: 10,
  active_crawl: {
    id: 11,
    site_id: 5,
    status: 'finished',
    created_at: '2026-03-14T12:00:00Z',
    started_at: '2026-03-14T12:01:00Z',
    finished_at: '2026-03-14T12:10:00Z',
    settings_json: { start_url: 'https://example.com' },
    stats_json: {},
    summary_counts: {
      total_pages: 42,
      total_links: 280,
      total_internal_links: 210,
      total_external_links: 70,
      pages_missing_title: 3,
      pages_missing_meta_description: 4,
      pages_missing_h1: 2,
      pages_non_indexable_like: 1,
      rendered_pages: 5,
      js_heavy_like_pages: 2,
      pages_with_render_errors: 0,
      pages_with_schema: 8,
      pages_with_x_robots_tag: 1,
      pages_with_gsc_28d: 20,
      pages_with_gsc_90d: 25,
      gsc_opportunities_28d: 6,
      gsc_opportunities_90d: 8,
      broken_internal_links: 1,
      redirecting_internal_links: 2,
    },
    progress: {
      visited_pages: 42,
      queued_urls: 0,
      discovered_links: 280,
      internal_links: 210,
      external_links: 70,
      errors_count: 0,
    },
  },
  baseline_crawl: {
    id: 10,
    site_id: 5,
    status: 'finished',
    created_at: '2026-03-13T12:00:00Z',
    started_at: '2026-03-13T12:01:00Z',
    finished_at: '2026-03-13T12:08:00Z',
    settings_json: { start_url: 'https://example.com' },
    stats_json: {},
    summary_counts: {
      total_pages: 40,
      total_links: 250,
      total_internal_links: 190,
      total_external_links: 60,
      pages_missing_title: 5,
      pages_missing_meta_description: 3,
      pages_missing_h1: 2,
      pages_non_indexable_like: 2,
      rendered_pages: 2,
      js_heavy_like_pages: 1,
      pages_with_render_errors: 0,
      pages_with_schema: 6,
      pages_with_x_robots_tag: 1,
      pages_with_gsc_28d: 18,
      pages_with_gsc_90d: 20,
      gsc_opportunities_28d: 4,
      gsc_opportunities_90d: 6,
      broken_internal_links: 2,
      redirecting_internal_links: 1,
    },
    progress: {
      visited_pages: 40,
      queued_urls: 0,
      discovered_links: 250,
      internal_links: 190,
      external_links: 60,
      errors_count: 0,
    },
  },
  crawl_history: [
    {
      id: 11,
      site_id: 5,
      status: 'finished',
      root_url: 'https://example.com',
      created_at: '2026-03-14T12:00:00Z',
      started_at: '2026-03-14T12:01:00Z',
      finished_at: '2026-03-14T12:10:00Z',
      total_pages: 42,
      total_internal_links: 210,
      total_external_links: 70,
      total_errors: 0,
    },
    {
      id: 10,
      site_id: 5,
      status: 'finished',
      root_url: 'https://example.com',
      created_at: '2026-03-13T12:00:00Z',
      started_at: '2026-03-13T12:01:00Z',
      finished_at: '2026-03-13T12:08:00Z',
      total_pages: 40,
      total_internal_links: 190,
      total_external_links: 60,
      total_errors: 0,
    },
  ],
}

function buildSyncSummary(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    visited_urls_count: 0,
    stored_pages_count: 0,
    extracted_pages_count: 0,
    skipped_urls_count: 0,
    skipped_non_html_count: 0,
    skipped_non_indexable_count: 0,
    skipped_out_of_scope_count: 0,
    skipped_filtered_count: 0,
    skipped_low_value_count: 0,
    skipped_duplicate_url_count: 0,
    skipped_fetch_error_count: 0,
    extraction_created_count: 0,
    extraction_skipped_unchanged_count: 0,
    extraction_failed_count: 0,
    sample_urls_by_reason: {},
    ...overrides,
  }
}

const baseSemanticDiagnostics: PaginatedCompetitiveGapResponse['context']['semantic_diagnostics'] = {
  semantic_version: 'competitive-gap-semantic-card-v1',
  cluster_version: 'competitive-gap-cluster-v1',
  coverage_version: 'competitive-gap-coverage-v1',
  competitor_semantic_cards_count: 10,
  own_page_semantic_profiles_count: 6,
  canonical_pages_count: 8,
  duplicate_pages_count: 1,
  near_duplicate_pages_count: 1,
  clusters_count: 2,
  low_confidence_clusters_count: 0,
  latest_failure_stage: null,
  latest_failure_error_code: null,
  latest_failure_error_message: null,
  coverage_breakdown: {
    exact_coverage: 0,
    strong_semantic_coverage: 1,
    partial_coverage: 1,
    wrong_intent_coverage: 0,
    commercial_missing_supporting: 0,
    informational_missing_commercial: 0,
    no_meaningful_coverage: 0,
  },
}

const baseCanonicalizationSummary: PaginatedCompetitiveGapResponse['summary']['canonicalization_summary'] = {
  canonical_pages_count: 8,
  duplicate_pages_count: 1,
  near_duplicate_pages_count: 1,
  filtered_leftovers_count: 0,
}

const baseClusterQualitySummary: PaginatedCompetitiveGapResponse['summary']['cluster_quality_summary'] = {
  clusters_count: 2,
  low_confidence_clusters_count: 0,
  average_cluster_confidence: 0.83,
  average_cluster_member_count: 2.5,
}

const baseCoverageCounts: PaginatedCompetitiveGapResponse['summary']['counts_by_coverage_type'] = {
  exact_coverage: 0,
  strong_semantic_coverage: 1,
  partial_coverage: 1,
  wrong_intent_coverage: 0,
  commercial_missing_supporting: 0,
  informational_missing_commercial: 0,
  no_meaningful_coverage: 0,
}

const baseGapDetailCounts: PaginatedCompetitiveGapResponse['summary']['counts_by_gap_detail_type'] = {
  NEW_TOPIC: 1,
  EXPAND_EXISTING_PAGE: 1,
  MISSING_SUPPORTING_CONTENT: 0,
  MISSING_MONEY_PAGE: 0,
  INTENT_MISMATCH: 0,
  FORMAT_GAP: 0,
  GEO_GAP: 0,
}

const gapPayload: PaginatedCompetitiveGapResponse = {
  context: {
    site_id: 5,
    site_domain: 'example.com',
    active_crawl_id: 11,
    basis_crawl_job_id: 11,
    gsc_date_range: 'last_28_days',
    active_crawl: {
      id: 11,
      status: 'finished',
      created_at: '2026-03-14T12:00:00Z',
      started_at: '2026-03-14T12:01:00Z',
      finished_at: '2026-03-14T12:10:00Z',
      root_url: 'https://example.com',
    },
    strategy_present: true,
    active_competitor_count: 2,
    data_source_mode: 'legacy',
    is_outdated_for_active_crawl: false,
    review_run_status: null,
    data_readiness: {
      has_active_crawl: true,
      has_strategy: true,
      has_active_competitors: true,
      gap_ready: true,
      missing_inputs: [],
      active_competitors_count: 2,
      competitors_with_pages_count: 2,
      competitors_with_current_extractions_count: 2,
      total_competitor_pages_count: 12,
      total_current_extractions_count: 10,
    },
    semantic_diagnostics: baseSemanticDiagnostics,
    empty_state_reason: null,
  },
  summary: {
    total_gaps: 2,
    high_priority_gaps: 1,
    competitors_considered: 2,
    topics_covered: 2,
    counts_by_type: {
      NEW_TOPIC: 1,
      EXPAND_EXISTING_TOPIC: 1,
      MISSING_SUPPORTING_PAGE: 0,
    },
    counts_by_page_type: {
      home: 0,
      category: 0,
      product: 0,
      service: 1,
      blog_article: 1,
      blog_index: 0,
      contact: 0,
      about: 0,
      faq: 0,
      location: 0,
      legal: 0,
      utility: 0,
      other: 0,
    },
    counts_by_gap_detail_type: baseGapDetailCounts,
    counts_by_coverage_type: baseCoverageCounts,
    canonicalization_summary: baseCanonicalizationSummary,
    cluster_quality_summary: baseClusterQualitySummary,
  },
  items: [
    {
      gap_key: 'NEW_TOPIC:local-seo:none:service',
      gap_type: 'NEW_TOPIC',
      segment: 'create_new_page',
      topic_key: 'local-seo',
      topic_label: 'Local SEO',
      semantic_cluster_key: 'semantic/local-seo-services',
      canonical_topic_label: 'Local SEO Services',
      merged_topic_count: 3,
      own_match_status: 'semantic_match',
      own_match_source: 'own-site/content/local-seo-services',
      target_page_id: null,
      target_url: null,
      page_type: 'service',
      target_page_type: null,
      suggested_page_type: 'service',
      competitor_ids: [1, 2],
      competitor_count: 2,
      competitor_urls: ['https://competitor-a.com/local-seo', 'https://competitor-b.com/local-seo'],
      consensus_score: 74,
      competitor_coverage_score: 82,
      own_coverage_score: 0,
      strategy_alignment_score: 65,
      business_value_score: 58,
      priority_score: 77,
      confidence: 0.84,
      rationale: 'Competitors cover Local SEO while the site has no matching topic cluster.',
      signals: {},
    },
    {
      gap_key: 'EXPAND_EXISTING_TOPIC:content-strategy:4:none',
      gap_type: 'EXPAND_EXISTING_TOPIC',
      segment: 'expand_existing_page',
      topic_key: 'content-strategy',
      topic_label: 'Content strategy',
      semantic_cluster_key: 'semantic/content-strategy',
      canonical_topic_label: 'Content Strategy',
      merged_topic_count: 1,
      own_match_status: 'exact_match',
      own_match_source: 'own-site/pages/4',
      target_page_id: 4,
      target_url: 'https://example.com/content-strategy',
      page_type: 'blog_article',
      target_page_type: 'blog_article',
      suggested_page_type: null,
      competitor_ids: [1],
      competitor_count: 1,
      competitor_urls: ['https://competitor-a.com/content-strategy'],
      consensus_score: 55,
      competitor_coverage_score: 68,
      own_coverage_score: 42,
      strategy_alignment_score: 70,
      business_value_score: 61,
      priority_score: 63,
      confidence: 0.79,
      rationale: 'Competitors go deeper on Content strategy than the current site.',
      signals: {},
    },
  ],
  page: 1,
  page_size: 25,
  total_items: 2,
  total_pages: 1,
}

const reviewRunsPayload: SiteContentGapReviewRun[] = []

function createGapPayload(
  overrides: {
    context?: Partial<PaginatedCompetitiveGapResponse['context']> & {
      empty_state_reason?: CompetitiveGapEmptyStateReason | null
      data_readiness?: Partial<PaginatedCompetitiveGapResponse['context']['data_readiness']> & {
        missing_inputs?: CompetitiveGapDiagnosticFlag[]
      }
    }
    summary?: Partial<PaginatedCompetitiveGapResponse['summary']>
    items?: PaginatedCompetitiveGapResponse['items']
    page?: number
    page_size?: number
    total_items?: number
    total_pages?: number
  } = {},
) {
  return {
    ...gapPayload,
    ...overrides,
    context: {
      ...gapPayload.context,
      ...(overrides.context ?? {}),
      data_readiness: {
        ...gapPayload.context.data_readiness,
        ...(overrides.context?.data_readiness ?? {}),
      },
      semantic_diagnostics: {
        ...gapPayload.context.semantic_diagnostics,
        ...(overrides.context?.semantic_diagnostics ?? {}),
      },
    },
    summary: {
      ...gapPayload.summary,
      ...(overrides.summary ?? {}),
      counts_by_gap_detail_type: {
        ...gapPayload.summary.counts_by_gap_detail_type,
        ...(overrides.summary?.counts_by_gap_detail_type ?? {}),
      },
      counts_by_coverage_type: {
        ...gapPayload.summary.counts_by_coverage_type,
        ...(overrides.summary?.counts_by_coverage_type ?? {}),
      },
      canonicalization_summary: {
        ...gapPayload.summary.canonicalization_summary,
        ...(overrides.summary?.canonicalization_summary ?? {}),
      },
      cluster_quality_summary: {
        ...gapPayload.summary.cluster_quality_summary,
        ...(overrides.summary?.cluster_quality_summary ?? {}),
      },
    },
    items: overrides.items ?? gapPayload.items,
  }
}

function renderCompetitiveGap(route: string) {
  const queryClient = createTestQueryClient()
  const user = userEvent.setup()

  return {
    user,
    ...render(
      <I18nextProvider i18n={i18n}>
        <QueryClientProvider client={queryClient}>
          <MemoryRouter initialEntries={[route]}>
            <Routes>
              <Route path="/sites/:siteId" element={<SiteWorkspaceLayout />}>
                <Route
                  path="competitive-gap"
                  element={
                    <>
                      <SiteCompetitiveGapPage />
                      <LocationEcho />
                    </>
                  }
                />
              </Route>
            </Routes>
          </MemoryRouter>
        </QueryClientProvider>
      </I18nextProvider>,
    ),
  }
}

function renderCompetitiveGapWorkspace(route: string) {
  const queryClient = createTestQueryClient()
  const user = userEvent.setup()

  return {
    user,
    ...render(
      <I18nextProvider i18n={i18n}>
        <QueryClientProvider client={queryClient}>
          <MemoryRouter initialEntries={[route]}>
            <Routes>
              <Route path="/sites/:siteId" element={<SiteWorkspaceLayout />}>
                <Route path="competitive-gap">
                  <Route
                    index
                    element={
                      <>
                        <SiteCompetitiveGapOverviewPage />
                        <LocationEcho />
                      </>
                    }
                  />
                  <Route
                    path="strategy"
                    element={
                      <>
                        <SiteCompetitiveGapStrategyPage />
                        <LocationEcho />
                      </>
                    }
                  />
                  <Route
                    path="competitors"
                    element={
                      <>
                        <SiteCompetitiveGapCompetitorsPage />
                        <LocationEcho />
                      </>
                    }
                  />
                  <Route
                    path="results"
                    element={
                      <>
                        <SiteCompetitiveGapResultsPage />
                        <LocationEcho />
                      </>
                    }
                  />
                  <Route
                    path="sync"
                    element={
                      <>
                        <SiteCompetitiveGapSyncPage />
                        <LocationEcho />
                      </>
                    }
                  />
                </Route>
              </Route>
            </Routes>
          </MemoryRouter>
        </QueryClientProvider>
      </I18nextProvider>,
    ),
  }
}

function LocationEcho() {
  const location = useLocation()
  return <output data-testid="location-search">{location.search}</output>
}

describe('SiteCompetitiveGapPage', () => {
  test('renders strategy, competitors, export link and lazy explanation', async () => {
    let explanationCalls = 0
    const currentStrategy = {
      id: 7,
      site_id: 5,
      raw_user_input: 'We want more local SEO leads and content strategy demand.',
      normalized_strategy_json: {
        schema_version: 'competitive_gap_strategy_v1',
        business_summary: 'SEO consultancy focused on local growth.',
        target_audiences: ['local businesses'],
        primary_goals: ['lead generation'],
        priority_topics: ['local seo', 'content strategy'],
        supporting_topics: ['technical seo'],
        priority_page_types: ['service'],
        geographic_focus: ['Warsaw'],
        constraints: [],
        differentiation_points: ['manual competitor workflow'],
      },
      llm_provider: 'openai',
      llm_model: 'gpt-5-mini',
      prompt_version: 'competitive-gap-strategy-normalization-v1',
      normalization_status: 'ready',
      last_normalization_attempt_at: '2026-03-16T12:10:00Z',
      normalization_fallback_used: false,
      normalization_debug_code: null,
      normalization_debug_message: 'Strategy normalized successfully.',
      normalized_at: '2026-03-16T12:10:00Z',
      created_at: '2026-03-16T12:00:00Z',
      updated_at: '2026-03-16T12:10:00Z',
    }
    const competitors = [
      {
        id: 1,
        site_id: 5,
        label: 'Competitor A',
        root_url: 'https://competitor-a.com',
        domain: 'competitor-a.com',
        is_active: true,
        notes: 'Primary local competitor',
        last_sync_run_id: 0,
        last_sync_status: 'idle',
        last_sync_stage: 'idle',
        last_sync_started_at: null,
        last_sync_finished_at: null,
        last_sync_error_code: null,
        last_sync_error: null,
        last_sync_processed_urls: 0,
        last_sync_url_limit: 400,
        last_sync_processed_extraction_pages: 0,
        last_sync_total_extractable_pages: 0,
        last_sync_progress_percent: 0,
        last_sync_summary: buildSyncSummary(),
        semantic_status: 'not_started',
        semantic_analysis_mode: 'not_started',
        last_semantic_run_started_at: null,
        last_semantic_run_finished_at: null,
        last_semantic_error: null,
        semantic_candidates_count: 0,
        semantic_llm_jobs_count: 0,
        semantic_resolved_count: 0,
        semantic_cache_hits: 0,
        semantic_fallback_count: 0,
        semantic_llm_merged_urls_count: 0,
        semantic_model: null,
        semantic_prompt_version: null,
        pages_count: 0,
        extracted_pages_count: 0,
        last_extracted_at: null,
        created_at: '2026-03-16T12:00:00Z',
        updated_at: '2026-03-16T12:00:00Z',
      },
      {
        id: 2,
        site_id: 5,
        label: 'Competitor B',
        root_url: 'https://competitor-b.com',
        domain: 'competitor-b.com',
        is_active: true,
        notes: null,
        last_sync_run_id: 4,
        last_sync_status: 'done',
        last_sync_stage: 'done',
        last_sync_started_at: '2026-03-16T12:15:00Z',
        last_sync_finished_at: '2026-03-16T12:16:00Z',
        last_sync_error_code: null,
        last_sync_error: null,
        last_sync_processed_urls: 28,
        last_sync_url_limit: 400,
        last_sync_processed_extraction_pages: 12,
        last_sync_total_extractable_pages: 12,
        last_sync_progress_percent: 100,
        last_sync_summary: buildSyncSummary({
          visited_urls_count: 28,
          stored_pages_count: 12,
          extracted_pages_count: 10,
          skipped_urls_count: 16,
          skipped_filtered_count: 8,
          skipped_low_value_count: 5,
          skipped_non_html_count: 2,
          skipped_duplicate_url_count: 1,
        }),
        semantic_status: 'ready',
        semantic_analysis_mode: 'mixed',
        last_semantic_run_started_at: '2026-03-16T12:20:00Z',
        last_semantic_run_finished_at: '2026-03-16T12:22:00Z',
        last_semantic_error: null,
        semantic_candidates_count: 12,
        semantic_llm_jobs_count: 4,
        semantic_resolved_count: 8,
        semantic_cache_hits: 7,
        semantic_fallback_count: 1,
        semantic_llm_merged_urls_count: 3,
        semantic_model: 'gpt-5.4-mini',
        semantic_prompt_version: 'competitive-gap-semantic-v1',
        pages_count: 12,
        extracted_pages_count: 10,
        last_extracted_at: '2026-03-16T12:16:00Z',
        created_at: '2026-03-16T12:00:00Z',
        updated_at: '2026-03-16T12:16:00Z',
      },
      {
        id: 3,
        site_id: 5,
        label: 'Competitor C',
        root_url: 'https://competitor-c.com',
        domain: 'competitor-c.com',
        is_active: true,
        notes: 'Errored sync',
        last_sync_run_id: 5,
        last_sync_status: 'failed',
        last_sync_stage: 'extracting',
        last_sync_started_at: '2026-03-16T12:17:00Z',
        last_sync_finished_at: '2026-03-16T12:18:00Z',
        last_sync_error_code: 'fetch_timeout',
        last_sync_error: 'Timeout while fetching the homepage.',
        last_sync_processed_urls: 34,
        last_sync_url_limit: 400,
        last_sync_processed_extraction_pages: 5,
        last_sync_total_extractable_pages: 12,
        last_sync_progress_percent: 42,
        last_sync_summary: buildSyncSummary({
          visited_urls_count: 34,
          stored_pages_count: 5,
          extracted_pages_count: 0,
          skipped_urls_count: 19,
          skipped_filtered_count: 10,
          skipped_fetch_error_count: 4,
          skipped_low_value_count: 5,
        }),
        semantic_status: 'failed',
        semantic_analysis_mode: 'mixed',
        last_semantic_run_started_at: '2026-03-16T12:25:00Z',
        last_semantic_run_finished_at: '2026-03-16T12:26:00Z',
        last_semantic_error: 'Semantic matching timed out after 30 seconds.',
        semantic_candidates_count: 4,
        semantic_llm_jobs_count: 1,
        semantic_resolved_count: 0,
        semantic_cache_hits: 0,
        semantic_fallback_count: 1,
        semantic_llm_merged_urls_count: 2,
        semantic_model: 'gpt-5.4-mini',
        semantic_prompt_version: 'competitive-gap-semantic-v1',
        pages_count: 0,
        extracted_pages_count: 0,
        last_extracted_at: null,
        created_at: '2026-03-16T12:00:00Z',
        updated_at: '2026-03-16T12:18:00Z',
      },
    ]

    vi.spyOn(globalThis, 'fetch').mockImplementation((input) => {
      const url = typeof input === 'string' ? input : input instanceof Request ? input.url : String(input)
      if (url.includes('/competitive-content-gap/explanation')) {
        explanationCalls += 1
        return jsonResponse({
          gap_key: 'NEW_TOPIC:local-seo:none:service',
          gap_signature: 'abc123',
          explanation: 'Competitors repeatedly cover this topic while the site has no matching page.',
          bullets: ['Two competitors already cover the topic.', 'The current site has no matching page.'],
          used_llm: true,
          fallback_used: false,
          fallback_reason: null,
          llm_provider: 'openai',
          llm_model: 'gpt-5-mini',
          prompt_version: 'competitive-gap-explanation-v1',
        })
      }
      if (url.includes('/competitive-content-gap/strategy')) {
        return jsonResponse(currentStrategy)
      }
      if (url.includes('/competitive-content-gap/review-runs')) {
        return jsonResponse(reviewRunsPayload)
      }
      if (url.includes('/competitive-content-gap/competitors')) {
        return jsonResponse(competitors)
      }
      if (url.includes('/competitive-content-gap')) {
        return jsonResponse(gapPayload)
      }
      if (url.includes('/sites/5')) {
        return jsonResponse(sitePayload)
      }
      throw new Error(`Unexpected request: ${url}`)
    })

    const { user } = renderCompetitiveGap('/sites/5/competitive-gap?active_crawl_id=11&baseline_crawl_id=10&topic=local')

    expect((await screen.findAllByText('Competitor A', {}, { timeout: 5000 })).length).toBeGreaterThan(0)
    expect(screen.getByText('SEO consultancy focused on local growth.')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Competitive gap' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Normalize again' })).toBeInTheDocument()
    expect(screen.getByText('Normalization debug')).toBeInTheDocument()
    expect(screen.getByText('Semantic merge debug')).toBeInTheDocument()
    expect(screen.getByText('LLM + local fallback')).toBeInTheDocument()
    expect(screen.getByText('LLM merged 5 URLs')).toBeInTheDocument()
    expect(screen.getByText('Fallback not used')).toBeInTheDocument()
    expect(screen.getByText('Data readiness')).toBeInTheDocument()
    expect(screen.getByText('Latest sync error')).toBeInTheDocument()
    expect(screen.getByText('Timeout while fetching the homepage.')).toBeInTheDocument()
    expect(screen.getByText('Analyzing pages: 5 / 12')).toBeInTheDocument()
    expect(screen.getByText('Filtered or utility: 10')).toBeInTheDocument()
    expect(screen.getAllByText('Semantic layer').length).toBeGreaterThan(0)
    expect(screen.getByText('Canonical topic: Local SEO Services')).toBeInTheDocument()
    expect(screen.getAllByText('Semantic match').length).toBeGreaterThan(0)
    expect(screen.getByText('Merged topics: 3')).toBeInTheDocument()
    expect(screen.getByText('Candidates: 12')).toBeInTheDocument()
    expect(screen.getByText('Resolved: 8')).toBeInTheDocument()
    expect(screen.getByText('50%')).toBeInTheDocument()
    expect(screen.getByText('Cache hits: 7')).toBeInTheDocument()
    expect(screen.getAllByText('Fallback count: 1').length).toBeGreaterThan(0)
    expect(screen.getByRole('button', { name: 'Resume semantic matching' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Re-run semantic matching' })).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: 'Reset runtime' }).length).toBeGreaterThan(0)
    expect(screen.getByRole('link', { name: 'Export gap CSV' })).toHaveAttribute(
      'href',
      expect.stringContaining('/sites/5/export/competitive-content-gap.csv'),
    )
    expect(screen.getByRole('link', { name: 'Export gap CSV' })).toHaveAttribute(
      'href',
      expect.stringContaining('topic=local'),
    )
    expect(explanationCalls).toBe(0)

    await user.click(screen.getAllByRole('button', { name: 'Explain' })[0])

    expect(await screen.findByText('Competitors repeatedly cover this topic while the site has no matching page.')).toBeInTheDocument()
    expect(explanationCalls).toBe(1)
  }, 10000)

  test('polls competitor status without repeatedly refetching the heavy gap payload during active runtime', async () => {
    vi.useFakeTimers()
    let gapCalls = 0
    let competitorsCalls = 0
    const busyCompetitors = [
      {
        id: 1,
        site_id: 5,
        label: 'Competitor A',
        root_url: 'https://competitor-a.com',
        domain: 'competitor-a.com',
        is_active: true,
        notes: null,
        last_sync_run_id: 12,
        last_sync_status: 'running',
        last_sync_stage: 'extracting',
        last_sync_started_at: '2026-03-16T12:05:00Z',
        last_sync_finished_at: null,
        last_sync_processed_urls: 4,
        last_sync_error_code: null,
        last_sync_error: null,
        last_sync_summary: buildSyncSummary({ visited_urls_count: 4, stored_pages_count: 4 }),
        pages_count: 4,
        extracted_pages_count: 0,
        latest_successful_sync_started_at: null,
        latest_successful_sync_finished_at: null,
        latest_successful_sync_summary: null,
        semantic_status: 'idle',
        semantic_stage: 'idle',
        semantic_last_run_id: null,
        semantic_last_started_at: null,
        semantic_last_finished_at: null,
        semantic_last_error_code: null,
        semantic_last_error: null,
        semantic_run_summary: null,
        latest_semantic_run_summary: null,
        latest_successful_semantic_started_at: null,
        latest_successful_semantic_finished_at: null,
        latest_successful_semantic_summary: null,
        created_at: '2026-03-16T12:00:00Z',
        updated_at: '2026-03-16T12:05:30Z',
      },
    ]

    vi.spyOn(globalThis, 'fetch').mockImplementation((input) => {
      const url = typeof input === 'string' ? input : input instanceof Request ? input.url : String(input)
      if (url.includes('/competitive-content-gap/strategy')) {
        return jsonResponse(null)
      }
      if (url.includes('/competitive-content-gap/review-runs')) {
        return jsonResponse(reviewRunsPayload)
      }
      if (url.includes('/competitive-content-gap/competitors')) {
        competitorsCalls += 1
        return jsonResponse(busyCompetitors)
      }
      if (url.includes('/competitive-content-gap/review-runs')) {
        return jsonResponse(reviewRunsPayload)
      }
      if (url.includes('/competitive-content-gap')) {
        gapCalls += 1
        return jsonResponse(gapPayload)
      }
      if (url.includes('/sites/5')) {
        return jsonResponse(sitePayload)
      }
      throw new Error(`Unexpected request: ${url}`)
    })

    const queryClient = createTestQueryClient()
    render(
      <I18nextProvider i18n={i18n}>
        <QueryClientProvider client={queryClient}>
          <MemoryRouter initialEntries={['/sites/5/competitive-gap?active_crawl_id=11&baseline_crawl_id=10']}>
            <Routes>
              <Route path="/sites/:siteId" element={<SiteWorkspaceLayout />}>
                <Route path="competitive-gap" element={<SiteCompetitiveGapPage />} />
              </Route>
            </Routes>
          </MemoryRouter>
        </QueryClientProvider>
      </I18nextProvider>,
    )

    await vi.advanceTimersByTimeAsync(1)
    await Promise.resolve()

    expect(screen.getByRole('heading', { name: 'Competitive gap' })).toBeInTheDocument()
    expect(gapCalls).toBe(1)
    expect(competitorsCalls).toBe(1)

    await vi.advanceTimersByTimeAsync(8_500)

    expect(gapCalls).toBe(1)
    expect(competitorsCalls).toBeGreaterThan(1)
  }, 10000)

  test('reruns strategy normalization and syncs competitors on demand', async () => {
    const strategyPayload: any = {
      id: 7,
      site_id: 5,
      raw_user_input: 'Need stronger local SEO coverage.',
      normalized_strategy_json: null,
      llm_provider: null,
      llm_model: null,
      prompt_version: null,
      normalization_status: 'not_processed',
      last_normalization_attempt_at: '2026-03-16T12:00:00Z',
      normalization_fallback_used: true,
      normalization_debug_code: 'llm_disabled',
      normalization_debug_message: 'LLM normalization is disabled.',
      normalized_at: null,
      created_at: '2026-03-16T12:00:00Z',
      updated_at: '2026-03-16T12:00:00Z',
    }
    const competitors: any[] = [
      {
        id: 1,
        site_id: 5,
        label: 'Competitor A',
        root_url: 'https://competitor-a.com',
        domain: 'competitor-a.com',
        is_active: true,
        notes: null,
        last_sync_run_id: 0,
        last_sync_status: 'idle',
        last_sync_stage: 'idle',
        last_sync_started_at: null,
        last_sync_finished_at: null,
        last_sync_error_code: null,
        last_sync_error: null,
        last_sync_processed_urls: 0,
        last_sync_url_limit: 400,
        last_sync_processed_extraction_pages: 0,
        last_sync_total_extractable_pages: 0,
        last_sync_progress_percent: 0,
        last_sync_summary: buildSyncSummary(),
        pages_count: 0,
        extracted_pages_count: 0,
        last_extracted_at: null,
        created_at: '2026-03-16T12:00:00Z',
        updated_at: '2026-03-16T12:00:00Z',
      },
    ]
    const requestLog: string[] = []

    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
      const request = input instanceof Request ? input : new Request(typeof input === 'string' ? input : String(input), init)
      requestLog.push(`${request.method} ${request.url}`)

      if (request.url.includes('/competitive-content-gap/strategy') && request.method === 'PUT') {
        const body = (await request.json()) as { raw_user_input: string }
        strategyPayload.raw_user_input = body.raw_user_input
        strategyPayload.normalization_status = 'ready'
        strategyPayload.llm_provider = 'openai'
        strategyPayload.llm_model = 'gpt-5-mini'
        strategyPayload.prompt_version = 'competitive-gap-strategy-normalization-v1'
        strategyPayload.last_normalization_attempt_at = '2026-03-16T12:05:00Z'
        strategyPayload.normalized_at = '2026-03-16T12:05:00Z'
        strategyPayload.normalization_fallback_used = false
        strategyPayload.normalization_debug_code = null
        strategyPayload.normalization_debug_message = 'Strategy normalized successfully.'
        strategyPayload.normalized_strategy_json = {
          schema_version: 'competitive_gap_strategy_v1',
          business_summary: 'Focused on local SEO demand.',
          target_audiences: ['local businesses'],
          primary_goals: ['lead generation'],
          priority_topics: ['local seo'],
          supporting_topics: ['google business profile'],
          priority_page_types: ['service'],
          geographic_focus: ['Warsaw'],
          constraints: [],
          differentiation_points: ['manual competitor reviews'],
        }
        strategyPayload.updated_at = '2026-03-16T12:05:00Z'
        return jsonResponse(strategyPayload)
      }

      if (request.url.includes('/competitive-content-gap/strategy')) {
        return jsonResponse(strategyPayload)
      }

      if (request.url.includes('/competitive-content-gap/competitors/1/sync') && request.method === 'POST') {
        competitors[0] = {
          ...competitors[0],
          last_sync_run_id: 1,
          last_sync_status: 'queued',
          last_sync_stage: 'queued',
          last_sync_started_at: '2026-03-16T12:06:00Z',
          last_sync_error_code: null,
          last_sync_processed_urls: 0,
          last_sync_url_limit: 400,
          last_sync_processed_extraction_pages: 0,
          last_sync_total_extractable_pages: 0,
          last_sync_progress_percent: 0,
          last_sync_summary: buildSyncSummary(),
        }
        return jsonResponse(competitors[0], { status: 202 })
      }

      if (request.url.includes('/competitive-content-gap/competitors/1/reset-sync') && request.method === 'POST') {
        competitors[0] = {
          ...competitors[0],
          last_sync_run_id: 1,
          last_sync_status: 'idle',
          last_sync_stage: 'idle',
          last_sync_started_at: null,
          last_sync_finished_at: null,
          last_sync_error_code: null,
          last_sync_error: null,
          last_sync_processed_urls: 0,
          last_sync_url_limit: 400,
          last_sync_processed_extraction_pages: 0,
          last_sync_total_extractable_pages: 0,
          last_sync_progress_percent: 0,
          last_sync_summary: buildSyncSummary(),
        }
        return jsonResponse(competitors[0])
      }

      if (request.url.includes('/competitive-content-gap/competitors')) {
        return jsonResponse(competitors)
      }

      if (request.url.includes('/competitive-content-gap/review-runs')) {
        return jsonResponse(reviewRunsPayload)
      }

      if (request.url.includes('/competitive-content-gap')) {
        return jsonResponse(gapPayload)
      }

      if (request.url.includes('/sites/5')) {
        return jsonResponse(sitePayload)
      }

      throw new Error(`Unexpected request: ${request.url}`)
    })

    const { user } = renderCompetitiveGap('/sites/5/competitive-gap?active_crawl_id=11&baseline_crawl_id=10')

    expect((await screen.findAllByText('Competitor A', {}, { timeout: 5000 })).length).toBeGreaterThan(0)

    await user.click(screen.getByRole('button', { name: 'Normalize again' }))

    await waitFor(() =>
      expect(
        requestLog.some((entry) => entry.includes('PUT http://localhost:8000/sites/5/competitive-content-gap/strategy')),
      ).toBe(true),
    )
    expect(await screen.findByText('Focused on local SEO demand.')).toBeInTheDocument()
    expect(screen.getByText('Strategy normalized successfully.')).toBeInTheDocument()

    await user.click(screen.getAllByRole('button', { name: 'Sync' })[0])

    await waitFor(() =>
      expect(
        requestLog.some((entry) => entry.includes('POST http://localhost:8000/sites/5/competitive-content-gap/competitors/1/sync')),
      ).toBe(true),
    )
    expect((await screen.findAllByText('Queued')).length).toBeGreaterThan(0)

    await user.click(screen.getAllByRole('button', { name: 'Reset runtime' })[0])

    await waitFor(() =>
      expect(
        requestLog.some((entry) => entry.includes('POST http://localhost:8000/sites/5/competitive-content-gap/competitors/1/reset-sync')),
      ).toBe(true),
    )
    expect((await screen.findAllByText('Idle')).length).toBeGreaterThan(0)
  }, 15000)

  test('shows recent runs and lets the operator retry a failed run', async () => {
    const competitors: any[] = [
      {
        id: 1,
        site_id: 5,
        label: 'Competitor A',
        root_url: 'https://competitor-a.com',
        domain: 'competitor-a.com',
        is_active: true,
        notes: 'Retry candidate',
        last_sync_run_id: 3,
        last_sync_status: 'failed',
        last_sync_stage: 'failed',
        last_sync_started_at: '2026-03-16T12:06:00Z',
        last_sync_finished_at: '2026-03-16T12:07:00Z',
        last_sync_error_code: 'timeout',
        last_sync_error: 'OpenAI request timed out.',
        last_sync_processed_urls: 18,
        last_sync_url_limit: 400,
        last_sync_processed_extraction_pages: 4,
        last_sync_total_extractable_pages: 6,
        last_sync_progress_percent: 64,
        last_sync_summary: buildSyncSummary({
          visited_urls_count: 18,
          stored_pages_count: 6,
          extracted_pages_count: 4,
          skipped_urls_count: 8,
        }),
        pages_count: 6,
        extracted_pages_count: 4,
        last_extracted_at: '2026-03-16T12:07:00Z',
        created_at: '2026-03-16T12:00:00Z',
        updated_at: '2026-03-16T12:07:00Z',
      },
    ]
    let syncRuns: any[] = [
      {
        id: 8,
        site_id: 5,
        competitor_id: 1,
        run_id: 3,
        status: 'failed',
        stage: 'failed',
        trigger_source: 'manual_single',
        started_at: '2026-03-16T12:06:00Z',
        finished_at: '2026-03-16T12:07:00Z',
        last_heartbeat_at: '2026-03-16T12:06:58Z',
        lease_expires_at: '2026-03-16T12:07:10Z',
        error_code: 'timeout',
        error_message_safe: 'OpenAI request timed out.',
        summary_json: buildSyncSummary({
          visited_urls_count: 18,
          stored_pages_count: 6,
          extracted_pages_count: 4,
        }),
        retry_of_run_id: null,
        processed_urls: 18,
        url_limit: 400,
        processed_extraction_pages: 4,
        total_extractable_pages: 6,
        progress_percent: 64,
        created_at: '2026-03-16T12:06:00Z',
        updated_at: '2026-03-16T12:07:00Z',
      },
      {
        id: 7,
        site_id: 5,
        competitor_id: 1,
        run_id: 2,
        status: 'done',
        stage: 'done',
        trigger_source: 'manual_single',
        started_at: '2026-03-16T11:06:00Z',
        finished_at: '2026-03-16T11:07:00Z',
        last_heartbeat_at: '2026-03-16T11:06:58Z',
        lease_expires_at: '2026-03-16T11:07:10Z',
        error_code: null,
        error_message_safe: null,
        summary_json: buildSyncSummary({
          visited_urls_count: 30,
          stored_pages_count: 10,
          extracted_pages_count: 8,
        }),
        retry_of_run_id: null,
        processed_urls: 30,
        url_limit: 400,
        processed_extraction_pages: 8,
        total_extractable_pages: 8,
        progress_percent: 100,
        created_at: '2026-03-16T11:06:00Z',
        updated_at: '2026-03-16T11:07:00Z',
      },
    ]
    const requestLog: string[] = []

    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
      const request = input instanceof Request ? input : new Request(typeof input === 'string' ? input : String(input), init)
      requestLog.push(`${request.method} ${request.url}`)

      if (request.url.includes('/competitive-content-gap/strategy')) {
        return jsonResponse(null)
      }

      if (request.url.includes('/competitive-content-gap/competitors/1/retry-sync') && request.method === 'POST') {
        competitors[0] = {
          ...competitors[0],
          last_sync_run_id: 4,
          last_sync_status: 'queued',
          last_sync_stage: 'queued',
          last_sync_started_at: '2026-03-16T12:08:00Z',
          last_sync_finished_at: null,
          last_sync_error_code: null,
          last_sync_error: null,
          last_sync_progress_percent: 0,
        }
        syncRuns = [
          {
            id: 9,
            site_id: 5,
            competitor_id: 1,
            run_id: 4,
            status: 'queued',
            stage: 'queued',
            trigger_source: 'retry',
            started_at: '2026-03-16T12:08:00Z',
            finished_at: null,
            last_heartbeat_at: '2026-03-16T12:08:00Z',
            lease_expires_at: '2026-03-16T12:08:20Z',
            error_code: null,
            error_message_safe: null,
            summary_json: buildSyncSummary(),
            retry_of_run_id: 3,
            processed_urls: 0,
            url_limit: 400,
            processed_extraction_pages: 0,
            total_extractable_pages: 0,
            progress_percent: 0,
            created_at: '2026-03-16T12:08:00Z',
            updated_at: '2026-03-16T12:08:00Z',
          },
          ...syncRuns,
        ]
        return jsonResponse(competitors[0], { status: 202 })
      }

      if (request.url.includes('/competitive-content-gap/competitors/1/sync-runs')) {
        return jsonResponse(syncRuns)
      }

      if (request.url.includes('/competitive-content-gap/competitors')) {
        return jsonResponse(competitors)
      }

      if (request.url.includes('/competitive-content-gap/review-runs')) {
        return jsonResponse(reviewRunsPayload)
      }

      if (request.url.includes('/competitive-content-gap')) {
        return jsonResponse(gapPayload)
      }

      if (request.url.includes('/sites/5')) {
        return jsonResponse(sitePayload)
      }

      throw new Error(`Unexpected request: ${request.url}`)
    })

    const { user } = renderCompetitiveGap('/sites/5/competitive-gap?active_crawl_id=11&baseline_crawl_id=10')

    expect((await screen.findAllByText('Competitor A')).length).toBeGreaterThan(0)
    expect(screen.getAllByText('Last run: run #3').length).toBeGreaterThan(0)

    await user.click(screen.getByRole('button', { name: 'Show recent runs' }))

    await waitFor(() =>
      expect(
        requestLog.some((entry) =>
          entry.includes('GET http://localhost:8000/sites/5/competitive-content-gap/competitors/1/sync-runs?limit=5'),
        ),
      ).toBe(true),
    )
    expect(await screen.findAllByText('run #3')).not.toHaveLength(0)
    expect(screen.getAllByText('OpenAI request timed out.').length).toBeGreaterThan(0)

    await user.click(screen.getByRole('button', { name: 'Retry sync' }))

    await waitFor(() =>
      expect(
        requestLog.some((entry) =>
          entry.includes('POST http://localhost:8000/sites/5/competitive-content-gap/competitors/1/retry-sync'),
        ),
      ).toBe(true),
    )
    expect(await screen.findByText('Retry queued')).toBeInTheDocument()
    expect(screen.getAllByText('Last run: run #4').length).toBeGreaterThan(0)
  }, 15000)

  test('reruns semantic matching on demand', async () => {
    const requestLog: string[] = []

    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
      const request = input instanceof Request ? input : new Request(typeof input === 'string' ? input : String(input), init)
      requestLog.push(`${request.method} ${request.url}`)

      if (request.url.includes('/competitive-content-gap/semantic/re-run') && request.method === 'POST') {
        const body = (await request.json()) as { mode: string; active_crawl_id?: number }
        expect(body).toEqual({ mode: 'full', active_crawl_id: 11 })
        return jsonResponse({
          site_id: 5,
          mode: 'full',
          active_crawl_id: 11,
          queued_count: 1,
          queued_competitor_ids: [1],
          already_running_competitor_ids: [],
          skipped_competitor_ids: [],
          message: 'Queued semantic matching.',
        })
      }

      if (request.url.includes('/competitive-content-gap/strategy')) {
        return jsonResponse(null)
      }

      if (request.url.includes('/competitive-content-gap/competitors')) {
        return jsonResponse([
          {
            id: 1,
            site_id: 5,
            label: 'Competitor A',
            root_url: 'https://competitor-a.com',
            domain: 'competitor-a.com',
            is_active: true,
            notes: null,
            last_sync_run_id: 4,
            last_sync_status: 'done',
            last_sync_stage: 'done',
            last_sync_started_at: '2026-03-16T12:15:00Z',
            last_sync_finished_at: '2026-03-16T12:16:00Z',
            last_sync_error_code: null,
            last_sync_error: null,
            last_sync_processed_urls: 28,
            last_sync_url_limit: 400,
            last_sync_processed_extraction_pages: 12,
            last_sync_total_extractable_pages: 12,
            last_sync_progress_percent: 100,
            last_sync_summary: buildSyncSummary({
              visited_urls_count: 28,
              stored_pages_count: 12,
              extracted_pages_count: 10,
            }),
            semantic_status: 'ready',
            semantic_analysis_mode: 'llm_only',
            last_semantic_run_started_at: '2026-03-16T12:20:00Z',
            last_semantic_run_finished_at: '2026-03-16T12:22:00Z',
            last_semantic_error: null,
            semantic_candidates_count: 12,
            semantic_llm_jobs_count: 4,
            semantic_resolved_count: 8,
            semantic_cache_hits: 7,
            semantic_fallback_count: 1,
            semantic_llm_merged_urls_count: 3,
            semantic_model: 'gpt-5.4-mini',
            semantic_prompt_version: 'competitive-gap-semantic-v1',
            pages_count: 12,
            extracted_pages_count: 10,
            last_extracted_at: '2026-03-16T12:16:00Z',
            created_at: '2026-03-16T12:00:00Z',
            updated_at: '2026-03-16T12:16:00Z',
          },
        ])
      }

      if (request.url.includes('/competitive-content-gap/review-runs')) {
        return jsonResponse(reviewRunsPayload)
      }

      if (request.url.includes('/competitive-content-gap')) {
        return jsonResponse(gapPayload)
      }

      if (request.url.includes('/sites/5')) {
        return jsonResponse(sitePayload)
      }

      throw new Error(`Unexpected request: ${request.url}`)
    })

    const { user } = renderCompetitiveGap('/sites/5/competitive-gap?active_crawl_id=11&baseline_crawl_id=10')

    expect(await screen.findByRole('button', { name: 'Re-run semantic matching' }, { timeout: 5000 })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Re-run semantic matching' }))

    await waitFor(() =>
      expect(
        requestLog.some((entry) => entry.includes('POST http://localhost:8000/sites/5/competitive-content-gap/semantic/re-run')),
      ).toBe(true),
    )
  }, 10000)

  test('resumes semantic matching incrementally on demand', async () => {
    const requestLog: string[] = []

    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
      const request = input instanceof Request ? input : new Request(typeof input === 'string' ? input : String(input), init)
      requestLog.push(`${request.method} ${request.url}`)

      if (request.url.includes('/competitive-content-gap/semantic/re-run') && request.method === 'POST') {
        const body = (await request.json()) as { mode: string; active_crawl_id?: number }
        expect(body).toEqual({ mode: 'incremental', active_crawl_id: 11 })
        return jsonResponse({
          site_id: 5,
          mode: 'incremental',
          active_crawl_id: 11,
          queued_count: 1,
          queued_competitor_ids: [1],
          already_running_competitor_ids: [],
          skipped_competitor_ids: [],
          message: 'Queued semantic resume.',
        })
      }

      if (request.url.includes('/competitive-content-gap/strategy')) {
        return jsonResponse(null)
      }

      if (request.url.includes('/competitive-content-gap/competitors')) {
        return jsonResponse([
          {
            id: 1,
            site_id: 5,
            label: 'Competitor A',
            root_url: 'https://competitor-a.com',
            domain: 'competitor-a.com',
            is_active: true,
            notes: null,
            last_sync_run_id: 4,
            last_sync_status: 'done',
            last_sync_stage: 'done',
            last_sync_started_at: '2026-03-16T12:15:00Z',
            last_sync_finished_at: '2026-03-16T12:16:00Z',
            last_sync_error_code: null,
            last_sync_error: null,
            last_sync_processed_urls: 28,
            last_sync_url_limit: 400,
            last_sync_processed_extraction_pages: 12,
            last_sync_total_extractable_pages: 12,
            last_sync_progress_percent: 100,
            last_sync_summary: buildSyncSummary({
              visited_urls_count: 28,
              stored_pages_count: 12,
              extracted_pages_count: 10,
            }),
            semantic_status: 'partial',
            semantic_analysis_mode: 'llm_only',
            last_semantic_run_started_at: '2026-03-16T12:20:00Z',
            last_semantic_run_finished_at: '2026-03-16T12:22:00Z',
            last_semantic_error: null,
            semantic_candidates_count: 12,
            semantic_llm_jobs_count: 4,
            semantic_resolved_count: 8,
            semantic_cache_hits: 7,
            semantic_fallback_count: 1,
            semantic_llm_merged_urls_count: 3,
            semantic_model: 'gpt-5.4-mini',
            semantic_prompt_version: 'competitive-gap-semantic-v1',
            pages_count: 12,
            extracted_pages_count: 10,
            last_extracted_at: '2026-03-16T12:16:00Z',
            created_at: '2026-03-16T12:00:00Z',
            updated_at: '2026-03-16T12:16:00Z',
          },
        ])
      }

      if (request.url.includes('/competitive-content-gap/review-runs')) {
        return jsonResponse(reviewRunsPayload)
      }

      if (request.url.includes('/competitive-content-gap')) {
        return jsonResponse(gapPayload)
      }

      if (request.url.includes('/sites/5')) {
        return jsonResponse(sitePayload)
      }

      throw new Error(`Unexpected request: ${request.url}`)
    })

    const { user } = renderCompetitiveGap('/sites/5/competitive-gap?active_crawl_id=11&baseline_crawl_id=10')

    expect(await screen.findByRole('button', { name: 'Resume semantic matching' }, { timeout: 5000 })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Resume semantic matching' }))

    await waitFor(() =>
      expect(
        requestLog.some((entry) => entry.includes('POST http://localhost:8000/sites/5/competitive-content-gap/semantic/re-run')),
      ).toBe(true),
    )
  }, 10000)

  test('shows active semantic runtime diagnostics while a run is in progress', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((input) => {
      const url = typeof input === 'string' ? input : input instanceof Request ? input.url : String(input)
      if (url.includes('/competitive-content-gap/strategy')) {
        return jsonResponse(null)
      }
      if (url.includes('/competitive-content-gap/competitors')) {
        return jsonResponse([
          {
            id: 1,
            site_id: 5,
            label: 'Competitor A',
            root_url: 'https://competitor-a.com',
            domain: 'competitor-a.com',
            is_active: true,
            notes: null,
            last_sync_run_id: 4,
            last_sync_status: 'done',
            last_sync_stage: 'done',
            last_sync_started_at: '2026-03-16T12:15:00Z',
            last_sync_finished_at: '2026-03-16T12:16:00Z',
            last_sync_error_code: null,
            last_sync_error: null,
            last_sync_processed_urls: 28,
            last_sync_url_limit: 400,
            last_sync_processed_extraction_pages: 12,
            last_sync_total_extractable_pages: 12,
            last_sync_progress_percent: 100,
            last_sync_summary: buildSyncSummary({
              visited_urls_count: 28,
              stored_pages_count: 12,
              extracted_pages_count: 10,
            }),
            semantic_status: 'running',
            semantic_analysis_mode: 'llm_only',
            last_semantic_stage: 'merge_topics',
            last_semantic_run_started_at: '2026-03-16T12:20:00Z',
            last_semantic_run_finished_at: null,
            last_semantic_heartbeat_at: '2026-03-16T12:23:30Z',
            last_semantic_lease_expires_at: '2026-03-16T12:28:30Z',
            last_semantic_error: null,
            semantic_candidates_count: 100,
            semantic_run_scope_candidates_count: 20,
            semantic_llm_jobs_count: 9,
            semantic_resolved_count: 14,
            semantic_run_scope_resolved_count: 14,
            semantic_progress_percent: 70,
            semantic_cache_hits: 18,
            semantic_fallback_count: 0,
            semantic_llm_merged_urls_count: 25,
            semantic_model: 'gpt-5.4-mini',
            semantic_prompt_version: 'competitive-gap-semantic-v1',
            pages_count: 12,
            extracted_pages_count: 10,
            last_extracted_at: '2026-03-16T12:16:00Z',
            created_at: '2026-03-16T12:00:00Z',
            updated_at: '2026-03-16T12:16:00Z',
          },
        ])
      }
      if (url.includes('/competitive-content-gap/review-runs')) {
        return jsonResponse(reviewRunsPayload)
      }
      if (url.includes('/competitive-content-gap')) {
        return jsonResponse(gapPayload)
      }
      if (url.includes('/sites/5')) {
        return jsonResponse(sitePayload)
      }
      throw new Error(`Unexpected request: ${url}`)
    })

    renderCompetitiveGap('/sites/5/competitive-gap?active_crawl_id=11&baseline_crawl_id=10')

    expect(await screen.findByText('Semantic merge debug', {}, { timeout: 5000 })).toBeInTheDocument()
    expect(screen.getAllByText('Working').length).toBeGreaterThan(0)
    expect(screen.getByText('Merging competitor topics')).toBeInTheDocument()
    expect(screen.getByText('Semantic matching is still working. If the heartbeat keeps moving, it is safe to wait a bit longer.')).toBeInTheDocument()
    expect(screen.getByText('14 / 20')).toBeInTheDocument()
    expect(screen.getAllByText('70%').length).toBeGreaterThan(0)
    expect(screen.getByText('Last heartbeat')).toBeInTheDocument()
    expect(screen.getByText('Lease expires')).toBeInTheDocument()
  }, 10000)

  test('filters keep state in the query string', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((input) => {
      const url = typeof input === 'string' ? input : input instanceof Request ? input.url : String(input)
      if (url.includes('/competitive-content-gap/strategy')) {
        return jsonResponse(null)
      }
      if (url.includes('/competitive-content-gap/competitors')) {
        return jsonResponse([])
      }
      if (url.includes('/competitive-content-gap/review-runs')) {
        return jsonResponse(reviewRunsPayload)
      }
      if (url.includes('/competitive-content-gap')) {
        return jsonResponse(gapPayload)
      }
      if (url.includes('/sites/5')) {
        return jsonResponse(sitePayload)
      }
      throw new Error(`Unexpected request: ${url}`)
    })

    const { user } = renderCompetitiveGap('/sites/5/competitive-gap?active_crawl_id=11&baseline_crawl_id=10')

    await screen.findByRole('button', { name: 'New topic' }, { timeout: 5000 })
    await user.click(screen.getByRole('button', { name: 'New topic' }))
    await waitFor(() => expect(screen.getByTestId('location-search')).toHaveTextContent('gap_type=NEW_TOPIC'))

    await user.selectOptions(screen.getByLabelText('Recommended page type'), 'service')
    await waitFor(() => expect(screen.getByTestId('location-search')).toHaveTextContent('page_type=service'))

    await user.selectOptions(screen.getByLabelText('Own match status'), 'no_meaningful_match')
    await waitFor(() => expect(screen.getByTestId('location-search')).toHaveTextContent('own_match_status=no_meaningful_match'))

    fireEvent.change(screen.getByLabelText('Topic contains'), { target: { value: 'local' } })
    await waitFor(() => expect(screen.getByTestId('location-search')).toHaveTextContent('topic=local'))
  }, 10000)

  test('saves strategy and creates competitor', async () => {
    const strategyPayload = {
      id: 7,
      site_id: 5,
      raw_user_input: '',
      normalized_strategy_json: null,
      llm_provider: null,
      llm_model: null,
      prompt_version: null,
      normalization_status: 'not_processed',
      last_normalization_attempt_at: null,
      normalization_fallback_used: true,
      normalization_debug_code: 'llm_disabled',
      normalization_debug_message: 'LLM normalization is disabled.',
      normalized_at: null,
      created_at: '2026-03-16T12:00:00Z',
      updated_at: '2026-03-16T12:00:00Z',
    }
    const competitors: Array<Record<string, unknown>> = []
    const requestLog: string[] = []

    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
      const request = input instanceof Request ? input : new Request(typeof input === 'string' ? input : String(input), init)
      requestLog.push(`${request.method} ${request.url}`)

      if (request.url.includes('/competitive-content-gap/strategy') && request.method === 'PUT') {
        const body = (await request.json()) as { raw_user_input: string }
        strategyPayload.raw_user_input = body.raw_user_input
        strategyPayload.normalization_status = 'not_processed'
        strategyPayload.updated_at = '2026-03-16T12:05:00Z'
        return jsonResponse(strategyPayload)
      }
      if (request.url.includes('/competitive-content-gap/strategy')) {
        return jsonResponse(strategyPayload)
      }
      if (request.url.includes('/competitive-content-gap/competitors') && request.method === 'POST') {
        const body = (await request.json()) as { root_url: string; label?: string; notes?: string }
        competitors.push({
          id: 1,
          site_id: 5,
          label: body.label ?? 'competitor-c.com',
          root_url: body.root_url,
          domain: 'competitor-c.com',
          is_active: true,
          notes: body.notes ?? null,
          last_sync_run_id: 0,
          last_sync_status: 'idle',
          last_sync_stage: 'idle',
          last_sync_started_at: null,
          last_sync_finished_at: null,
          last_sync_error_code: null,
          last_sync_error: null,
          last_sync_processed_urls: 0,
          last_sync_url_limit: 400,
          last_sync_processed_extraction_pages: 0,
          last_sync_total_extractable_pages: 0,
          last_sync_progress_percent: 0,
          last_sync_summary: buildSyncSummary(),
          pages_count: 0,
          extracted_pages_count: 0,
          last_extracted_at: null,
          created_at: '2026-03-16T12:00:00Z',
          updated_at: '2026-03-16T12:00:00Z',
        })
        return jsonResponse(competitors[0], { status: 201 })
      }
      if (request.url.includes('/competitive-content-gap/competitors')) {
        return jsonResponse(competitors)
      }
      if (request.url.includes('/competitive-content-gap/review-runs')) {
        return jsonResponse(reviewRunsPayload)
      }
      if (request.url.includes('/competitive-content-gap')) {
        return jsonResponse(gapPayload)
      }
      if (request.url.includes('/sites/5')) {
        return jsonResponse(sitePayload)
      }
      throw new Error(`Unexpected request: ${request.url}`)
    })

    const { user } = renderCompetitiveGap('/sites/5/competitive-gap?active_crawl_id=11&baseline_crawl_id=10')

    await screen.findByLabelText('Competitor root URL', {}, { timeout: 5000 })

    await user.clear(screen.getByLabelText('Strategy notes'))
    await user.type(screen.getByLabelText('Strategy notes'), 'Focus on local SEO growth.')
    await user.click(screen.getByRole('button', { name: 'Save strategy' }))

    await waitFor(() => expect(requestLog.some((entry) => entry.includes('PUT http://localhost:8000/sites/5/competitive-content-gap/strategy'))).toBe(true))

    await user.type(screen.getByLabelText('Competitor root URL'), 'https://competitor-c.com')
    await user.type(screen.getByLabelText('Competitor label'), 'Competitor C')
    await user.click(screen.getByRole('button', { name: 'Add competitor' }))

    await waitFor(() => expect(screen.getAllByText('Competitor C').length).toBeGreaterThan(0))
  }, 15000)

  test('shows a specific empty state when competitors were added but pages are not synced yet', async () => {
    const emptyPayload = createGapPayload({
      items: [],
      total_items: 0,
      context: {
        strategy_present: false,
        empty_state_reason: 'no_competitor_pages',
        data_readiness: {
          has_active_crawl: true,
          has_strategy: false,
          has_active_competitors: true,
          gap_ready: false,
          missing_inputs: ['strategy', 'competitor_pages'],
          active_competitors_count: 1,
          competitors_with_pages_count: 0,
          competitors_with_current_extractions_count: 0,
          total_competitor_pages_count: 0,
          total_current_extractions_count: 0,
        },
      },
      summary: {
        total_gaps: 0,
        high_priority_gaps: 0,
        topics_covered: 0,
      },
    })

    vi.spyOn(globalThis, 'fetch').mockImplementation((input) => {
      const url = typeof input === 'string' ? input : input instanceof Request ? input.url : String(input)
      if (url.includes('/competitive-content-gap/strategy')) {
        return jsonResponse(null)
      }
      if (url.includes('/competitive-content-gap/competitors')) {
        return jsonResponse([
          {
            id: 1,
            site_id: 5,
            label: 'Competitor A',
            root_url: 'https://competitor-a.com',
            domain: 'competitor-a.com',
            is_active: true,
            notes: null,
            last_sync_run_id: 0,
            last_sync_status: 'idle',
            last_sync_stage: 'idle',
            last_sync_started_at: null,
            last_sync_finished_at: null,
            last_sync_error_code: null,
            last_sync_error: null,
            last_sync_processed_urls: 0,
            last_sync_url_limit: 400,
            last_sync_processed_extraction_pages: 0,
            last_sync_total_extractable_pages: 0,
            last_sync_progress_percent: 0,
            last_sync_summary: buildSyncSummary(),
            pages_count: 0,
            extracted_pages_count: 0,
            last_extracted_at: null,
            created_at: '2026-03-16T12:00:00Z',
            updated_at: '2026-03-16T12:00:00Z',
          },
        ])
      }
      if (url.includes('/competitive-content-gap/review-runs')) {
        return jsonResponse(reviewRunsPayload)
      }
      if (url.includes('/competitive-content-gap')) {
        return jsonResponse(emptyPayload)
      }
      if (url.includes('/sites/5')) {
        return jsonResponse(sitePayload)
      }
      throw new Error(`Unexpected request: ${url}`)
    })

    renderCompetitiveGap('/sites/5/competitive-gap?active_crawl_id=11&baseline_crawl_id=10')

    expect(await screen.findByText('Competitors are added, but they have not been synced yet')).toBeInTheDocument()
    expect(screen.getByText('The strategy is optional, but adding it helps explain why a recommendation matches the business direction.')).toBeInTheDocument()
  })

  test('disables sync when a competitor is already queued or running', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((input) => {
      const url = typeof input === 'string' ? input : input instanceof Request ? input.url : String(input)
      if (url.includes('/competitive-content-gap/strategy')) {
        return jsonResponse(null)
      }
      if (url.includes('/competitive-content-gap/competitors')) {
        return jsonResponse([
          {
            id: 1,
            site_id: 5,
            label: 'Competitor A',
            root_url: 'https://competitor-a.com',
            domain: 'competitor-a.com',
            is_active: true,
            notes: null,
            last_sync_run_id: 7,
            last_sync_status: 'running',
            last_sync_stage: 'crawling',
            last_sync_started_at: '2026-03-16T12:20:00Z',
            last_sync_finished_at: null,
            last_sync_error_code: null,
            last_sync_error: null,
            last_sync_processed_urls: 14,
            last_sync_url_limit: 400,
            last_sync_processed_extraction_pages: 0,
            last_sync_total_extractable_pages: 0,
            last_sync_progress_percent: 12,
            last_sync_summary: buildSyncSummary({
              visited_urls_count: 14,
              stored_pages_count: 5,
            }),
            pages_count: 5,
            extracted_pages_count: 0,
            last_extracted_at: null,
            created_at: '2026-03-16T12:00:00Z',
            updated_at: '2026-03-16T12:20:00Z',
          },
        ])
      }
      if (url.includes('/competitive-content-gap/review-runs')) {
        return jsonResponse(reviewRunsPayload)
      }
      if (url.includes('/competitive-content-gap')) {
        return jsonResponse(createGapPayload())
      }
      if (url.includes('/sites/5')) {
        return jsonResponse(sitePayload)
      }
      throw new Error(`Unexpected request: ${url}`)
    })

    renderCompetitiveGap('/sites/5/competitive-gap?active_crawl_id=11&baseline_crawl_id=10')

    const button = await screen.findByRole('button', { name: 'Sync in progress' })
    expect(button).toBeDisabled()
  })

  test('renders the overview subroute with readiness, top recommendations and submenu links', async () => {
    const requestLog: string[] = []

    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
      const request = input instanceof Request ? input : new Request(typeof input === 'string' ? input : String(input), init)
      requestLog.push(`${request.method} ${request.url}`)

      if (request.url.includes('/competitive-content-gap/strategy')) {
        return jsonResponse(null)
      }
      if (request.url.includes('/competitive-content-gap/competitors')) {
        return jsonResponse([])
      }
      if (request.url.includes('/competitive-content-gap/review-runs')) {
        return jsonResponse(reviewRunsPayload)
      }
      if (request.url.includes('/competitive-content-gap')) {
        return jsonResponse(createGapPayload())
      }
      if (request.url.includes('/sites/5')) {
        return jsonResponse(sitePayload)
      }
      throw new Error(`Unexpected request: ${request.url}`)
    })

    renderCompetitiveGapWorkspace('/sites/5/competitive-gap?active_crawl_id=11&baseline_crawl_id=10')

    expect(await screen.findByText('Top 5 content gap recommendations')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Results' })).toHaveAttribute(
      'href',
      '/sites/5/competitive-gap/results?active_crawl_id=11&baseline_crawl_id=10',
    )
    expect(screen.queryByLabelText('Recommended page type')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Competitor root URL')).not.toBeInTheDocument()
    await waitFor(() =>
      expect(
        requestLog.some(
          (entry) =>
            entry.includes('/sites/5/competitive-content-gap?') &&
            entry.includes('page_size=5') &&
            entry.includes('sort_by=priority_score'),
        ),
      ).toBe(true),
    )
  })

  test('renders the strategy brief subroute without loading the full results payload', async () => {
    const requestLog: string[] = []
    const strategyPayload = {
      id: 7,
      site_id: 5,
      raw_user_input: 'Focus on local SEO demand and content strategy.',
      normalized_strategy_json: {
        schema_version: 'competitive_gap_strategy_v1',
        business_summary: 'SEO consultancy focused on local growth.',
        target_audiences: ['local businesses'],
        primary_goals: ['lead generation'],
        priority_topics: ['local seo'],
        supporting_topics: ['technical seo'],
        priority_page_types: ['service'],
        geographic_focus: ['Warsaw'],
        constraints: [],
        differentiation_points: ['manual competitor workflow'],
      },
      llm_provider: 'openai',
      llm_model: 'gpt-5-mini',
      prompt_version: 'competitive-gap-strategy-normalization-v1',
      normalization_status: 'ready',
      last_normalization_attempt_at: '2026-03-16T12:10:00Z',
      normalization_fallback_used: false,
      normalization_debug_code: null,
      normalization_debug_message: 'Strategy normalized successfully.',
      normalized_at: '2026-03-16T12:10:00Z',
      created_at: '2026-03-16T12:00:00Z',
      updated_at: '2026-03-16T12:10:00Z',
    }

    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
      const request = input instanceof Request ? input : new Request(typeof input === 'string' ? input : String(input), init)
      requestLog.push(`${request.method} ${request.url}`)

      if (request.url.includes('/competitive-content-gap/strategy')) {
        return jsonResponse(strategyPayload)
      }
      if (request.url.includes('/competitive-content-gap/competitors')) {
        return jsonResponse([])
      }
      if (request.url.includes('/competitive-content-gap/review-runs')) {
        return jsonResponse(reviewRunsPayload)
      }
      if (request.url.includes('/competitive-content-gap')) {
        throw new Error(`Gap payload should stay disabled on the strategy subroute: ${request.url}`)
      }
      if (request.url.includes('/sites/5')) {
        return jsonResponse(sitePayload)
      }
      throw new Error(`Unexpected request: ${request.url}`)
    })

    renderCompetitiveGapWorkspace('/sites/5/competitive-gap/strategy?active_crawl_id=11&baseline_crawl_id=10')

    expect(await screen.findByLabelText('Strategy notes')).toBeInTheDocument()
    expect(screen.getByText('Normalized hints')).toBeInTheDocument()
    expect(screen.queryByText('Top 5 content gap recommendations')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Recommended page type')).not.toBeInTheDocument()
    expect(requestLog.some((entry) => entry.includes('/sites/5/competitive-content-gap?'))).toBe(false)
  })

  test('renders the synchronization subroute and loads accepted or rejected review details', async () => {
    const competitors = [
      {
        id: 1,
        site_id: 5,
        label: 'Competitor A',
        root_url: 'https://competitor-a.com',
        domain: 'competitor-a.com',
        is_active: true,
        notes: 'Primary local competitor',
        last_sync_run_id: 4,
        last_sync_status: 'done',
        last_sync_stage: 'done',
        last_sync_started_at: '2026-03-16T12:15:00Z',
        last_sync_finished_at: '2026-03-16T12:16:00Z',
        last_sync_error_code: null,
        last_sync_error: null,
        last_sync_processed_urls: 28,
        last_sync_url_limit: 400,
        last_sync_processed_extraction_pages: 8,
        last_sync_total_extractable_pages: 10,
        last_sync_progress_percent: 100,
        last_sync_summary: buildSyncSummary({
          visited_urls_count: 28,
          stored_pages_count: 10,
          extracted_pages_count: 8,
        }),
        semantic_status: 'ready',
        semantic_analysis_mode: 'mixed',
        last_semantic_run_started_at: '2026-03-16T12:20:00Z',
        last_semantic_run_finished_at: '2026-03-16T12:22:00Z',
        last_semantic_error: null,
        semantic_candidates_count: 12,
        semantic_llm_jobs_count: 4,
        semantic_resolved_count: 8,
        semantic_cache_hits: 7,
        semantic_fallback_count: 1,
        semantic_llm_merged_urls_count: 3,
        semantic_model: 'gpt-5.4-mini',
        semantic_prompt_version: 'competitive-gap-semantic-v1',
        pages_count: 10,
        accepted_pages_count: 7,
        rejected_pages_count: 3,
        extracted_pages_count: 8,
        last_extracted_at: '2026-03-16T12:16:00Z',
        created_at: '2026-03-16T12:00:00Z',
        updated_at: '2026-03-16T12:16:00Z',
      },
    ]
    const reviewPayload = {
      site_id: 5,
      competitor_id: 1,
      review_status: 'all',
      summary: {
        total_pages: 10,
        accepted_pages: 7,
        rejected_pages: 3,
        current_extractions_count: 8,
        counts_by_reason: {
          accepted_with_extraction: 6,
          accepted_pending_extraction: 1,
          weak_about: 2,
          non_indexable: 1,
        },
      },
      items: [
        {
          id: 501,
          url: 'https://competitor-a.com/about',
          normalized_url: 'https://competitor-a.com/about',
          final_url: 'https://competitor-a.com/about',
          status_code: 200,
          title: 'About the clinic',
          meta_description: 'Meet the team behind the clinic.',
          h1: 'About our clinic',
          page_type: 'about',
          page_bucket: 'trust',
          page_type_confidence: 0.91,
          semantic_eligible: false,
          semantic_exclusion_reason: 'weak_about',
          review_status: 'rejected',
          review_reason_code: 'weak_about',
          review_reason_detail: 'Rejected before extraction: exclusion_reason=weak_about. weak_evidence_reason=about.',
          has_current_extraction: false,
          current_extraction_topic_label: null,
          current_extraction_confidence: null,
          last_extracted_at: null,
          diagnostics: {
            weak_evidence_flag: true,
            weak_evidence_reason: 'about',
            dominant_topic_strength: 0.18,
          },
          fetched_at: '2026-03-16T12:16:00Z',
          updated_at: '2026-03-16T12:16:00Z',
        },
      ],
      page: 1,
      page_size: 20,
      total_items: 1,
      total_pages: 1,
    }

    vi.spyOn(globalThis, 'fetch').mockImplementation((input) => {
      const url = typeof input === 'string' ? input : input instanceof Request ? input.url : String(input)
      if (url.includes('/competitive-content-gap/competitors/1/page-review')) {
        return jsonResponse(reviewPayload)
      }
      if (url.includes('/competitive-content-gap/strategy')) {
        return jsonResponse(null)
      }
      if (url.includes('/competitive-content-gap/review-runs')) {
        return jsonResponse(reviewRunsPayload)
      }
      if (url.includes('/competitive-content-gap/competitors')) {
        return jsonResponse(competitors)
      }
      if (url.includes('/competitive-content-gap')) {
        return jsonResponse(createGapPayload())
      }
      if (url.includes('/sites/5')) {
        return jsonResponse(sitePayload)
      }
      throw new Error(`Unexpected request: ${url}`)
    })

    const { user } = renderCompetitiveGapWorkspace('/sites/5/competitive-gap/sync?active_crawl_id=11&baseline_crawl_id=10')

    expect(await screen.findByText('Synchronization')).toBeInTheDocument()
    expect(screen.getByText('Accepted: 7')).toBeInTheDocument()
    expect(screen.getByText('Rejected: 3')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Show URL review' }))
    expect(await screen.findByText('Rejected before extraction: exclusion_reason=weak_about. weak_evidence_reason=about.')).toBeInTheDocument()
    expect(screen.getByText('weak_evidence_reason=about')).toBeInTheDocument()
    expect(screen.queryByLabelText('Recommended page type')).not.toBeInTheDocument()
  })

  test('renders the competitor selection subroute as a lighter management view', async () => {
    const competitors = [
      {
        id: 1,
        site_id: 5,
        label: 'Competitor A',
        root_url: 'https://competitor-a.com',
        domain: 'competitor-a.com',
        is_active: true,
        notes: 'Primary local competitor',
        last_sync_run_id: 4,
        last_sync_status: 'done',
        last_sync_stage: 'done',
        last_sync_started_at: '2026-03-16T12:15:00Z',
        last_sync_finished_at: '2026-03-16T12:16:00Z',
        last_sync_error_code: null,
        last_sync_error: null,
        last_sync_processed_urls: 28,
        last_sync_url_limit: 400,
        last_sync_processed_extraction_pages: 8,
        last_sync_total_extractable_pages: 10,
        last_sync_progress_percent: 100,
        last_sync_summary: buildSyncSummary({
          visited_urls_count: 28,
          stored_pages_count: 10,
          extracted_pages_count: 8,
        }),
        semantic_status: 'ready',
        semantic_analysis_mode: 'mixed',
        last_semantic_run_started_at: '2026-03-16T12:20:00Z',
        last_semantic_run_finished_at: '2026-03-16T12:22:00Z',
        last_semantic_error: null,
        semantic_candidates_count: 12,
        semantic_llm_jobs_count: 4,
        semantic_resolved_count: 8,
        semantic_cache_hits: 7,
        semantic_fallback_count: 1,
        semantic_llm_merged_urls_count: 3,
        semantic_model: 'gpt-5.4-mini',
        semantic_prompt_version: 'competitive-gap-semantic-v1',
        pages_count: 10,
        accepted_pages_count: 7,
        rejected_pages_count: 3,
        extracted_pages_count: 8,
        last_extracted_at: '2026-03-16T12:16:00Z',
        created_at: '2026-03-16T12:00:00Z',
        updated_at: '2026-03-16T12:16:00Z',
      },
    ]

    vi.spyOn(globalThis, 'fetch').mockImplementation((input) => {
      const url = typeof input === 'string' ? input : input instanceof Request ? input.url : String(input)
      if (url.includes('/competitive-content-gap/strategy')) {
        return jsonResponse(null)
      }
      if (url.includes('/competitive-content-gap/competitors')) {
        return jsonResponse(competitors)
      }
      if (url.includes('/competitive-content-gap')) {
        throw new Error(`Gap payload should stay disabled on the competitor management subroute: ${url}`)
      }
      if (url.includes('/sites/5')) {
        return jsonResponse(sitePayload)
      }
      throw new Error(`Unexpected request: ${url}`)
    })

    renderCompetitiveGapWorkspace('/sites/5/competitive-gap/competitors?active_crawl_id=11&baseline_crawl_id=10')

    expect(await screen.findByLabelText('Competitor root URL')).toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: 'Open synchronization' }).length).toBeGreaterThan(0)
    expect(screen.queryByRole('button', { name: 'Show URL review' })).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Recommended page type')).not.toBeInTheDocument()
  })

  test('shows reviewed source mode and minimal review fields on the main gap view', async () => {
    const reviewedPayload = createGapPayload({
      context: {
        data_source_mode: 'reviewed',
        review_run_status: 'completed',
      },
      items: [
        {
          ...gapPayload.items[0],
          decision_action: 'rewrite',
          reviewed_phrase: 'Local SEO consulting',
          fit_score: 88,
        },
        {
          ...gapPayload.items[1],
          decision_action: 'merge',
          merge_target_phrase: 'Local SEO consulting',
        },
      ],
    })

    vi.spyOn(globalThis, 'fetch').mockImplementation((input) => {
      const url = typeof input === 'string' ? input : input instanceof Request ? input.url : String(input)
      if (url.includes('/competitive-content-gap/strategy')) {
        return jsonResponse(null)
      }
      if (url.includes('/competitive-content-gap/competitors')) {
        return jsonResponse([])
      }
      if (url.includes('/competitive-content-gap/review-runs')) {
        return jsonResponse(reviewRunsPayload)
      }
      if (url.includes('/competitive-content-gap')) {
        return jsonResponse(reviewedPayload)
      }
      if (url.includes('/sites/5')) {
        return jsonResponse(sitePayload)
      }
      throw new Error(`Unexpected request: ${url}`)
    })

    renderCompetitiveGap('/sites/5/competitive-gap?active_crawl_id=11&baseline_crawl_id=10')

    expect(await screen.findByText('Source: Reviewed')).toBeInTheDocument()
    expect(screen.getByText('Review run: completed')).toBeInTheDocument()
    expect(screen.getByText('Rewrite')).toBeInTheDocument()
    expect(screen.getByText('Fit 88/100')).toBeInTheDocument()
    expect(
      screen.getAllByText((_, node) => node?.textContent === 'Reviewed phrase: Local SEO consulting').length,
    ).toBeGreaterThan(0)
    expect(
      screen.getAllByText((_, node) => node?.textContent === 'Merge target: Local SEO consulting').length,
    ).toBeGreaterThan(0)
  })

  test('shows raw candidates source mode and outdated fallback message when the active crawl changed', async () => {
    const rawPayload = createGapPayload({
      context: {
        data_source_mode: 'raw_candidates',
        basis_crawl_job_id: 10,
        active_crawl_id: 11,
        is_outdated_for_active_crawl: true,
        review_run_status: 'failed',
      },
      items: [
        {
          ...gapPayload.items[0],
          decision_action: 'remove',
          remove_reason_text: 'Too broad for the current site focus.',
        },
      ],
    })

    vi.spyOn(globalThis, 'fetch').mockImplementation((input) => {
      const url = typeof input === 'string' ? input : input instanceof Request ? input.url : String(input)
      if (url.includes('/competitive-content-gap/strategy')) {
        return jsonResponse(null)
      }
      if (url.includes('/competitive-content-gap/competitors')) {
        return jsonResponse([])
      }
      if (url.includes('/competitive-content-gap/review-runs')) {
        return jsonResponse(reviewRunsPayload)
      }
      if (url.includes('/competitive-content-gap')) {
        return jsonResponse(rawPayload)
      }
      if (url.includes('/sites/5')) {
        return jsonResponse(sitePayload)
      }
      throw new Error(`Unexpected request: ${url}`)
    })

    renderCompetitiveGap('/sites/5/competitive-gap?active_crawl_id=11&baseline_crawl_id=10')

    expect(await screen.findByText('Source: Raw candidates')).toBeInTheDocument()
    expect(screen.getByText('Review data is not current for the active crawl')).toBeInTheDocument()
    expect(
      screen.getByText(
        'These reviewed or raw records were generated for crawl #10. The current view is using a safe fallback for active crawl #11.',
      ),
    ).toBeInTheDocument()
    expect(screen.getByText('Remove')).toBeInTheDocument()
    expect(
      screen.getAllByText((_, node) => node?.textContent === 'Remove reason: Too broad for the current site focus.').length,
    ).toBeGreaterThan(0)
  })

  test('keeps rendering the legacy payload without review metadata regressions', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((input) => {
      const url = typeof input === 'string' ? input : input instanceof Request ? input.url : String(input)
      if (url.includes('/competitive-content-gap/strategy')) {
        return jsonResponse(null)
      }
      if (url.includes('/competitive-content-gap/competitors')) {
        return jsonResponse([])
      }
      if (url.includes('/competitive-content-gap/review-runs')) {
        return jsonResponse(reviewRunsPayload)
      }
      if (url.includes('/competitive-content-gap')) {
        return jsonResponse(createGapPayload({ context: { data_source_mode: 'legacy', review_run_status: null } }))
      }
      if (url.includes('/sites/5')) {
        return jsonResponse(sitePayload)
      }
      throw new Error(`Unexpected request: ${url}`)
    })

    renderCompetitiveGap('/sites/5/competitive-gap?active_crawl_id=11&baseline_crawl_id=10')

    expect(await screen.findByText('Source: Legacy fallback')).toBeInTheDocument()
    expect(screen.getByText('Local SEO')).toBeInTheDocument()
    expect(screen.queryByText(/Reviewed phrase:/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Remove reason:/)).not.toBeInTheDocument()
  })

  test('shows recent review runs with latest status for the active crawl', async () => {
    const recentRuns: SiteContentGapReviewRun[] = [
      {
        id: 21,
        site_id: 5,
        basis_crawl_job_id: 11,
        run_id: 3,
        status: 'completed',
        stage: 'finalize',
        trigger_source: 'manual_ui',
        scope_type: 'all_current',
        selected_candidate_ids_json: [101, 102],
        candidate_count: 2,
        candidate_set_hash: 'candidate-hash-3',
        candidate_generation_version: 'v1',
        own_context_hash: 'own-hash-3',
        gsc_context_hash: 'gsc-hash-3',
        context_summary_json: {},
        output_language: 'en',
        llm_provider: 'openai',
        llm_model: 'gpt-5-mini',
        prompt_version: 'content-gap-review-v1',
        schema_version: 'content-gap-review-schema-v1',
        batch_size: 5,
        batch_count: 1,
        completed_batch_count: 1,
        lease_owner: null,
        lease_expires_at: null,
        last_heartbeat_at: '2026-03-18T10:05:00Z',
        started_at: '2026-03-18T10:00:00Z',
        finished_at: '2026-03-18T10:06:00Z',
        error_code: null,
        error_message_safe: null,
        retry_of_run_id: null,
        created_at: '2026-03-18T10:00:00Z',
        updated_at: '2026-03-18T10:06:00Z',
      },
      {
        id: 20,
        site_id: 5,
        basis_crawl_job_id: 10,
        run_id: 2,
        status: 'failed',
        stage: 'prepare_context',
        trigger_source: 'manual_ui',
        scope_type: 'all_current',
        selected_candidate_ids_json: [99],
        candidate_count: 1,
        candidate_set_hash: 'candidate-hash-2',
        candidate_generation_version: 'v1',
        own_context_hash: 'own-hash-2',
        gsc_context_hash: null,
        context_summary_json: {},
        output_language: 'en',
        llm_provider: 'openai',
        llm_model: 'gpt-5-mini',
        prompt_version: 'content-gap-review-v1',
        schema_version: 'content-gap-review-schema-v1',
        batch_size: 5,
        batch_count: 1,
        completed_batch_count: 0,
        lease_owner: null,
        lease_expires_at: null,
        last_heartbeat_at: null,
        started_at: '2026-03-17T09:00:00Z',
        finished_at: '2026-03-17T09:01:00Z',
        error_code: 'model_error',
        error_message_safe: 'The run failed before completion.',
        retry_of_run_id: null,
        created_at: '2026-03-17T09:00:00Z',
        updated_at: '2026-03-17T09:01:00Z',
      },
    ]

    vi.spyOn(globalThis, 'fetch').mockImplementation((input) => {
      const url = typeof input === 'string' ? input : input instanceof Request ? input.url : String(input)
      if (url.includes('/competitive-content-gap/strategy')) {
        return jsonResponse(null)
      }
      if (url.includes('/competitive-content-gap/competitors')) {
        return jsonResponse([])
      }
      if (url.includes('/competitive-content-gap/review-runs')) {
        return jsonResponse(recentRuns)
      }
      if (url.includes('/competitive-content-gap')) {
        return jsonResponse(createGapPayload({ context: { data_source_mode: 'reviewed', review_run_status: 'completed' } }))
      }
      if (url.includes('/sites/5')) {
        return jsonResponse(sitePayload)
      }
      throw new Error(`Unexpected request: ${url}`)
    })

    renderCompetitiveGap('/sites/5/competitive-gap?active_crawl_id=11&baseline_crawl_id=10')

    expect(await screen.findByText('Content Gap review runs')).toBeInTheDocument()
    expect(await screen.findByText('Status: completed')).toBeInTheDocument()
    expect(await screen.findByText('Snapshot #11')).toBeInTheDocument()
    expect(await screen.findByText('Snapshot #10')).toBeInTheDocument()
    expect(
      await screen.findByText('This run belongs to crawl #10, so retry stays disabled for the current active snapshot.'),
    ).toBeInTheDocument()
  })

  test('allows retry for failed current-snapshot review runs and blocks it for outdated ones in the UI', async () => {
    const recentRuns: SiteContentGapReviewRun[] = [
      {
        id: 31,
        site_id: 5,
        basis_crawl_job_id: 11,
        run_id: 6,
        status: 'failed',
        stage: 'finalize',
        trigger_source: 'manual_ui',
        scope_type: 'all_current',
        selected_candidate_ids_json: [101],
        candidate_count: 1,
        candidate_set_hash: 'candidate-hash-6',
        candidate_generation_version: 'v1',
        own_context_hash: 'own-hash-6',
        gsc_context_hash: 'gsc-hash-6',
        context_summary_json: {},
        output_language: 'en',
        llm_provider: 'openai',
        llm_model: 'gpt-5-mini',
        prompt_version: 'content-gap-review-v1',
        schema_version: 'content-gap-review-schema-v1',
        batch_size: 5,
        batch_count: 1,
        completed_batch_count: 0,
        lease_owner: null,
        lease_expires_at: null,
        last_heartbeat_at: null,
        started_at: '2026-03-19T10:00:00Z',
        finished_at: '2026-03-19T10:01:00Z',
        error_code: 'model_error',
        error_message_safe: 'The run failed before completion.',
        retry_of_run_id: null,
        created_at: '2026-03-19T10:00:00Z',
        updated_at: '2026-03-19T10:01:00Z',
      },
      {
        id: 30,
        site_id: 5,
        basis_crawl_job_id: 10,
        run_id: 5,
        status: 'stale',
        stage: 'prepare_context',
        trigger_source: 'manual_ui',
        scope_type: 'all_current',
        selected_candidate_ids_json: [88],
        candidate_count: 1,
        candidate_set_hash: 'candidate-hash-5',
        candidate_generation_version: 'v1',
        own_context_hash: 'own-hash-5',
        gsc_context_hash: null,
        context_summary_json: {},
        output_language: 'en',
        llm_provider: 'openai',
        llm_model: 'gpt-5-mini',
        prompt_version: 'content-gap-review-v1',
        schema_version: 'content-gap-review-schema-v1',
        batch_size: 5,
        batch_count: 1,
        completed_batch_count: 0,
        lease_owner: null,
        lease_expires_at: null,
        last_heartbeat_at: null,
        started_at: '2026-03-18T10:00:00Z',
        finished_at: null,
        error_code: null,
        error_message_safe: null,
        retry_of_run_id: null,
        created_at: '2026-03-18T10:00:00Z',
        updated_at: '2026-03-18T10:05:00Z',
      },
    ]
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementation((input, init) => {
      const request = input instanceof Request ? input : new Request(typeof input === 'string' ? input : String(input), init)
      if (request.url.includes('/competitive-content-gap/strategy')) {
        return Promise.resolve(jsonResponse(null))
      }
      if (request.url.includes('/competitive-content-gap/competitors')) {
        return Promise.resolve(jsonResponse([]))
      }
      if (request.url.includes('/competitive-content-gap/review-runs/6/retry') && request.method === 'POST') {
        return Promise.resolve(
          jsonResponse({
            ...recentRuns[0],
            id: 32,
            run_id: 7,
            status: 'queued',
            stage: 'prepare_context',
            retry_of_run_id: 6,
            created_at: '2026-03-19T10:05:00Z',
            updated_at: '2026-03-19T10:05:00Z',
          }),
        )
      }
      if (request.url.includes('/competitive-content-gap/review-runs')) {
        return Promise.resolve(jsonResponse(recentRuns))
      }
      if (request.url.includes('/competitive-content-gap')) {
        return Promise.resolve(
          jsonResponse(createGapPayload({ context: { data_source_mode: 'reviewed', review_run_status: 'failed' } })),
        )
      }
      if (request.url.includes('/sites/5')) {
        return Promise.resolve(jsonResponse(sitePayload))
      }
      return Promise.reject(new Error(`Unexpected request: ${request.url}`))
    })

    const { user } = renderCompetitiveGap('/sites/5/competitive-gap?active_crawl_id=11&baseline_crawl_id=10')

    expect(await screen.findByText('Run #6')).toBeInTheDocument()
    const retryButtons = screen.getAllByRole('button', { name: 'Retry review' })
    expect(retryButtons).toHaveLength(1)

    await user.click(retryButtons[0])

    await waitFor(() =>
      expect(
        fetchSpy.mock.calls.some(([input, init]) => {
          const request = input instanceof Request ? input : new Request(typeof input === 'string' ? input : String(input), init)
          return request.url.includes('/competitive-content-gap/review-runs/6/retry') && request.method === 'POST'
        }),
      ).toBe(true),
    )
    expect(screen.queryAllByRole('button', { name: 'Retry review' })).toHaveLength(1)
  })

  test('renders the results subroute with filters, list and pagination controls', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((input) => {
      const url = typeof input === 'string' ? input : input instanceof Request ? input.url : String(input)
      if (url.includes('/competitive-content-gap/strategy')) {
        return jsonResponse(null)
      }
      if (url.includes('/competitive-content-gap/competitors')) {
        return jsonResponse([])
      }
      if (url.includes('/competitive-content-gap/review-runs')) {
        return jsonResponse(reviewRunsPayload)
      }
      if (url.includes('/competitive-content-gap')) {
        return jsonResponse(createGapPayload())
      }
      if (url.includes('/sites/5')) {
        return jsonResponse(sitePayload)
      }
      throw new Error(`Unexpected request: ${url}`)
    })

    renderCompetitiveGapWorkspace('/sites/5/competitive-gap/results?active_crawl_id=11&baseline_crawl_id=10')

    expect(await screen.findByLabelText('Recommended page type')).toBeInTheDocument()
    expect(screen.getByText('Cluster quality')).toBeInTheDocument()
    expect(screen.getByText('Canonicalization')).toBeInTheDocument()
    expect(screen.queryByText('Top 5 content gap recommendations')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Competitor root URL')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Strategy notes')).not.toBeInTheDocument()
  })
})
