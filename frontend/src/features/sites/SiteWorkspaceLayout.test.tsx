import { QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'
import { I18nextProvider } from 'react-i18next'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { afterEach, describe, expect, test, vi } from 'vitest'

import i18n from '../../i18n'
import { createTestQueryClient, jsonResponse } from '../../test/testUtils'
import { formatCrawlDateTime, formatCrawlOptionLabel } from '../../utils/format'
import { SiteAuditComparePage } from '../audit/SiteAuditComparePage'
import { SiteAuditOverviewPage, SiteAuditSectionsPage } from '../audit/SiteAuditWorkspacePage'
import { SiteContentRecommendationsPage } from '../content-recommendations/SiteContentRecommendationsPage'
import { SiteCompetitiveGapPage } from '../competitive-gap/SiteCompetitiveGapPage'
import { SiteGscPage } from '../gsc/SiteGscPage'
import { SiteInternalLinkingCurrentPage } from '../internal-linking/SiteInternalLinkingCurrentPage'
import { SiteInternalLinkingComparePage } from '../internal-linking/SiteInternalLinkingComparePage'
import { SiteOpportunitiesCurrentPage } from '../opportunities/SiteOpportunitiesCurrentPage'
import { SiteOpportunitiesComparePage } from '../opportunities/SiteOpportunitiesComparePage'
import { SitePagesComparePage } from '../pages/SitePagesComparePage'
import { SitePagesOverviewPage } from '../pages/SitePagesOverviewPage'
import { SitePagesRecordsPage } from '../pages/SitePagesRecordsPage'
import { SiteCrawlsPage } from './SiteCrawlsPage'
import { SiteChangesHubPage } from './SiteChangesHubPage'
import { SiteNewCrawlPage } from './SiteNewCrawlPage'
import { SiteOverviewPage } from './SiteOverviewPage'
import { SiteProgressPage } from './SiteProgressPage'
import { SiteWorkspaceLayout } from './SiteWorkspaceLayout'

afterEach(() => {
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
    running_crawls: 1,
    finished_crawls: 1,
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
    status: 'running',
    created_at: '2026-03-14T12:00:00Z',
    started_at: '2026-03-14T12:01:00Z',
    finished_at: null,
    settings_json: {
      start_url: 'https://example.com',
      max_urls: 500,
      max_depth: 3,
      delay: 0.25,
      request_delay: 0.25,
      render_mode: 'auto',
      render_timeout_ms: 8000,
      max_rendered_pages_per_job: 25,
    },
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
      queued_urls: 12,
      discovered_links: 280,
      internal_links: 210,
      external_links: 70,
      errors_count: 2,
    },
  },
  baseline_crawl: {
    id: 10,
    site_id: 5,
    status: 'finished',
    created_at: '2026-03-13T12:00:00Z',
    started_at: '2026-03-13T12:01:00Z',
    finished_at: '2026-03-13T12:08:00Z',
    settings_json: {
      start_url: 'https://example.com',
      max_urls: 500,
      max_depth: 3,
      delay: 0.25,
      request_delay: 0.25,
      render_mode: 'auto',
      render_timeout_ms: 8000,
      max_rendered_pages_per_job: 25,
    },
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
      errors_count: 1,
    },
  },
  crawl_history: [
    {
      id: 11,
      site_id: 5,
      status: 'running',
      root_url: 'https://example.com',
      created_at: '2026-03-14T12:00:00Z',
      started_at: '2026-03-14T12:01:00Z',
      finished_at: null,
      total_pages: 42,
      total_internal_links: 210,
      total_external_links: 70,
      total_errors: 1,
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
      total_errors: 2,
    },
  ],
}

const sitePagesComparePayload = {
  context: {
    site_id: 5,
    site_domain: 'example.com',
    active_crawl_id: 11,
    baseline_crawl_id: 10,
    compare_available: true,
    compare_unavailable_reason: null,
    gsc_date_range: 'last_28_days',
    active_crawl: {
      id: 11,
      status: 'running',
      created_at: '2026-03-14T12:00:00Z',
      started_at: '2026-03-14T12:01:00Z',
      finished_at: null,
      root_url: 'https://example.com',
    },
    baseline_crawl: {
      id: 10,
      status: 'finished',
      created_at: '2026-03-13T12:00:00Z',
      started_at: '2026-03-13T12:01:00Z',
      finished_at: '2026-03-13T12:08:00Z',
      root_url: 'https://example.com',
    },
  },
  gsc_date_range: 'last_28_days',
  summary: {
    active_urls: 42,
    baseline_urls: 40,
    shared_urls: 38,
    new_urls: 4,
    missing_urls: 2,
    changed_urls: 10,
    improved_urls: 6,
    worsened_urls: 3,
    unchanged_urls: 29,
    status_changed_urls: 2,
    title_changed_urls: 3,
    meta_description_changed_urls: 2,
    h1_changed_urls: 1,
    canonical_changed_urls: 0,
    noindex_changed_urls: 1,
    priority_improved_urls: 3,
    priority_worsened_urls: 1,
    internal_linking_improved_urls: 2,
    internal_linking_worsened_urls: 1,
    content_growth_urls: 4,
    content_drop_urls: 1,
  },
  items: [],
  page: 1,
  page_size: 1,
  total_items: 0,
  total_pages: 0,
}

const siteAuditComparePayload = {
  context: sitePagesComparePayload.context,
  summary: {
    total_sections: 12,
    resolved_sections: 3,
    new_sections: 1,
    improved_sections: 2,
    worsened_sections: 1,
    unchanged_sections: 5,
    resolved_issues_total: 4,
    new_issues_total: 2,
    active_issues_total: 11,
    baseline_issues_total: 13,
  },
  sections: [],
}

const sitePagesCurrentPayload = {
  items: [
    {
      id: 101,
      crawl_job_id: 11,
      url: 'https://example.com/blog/alpha',
      normalized_url: 'https://example.com/blog/alpha',
      final_url: 'https://example.com/blog/alpha',
      status_code: 200,
      title: 'Alpha',
      title_length: 42,
      meta_description: 'Alpha meta',
      meta_description_length: 96,
      h1: 'Alpha heading',
      h1_length: 13,
      h1_count: 1,
      h2_count: 2,
      canonical_url: 'https://example.com/blog/alpha',
      canonical_target_url: 'https://example.com/blog/alpha',
      canonical_target_status_code: 200,
      robots_meta: 'index,follow',
      x_robots_tag: null,
      content_type: 'text/html',
      word_count: 320,
      content_text_hash: 'hash-alpha',
      images_count: 4,
      images_missing_alt_count: 1,
      html_size_bytes: 2048,
      was_rendered: true,
      render_attempted: true,
      fetch_mode_used: 'playwright',
      js_heavy_like: true,
      render_reason: 'low_text_many_scripts(words=1,scripts=6,links=0)',
      render_error_message: null,
      schema_present: true,
      schema_count: 2,
      schema_types_json: ['Article', 'BreadcrumbList'],
      schema_types_text: 'Article, BreadcrumbList',
      page_type: 'blog_article',
      page_bucket: 'informational',
      page_type_confidence: 0.94,
      page_type_version: '11.1-v1',
      page_type_rationale: 'schema:article(+7.0) | path:first_segment:blog(+5.5)',
      has_render_error: false,
      has_x_robots_tag: false,
      response_time_ms: 44,
      is_internal: true,
      depth: 1,
      fetched_at: '2026-03-13T12:00:00Z',
      error_message: null,
      title_missing: false,
      meta_description_missing: false,
      h1_missing: false,
      title_too_short: true,
      title_too_long: false,
      meta_description_too_short: false,
      meta_description_too_long: false,
      multiple_h1: false,
      missing_h2: false,
      canonical_missing: false,
      self_canonical: true,
      canonical_to_other_url: false,
      canonical_to_non_200: false,
      canonical_to_redirect: false,
      noindex_like: false,
      non_indexable_like: false,
      thin_content: false,
      duplicate_title: false,
      duplicate_meta_description: false,
      duplicate_content: false,
      missing_alt_images: true,
      no_images: false,
      oversized: false,
      clicks_28d: 12,
      impressions_28d: 340,
      ctr_28d: 0.0353,
      position_28d: 8.4,
      gsc_fetched_at_28d: '2026-03-13T12:00:00Z',
      top_queries_count_28d: 6,
      has_gsc_28d: true,
      clicks_90d: 30,
      impressions_90d: 920,
      ctr_90d: 0.0326,
      position_90d: 9.1,
      gsc_fetched_at_90d: '2026-03-13T12:00:00Z',
      top_queries_count_90d: 14,
      has_gsc_90d: true,
      has_technical_issue: true,
      technical_issue_count: 2,
      incoming_internal_links: 6,
      incoming_internal_linking_pages: 3,
      priority_score: 68,
      priority_level: 'high',
      priority_rationale: 'URL has high impressions and low CTR with snippet issues.',
      traffic_component: 22,
      issue_component: 4,
      opportunity_component: 20,
      internal_linking_component: 0,
      opportunity_count: 3,
      primary_opportunity_type: 'HIGH_IMPRESSIONS_LOW_CTR',
      opportunity_types: ['QUICK_WINS', 'HIGH_IMPRESSIONS_LOW_CTR', 'LOW_HANGING_FRUIT'],
      has_cannibalization: true,
      cannibalization_cluster_id: 'cannibalization-3-1',
      cannibalization_severity: 'high',
      cannibalization_impact_level: 'medium',
      cannibalization_recommendation_type: 'MERGE_CANDIDATE',
      cannibalization_rationale: 'Two URLs overlap on the same commercial query set.',
      cannibalization_competing_urls_count: 1,
      cannibalization_strongest_competing_url: 'https://example.com/blog/beta',
      cannibalization_strongest_competing_page_id: 102,
      cannibalization_dominant_competing_url: 'https://example.com/blog/beta',
      cannibalization_dominant_competing_page_id: 102,
      cannibalization_common_queries_count: 2,
      cannibalization_weighted_overlap_by_impressions: 0.62,
      cannibalization_weighted_overlap_by_clicks: 0.58,
      cannibalization_overlap_ratio: 0.67,
      cannibalization_overlap_strength: 0.64,
      cannibalization_shared_top_queries: ['alpha query', 'alpha guide'],
      created_at: '2026-03-13T12:00:00Z',
    },
  ],
  page: 1,
  page_size: 8,
  total_items: 1,
  total_pages: 1,
  available_status_codes: [200],
  has_gsc_integration: true,
}

const pageTaxonomySummaryPayload = {
  crawl_job_id: 11,
  page_type_version: '11.1-v1',
  total_pages: 42,
  classified_pages: 42,
  counts_by_page_type: {
    home: 1,
    category: 2,
    product: 3,
    service: 1,
    blog_article: 12,
    blog_index: 1,
    contact: 1,
    about: 0,
    faq: 0,
    location: 0,
    legal: 0,
    utility: 1,
    other: 21,
  },
  counts_by_page_bucket: {
    commercial: 12,
    informational: 20,
    utility: 4,
    trust: 3,
    other: 3,
  },
}

const siteAuditCurrentPayload = {
  crawl_job_id: 11,
  summary: {
    total_pages: 42,
    pages_missing_title: 1,
    pages_title_too_short: 0,
    pages_title_too_long: 0,
    pages_missing_meta_description: 1,
    pages_meta_description_too_short: 0,
    pages_meta_description_too_long: 0,
    pages_missing_h1: 0,
    pages_multiple_h1: 0,
    pages_missing_h2: 0,
    pages_missing_canonical: 0,
    pages_self_canonical: 1,
    pages_canonical_to_other_url: 0,
    pages_canonical_to_non_200: 0,
    pages_canonical_to_redirect: 0,
    pages_noindex_like: 0,
    pages_non_indexable_like: 0,
    pages_duplicate_title_groups: 0,
    pages_duplicate_meta_description_groups: 0,
    pages_thin_content: 0,
    pages_duplicate_content_groups: 0,
    pages_with_missing_alt_images: 1,
    pages_with_no_images: 0,
    oversized_pages: 0,
    js_heavy_like_pages: 1,
    rendered_pages: 1,
    pages_with_render_errors: 0,
    pages_with_schema: 1,
    pages_missing_schema: 41,
    pages_with_x_robots_tag: 0,
    pages_with_schema_types_summary: 1,
    broken_internal_links: 1,
    unresolved_internal_targets: 0,
    redirecting_internal_links: 0,
    internal_links_to_noindex_like_pages: 0,
    internal_links_to_canonicalized_pages: 0,
    redirect_chains_internal: 0,
  },
  pages_missing_title: [
    {
      page_id: 1,
      url: 'https://example.com/no-title',
      normalized_url: 'https://example.com/no-title',
      final_url: 'https://example.com/no-title',
      status_code: 200,
      title: null,
      title_length: null,
      meta_description: null,
      meta_description_length: null,
      h1: null,
      h1_length: null,
      h1_count: null,
      h2_count: null,
      canonical_url: null,
      canonical_target_url: null,
      canonical_target_status_code: null,
      robots_meta: null,
      x_robots_tag: null,
      content_type: null,
      word_count: null,
      content_text_hash: null,
      images_count: null,
      images_missing_alt_count: null,
      html_size_bytes: null,
      was_rendered: false,
      render_attempted: false,
      fetch_mode_used: null,
      js_heavy_like: false,
      render_reason: null,
      render_error_message: null,
      schema_present: false,
      schema_count: null,
      schema_types_json: null,
      schema_types_text: '',
      page_type: 'other',
      page_bucket: 'other',
      page_type_confidence: 0,
      page_type_version: 'v1',
      page_type_rationale: null,
      has_render_error: false,
      has_x_robots_tag: false,
      response_time_ms: null,
      is_internal: true,
      depth: 1,
      fetched_at: null,
      error_message: null,
      title_missing: true,
      meta_description_missing: true,
      h1_missing: true,
      title_too_short: false,
      title_too_long: false,
      meta_description_too_short: false,
      meta_description_too_long: false,
      multiple_h1: false,
      missing_h2: false,
      canonical_missing: true,
      self_canonical: false,
      canonical_to_other_url: false,
      canonical_to_non_200: false,
      canonical_to_redirect: false,
      noindex_like: false,
      non_indexable_like: false,
      thin_content: false,
      duplicate_title: false,
      duplicate_meta_description: false,
      duplicate_content: false,
      missing_alt_images: false,
      no_images: false,
      oversized: false,
      clicks_28d: null,
      impressions_28d: null,
      ctr_28d: null,
      position_28d: null,
      gsc_fetched_at_28d: null,
      top_queries_count_28d: 0,
      has_gsc_28d: false,
      clicks_90d: null,
      impressions_90d: null,
      ctr_90d: null,
      position_90d: null,
      gsc_fetched_at_90d: null,
      top_queries_count_90d: 0,
      has_gsc_90d: false,
      priority_score: 0,
      priority_level: 'low',
      priority_rationale: '',
      traffic_component: 0,
      issue_component: 0,
      opportunity_component: 0,
      internal_linking_component: 0,
      opportunity_count: 0,
      primary_opportunity_type: null,
      opportunity_types: [],
      incoming_internal_links: 0,
      incoming_internal_linking_pages: 0,
      has_cannibalization: false,
      cannibalization_competing_urls_count: 0,
      cannibalization_overlap_strength: 0,
      cannibalization_strongest_competing_url: null,
      cannibalization_recommendation_type: null,
    },
  ],
  pages_title_too_short: [],
  pages_title_too_long: [],
  pages_missing_meta_description: [],
  pages_meta_description_too_short: [],
  pages_meta_description_too_long: [],
  pages_missing_h1: [],
  pages_multiple_h1: [],
  pages_missing_h2: [],
  pages_duplicate_title: [],
  pages_duplicate_meta_description: [],
  pages_missing_canonical: [],
  pages_self_canonical: [],
  pages_canonical_to_other_url: [],
  pages_canonical_to_non_200: [],
  pages_canonical_to_redirect: [],
  pages_noindex_like: [],
  pages_non_indexable_like: [],
  broken_internal_links: [
    {
      link_id: 31,
      source_url: 'https://example.com/start',
      target_url: 'https://example.com/404',
      target_normalized_url: 'https://example.com/404',
      target_status_code: 404,
      final_url: 'https://example.com/404',
      redirect_hops: 1,
      target_canonical_url: null,
      target_noindex_like: false,
      target_non_indexable_like: false,
      signals: ['broken_internal'],
    },
  ],
  unresolved_internal_targets: [],
  redirecting_internal_links: [],
  internal_links_to_noindex_like_pages: [],
  internal_links_to_canonicalized_pages: [],
  redirect_chains_internal: [],
  pages_thin_content: [],
  pages_duplicate_content: [],
  js_heavy_like_pages: [],
  rendered_pages: [],
  pages_with_render_errors: [],
  pages_with_schema: [],
  pages_missing_schema: [],
  pages_with_x_robots_tag: [],
  pages_with_schema_types_summary: [],
  pages_with_missing_alt_images: [],
  pages_with_no_images: [],
  oversized_pages: [],
}

const siteOpportunitiesComparePayload = {
  context: sitePagesComparePayload.context,
  gsc_date_range: 'last_28_days',
  actionable_priority_score_threshold: 60,
  summary: {
    total_urls: 42,
    active_urls_with_opportunities: 9,
    active_actionable_urls: 4,
    new_opportunity_urls: 2,
    resolved_opportunity_urls: 1,
    priority_up_urls: 1,
    priority_down_urls: 1,
    entered_actionable_urls: 2,
    left_actionable_urls: 1,
  },
  items: [],
  page: 1,
  page_size: 1,
  total_items: 0,
  total_pages: 0,
}

const siteInternalLinkingComparePayload = {
  context: sitePagesComparePayload.context,
  gsc_date_range: 'last_28_days',
  summary: {
    total_urls: 42,
    issue_urls_in_active: 7,
    new_orphan_like_urls: 1,
    resolved_orphan_like_urls: 2,
    weakly_linked_improved_urls: 2,
    weakly_linked_worsened_urls: 1,
    link_equity_improved_urls: 1,
    link_equity_worsened_urls: 0,
    linking_pages_up_urls: 2,
    linking_pages_down_urls: 1,
    anchor_diversity_improved_urls: 1,
    anchor_diversity_worsened_urls: 0,
    boilerplate_improved_urls: 1,
    boilerplate_worsened_urls: 0,
  },
  items: [],
  page: 1,
  page_size: 1,
  total_items: 0,
  total_pages: 0,
}

const opportunitiesSummaryPayload = {
  crawl_job_id: 11,
  gsc_date_range: 'last_28_days',
  total_pages: 42,
  pages_with_opportunities: 9,
  high_priority_pages: 4,
  critical_priority_pages: 1,
  groups: [
    {
      type: 'QUICK_WINS',
      count: 3,
      top_priority_score: 68,
      top_opportunity_score: 74,
      top_pages: [
        {
          page_id: 101,
          url: 'https://example.com/quick-win',
          priority_score: 68,
          priority_level: 'high',
          priority_rationale: 'Priority rationale',
          primary_opportunity_type: 'QUICK_WINS',
          opportunity_count: 2,
          opportunity_types: ['QUICK_WINS', 'LOW_HANGING_FRUIT'],
          clicks: 12,
          impressions: 320,
          ctr: 0.0375,
          position: 9.2,
          incoming_internal_links: 5,
          incoming_internal_linking_pages: 3,
          opportunities: [],
          opportunity_score: 74,
          impact_level: 'high',
          effort_level: 'low',
          rationale: 'Quick win rationale.',
        },
      ],
    },
  ],
  top_priority_pages: [
    {
      page_id: 101,
      url: 'https://example.com/quick-win',
      priority_score: 68,
      priority_level: 'high',
      priority_rationale: 'Priority rationale',
      primary_opportunity_type: 'QUICK_WINS',
      opportunity_count: 2,
      opportunity_types: ['QUICK_WINS', 'LOW_HANGING_FRUIT'],
      clicks: 12,
      impressions: 320,
      ctr: 0.0375,
      position: 9.2,
      incoming_internal_links: 5,
      incoming_internal_linking_pages: 3,
      opportunities: [],
      opportunity_score: 74,
      impact_level: 'high',
      effort_level: 'low',
      rationale: 'Quick win rationale.',
    },
  ],
}

const internalLinkingOverviewPayload = {
  crawl_job_id: 11,
  gsc_date_range: 'last_28_days',
  total_internal_pages: 42,
  issue_pages: 7,
  orphan_like_pages: 3,
  weakly_linked_important_pages: 2,
  low_anchor_diversity_pages: 1,
  exact_match_anchor_concentration_pages: 1,
  boilerplate_dominated_pages: 1,
  low_link_equity_pages: 2,
  median_link_equity_score: 54,
  average_anchor_diversity_score: 0.48,
  average_body_like_share: 0.61,
}

const internalLinkingIssuesPayload = {
  crawl_job_id: 11,
  gsc_date_range: 'last_28_days',
  items: [
    {
      page_id: 201,
      url: 'https://example.com/orphan',
      normalized_url: 'https://example.com/orphan',
      priority_score: 56,
      priority_level: 'high',
      priority_rationale: 'Priority rationale',
      primary_opportunity_type: 'UNDERLINKED_OPPORTUNITIES',
      opportunity_types: ['UNDERLINKED_OPPORTUNITIES'],
      technical_issue_count: 0,
      clicks: 9,
      impressions: 180,
      ctr: 0.05,
      position: 8.7,
      incoming_internal_links: 1,
      incoming_internal_linking_pages: 1,
      incoming_follow_links: 0,
      incoming_follow_linking_pages: 0,
      incoming_nofollow_links: 1,
      body_like_links: 0,
      body_like_linking_pages: 0,
      boilerplate_like_links: 1,
      boilerplate_like_linking_pages: 1,
      body_like_share: 0,
      boilerplate_like_share: 1,
      unique_anchor_count: 1,
      anchor_diversity_score: 0.2,
      exact_match_anchor_count: 0,
      exact_match_anchor_ratio: 0,
      link_equity_score: 12.4,
      link_equity_rank: 40,
      internal_linking_score: 88,
      issue_count: 2,
      orphan_like: true,
      weakly_linked_important: false,
      low_anchor_diversity: false,
      exact_match_anchor_concentration: false,
      boilerplate_dominated: true,
      low_link_equity: true,
      issue_types: ['ORPHAN_LIKE', 'LOW_LINK_EQUITY'],
      primary_issue_type: 'ORPHAN_LIKE',
      top_anchor_samples: [],
      rationale: 'Orphan-like with weak link equity.',
    },
  ],
  page: 1,
  page_size: 25,
  total_items: 1,
  total_pages: 1,
}

const siteContentRecommendationsPayload = {
  context: {
    site_id: 5,
    site_domain: 'example.com',
    active_crawl_id: 11,
    baseline_crawl_id: 10,
    gsc_date_range: 'last_28_days',
    active_crawl: sitePagesComparePayload.context.active_crawl,
    baseline_crawl: sitePagesComparePayload.context.baseline_crawl,
  },
  summary: {
    total_recommendations: 5,
    implemented_recommendations: 3,
    high_priority_recommendations: 2,
    clusters_covered: 4,
    create_new_page_recommendations: 1,
    expand_existing_page_recommendations: 2,
    strengthen_cluster_recommendations: 1,
    improve_internal_support_recommendations: 1,
    counts_by_type: {
      MISSING_SUPPORTING_CONTENT: 1,
      THIN_CLUSTER: 1,
      EXPAND_EXISTING_PAGE: 1,
      MISSING_STRUCTURAL_PAGE_TYPE: 1,
      INTERNAL_LINKING_SUPPORT: 1,
    },
    counts_by_page_type: {
      home: 0,
      category: 1,
      product: 0,
      service: 1,
      blog_article: 2,
      blog_index: 0,
      contact: 0,
      about: 0,
      faq: 0,
      location: 0,
      legal: 0,
      utility: 0,
      other: 1,
    },
  },
  items: [],
  implemented_items: [
    {
      recommendation_key: 'rec-1',
      recommendation_type: 'EXPAND_EXISTING_PAGE',
      segment: 'expand_existing_page',
      target_url: 'https://example.com/services/seo',
      normalized_target_url: 'https://example.com/services/seo',
      target_title_snapshot: 'SEO services',
      suggested_page_type: 'service',
      cluster_label: 'seo services',
      cluster_key: 'seo-services',
      recommendation_text: 'Expand the services page',
      signals_snapshot: ['Signal A'],
      reasons_snapshot: ['Reason A'],
      helper_snapshot: null,
      primary_outcome_kind: 'gsc',
      outcome_status: 'improved',
      outcome_summary: 'Clicks and impressions are improving.',
      outcome_details: [],
      outcome_window: '30d',
      is_too_early: false,
      days_since_implemented: 40,
      eligible_for_window: true,
      implemented_at: '2026-03-15T08:00:00Z',
      implemented_crawl_job_id: 10,
      implemented_baseline_crawl_job_id: 9,
      times_marked_done: 1,
    },
  ],
  implemented_total: 3,
  implemented_summary: {
    total_count: 3,
    status_counts: {
      improved: 1,
      unchanged: 1,
      pending: 0,
      too_early: 1,
      limited: 0,
      unavailable: 0,
      worsened: 0,
    },
    mode_counts: {
      gsc: 2,
      internal_linking: 1,
      cannibalization: 0,
      issue_flags: 0,
      mixed: 0,
      unknown: 0,
    },
  },
  page: 1,
  page_size: 5,
  total_items: 0,
  total_pages: 0,
}

const siteGscSummaryPayload = {
  site_id: 5,
  site_domain: 'example.com',
  site_root_url: 'https://example.com',
  auth_connected: true,
  selected_property_uri: 'sc-domain:example.com',
  selected_property_permission_level: 'siteOwner',
  available_date_ranges: ['last_28_days', 'last_90_days'],
  active_crawl_id: 11,
  active_crawl_has_gsc_data: true,
  active_crawl: {
    id: 11,
    site_id: 5,
    status: 'running',
    root_url: 'https://example.com',
    created_at: '2026-03-14T12:00:00Z',
    started_at: '2026-03-14T12:01:00Z',
    finished_at: null,
  },
  ranges: [
    {
      date_range_label: 'last_28_days',
      imported_pages: 20,
      pages_with_impressions: 14,
      pages_with_clicks: 6,
      pages_with_top_queries: 8,
      total_top_queries: 22,
      opportunities_with_impressions: 5,
      opportunities_with_clicks: 3,
      last_imported_at: '2026-03-16T09:00:00Z',
    },
  ],
}

function renderWorkspace(route: string) {
  const queryClient = createTestQueryClient()

  return render(
    <I18nextProvider i18n={i18n}>
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[route]}>
          <LocationProbe />
          <Routes>
            <Route path="/sites/:siteId" element={<SiteWorkspaceLayout />}>
              <Route index element={<SiteOverviewPage />} />
              <Route path="progress" element={<SiteProgressPage />} />
              <Route path="crawls">
                <Route index element={<SiteCrawlsPage />} />
                <Route path="new" element={<SiteNewCrawlPage />} />
              </Route>
              <Route path="changes">
                <Route index element={<SiteChangesHubPage />} />
                <Route path="pages" element={<SitePagesComparePage />} />
                <Route path="audit" element={<SiteAuditComparePage />} />
                <Route path="opportunities" element={<SiteOpportunitiesComparePage />} />
                <Route path="internal-linking" element={<SiteInternalLinkingComparePage />} />
              </Route>
              <Route path="pages">
                <Route index element={<SitePagesOverviewPage />} />
                <Route path="records" element={<SitePagesRecordsPage />} />
              </Route>
              <Route path="content-recommendations" element={<SiteContentRecommendationsPage />} />
              <Route path="competitive-gap" element={<SiteCompetitiveGapPage />} />
              <Route path="audit">
                <Route index element={<SiteAuditOverviewPage />} />
                <Route path="sections" element={<SiteAuditSectionsPage />} />
              </Route>
              <Route path="opportunities">
                <Route index element={<SiteOpportunitiesCurrentPage />} />
                <Route path="records" element={<SiteOpportunitiesCurrentPage mode="records" />} />
              </Route>
              <Route path="internal-linking">
                <Route index element={<SiteInternalLinkingCurrentPage />} />
                <Route path="issues" element={<SiteInternalLinkingCurrentPage mode="issues" />} />
              </Route>
              <Route path="gsc" element={<SiteGscPage />} />
            </Route>
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    </I18nextProvider>,
  )
}

function LocationProbe() {
  const location = useLocation()

  return <div data-testid="location-probe">{`${location.pathname}${location.search}`}</div>
}

describe('SiteWorkspaceLayout', () => {
  test('renders the current-first site overview with a lighter baseline helper', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((input) => {
      const url = String(input)
      if (url.includes('/sites/5/content-generator-assets')) {
        return jsonResponse({
          site_id: 5,
          has_assets: false,
          can_regenerate: false,
          active_crawl_id: 11,
          active_crawl_status: 'running',
          status: null,
          basis_crawl_job_id: null,
          surfer_custom_instructions: null,
          seowriting_details_to_include: null,
          introductory_hook_brief: null,
          source_urls: [],
          source_pages_hash: null,
          prompt_version: null,
          llm_provider: null,
          llm_model: null,
          generated_at: null,
          last_error_code: null,
          last_error_message: null,
        })
      }
      if (url.includes('/sites/5') && !url.includes('/crawls')) {
        return jsonResponse(sitePayload)
      }
      throw new Error(`Unexpected request: ${url}`)
    })

    renderWorkspace('/sites/5?active_crawl_id=11&baseline_crawl_id=10')

    expect(await screen.findByText('example.com')).toBeInTheDocument()
    expect(screen.getAllByRole('option', { name: formatCrawlOptionLabel(sitePayload.crawl_history[0], sitePayload.root_url) }).length).toBeGreaterThan(0)
    expect(screen.getAllByRole('option', { name: formatCrawlOptionLabel(sitePayload.crawl_history[1], sitePayload.root_url) }).length).toBeGreaterThan(0)
    expect(screen.queryByLabelText('Baseline crawl')).not.toBeInTheDocument()
    expect(screen.getByText('Site state now')).toBeInTheDocument()
    expect(screen.getByText('Active snapshot KPIs')).toBeInTheDocument()
    expect(screen.getByText('Instructions for content generators')).toBeInTheDocument()
    expect(screen.getByText('Key signals and next actions')).toBeInTheDocument()
    expect(screen.getByText('Compare ready')).toBeInTheDocument()
    expect(screen.getByText('Comparison stays under Changes.')).toBeInTheDocument()
    expect(screen.getAllByText(formatCrawlDateTime(sitePayload.active_crawl)).length).toBeGreaterThan(0)
    expect(screen.getAllByText(formatCrawlDateTime(sitePayload.baseline_crawl)).length).toBeGreaterThan(0)
    fireEvent.click(screen.getByText('Operations'))
    expect(screen.getByRole('link', { name: 'Open active crawl' })).toHaveAttribute('href', '/jobs/11')
    expect(screen.getAllByRole('link', { name: 'Open crawl' })[0]).toHaveAttribute('href', '/jobs/11')
    expect(screen.getAllByRole('link', { name: 'Open Changes' })[0]).toHaveAttribute(
      'href',
      '/sites/5/changes?active_crawl_id=11&baseline_crawl_id=10',
    )
    expect(screen.getAllByText('Content Recommendations').length).toBeGreaterThan(0)
    expect(screen.getAllByRole('link', { name: 'Open crawl history' })[0]).toHaveAttribute(
      'href',
      '/sites/5/crawls?active_crawl_id=11&baseline_crawl_id=10',
    )
    expect(
      screen
        .getAllByRole('link', { name: 'New Crawl' })
        .map((link) => link.getAttribute('href')),
    ).toContain('/sites/5/crawls/new?active_crawl_id=11&baseline_crawl_id=10')
    expect(
      screen
        .getAllByRole('link', { name: 'Open Changes' })
        .map((link) => link.getAttribute('href')),
    ).toContain('/sites/5/changes?active_crawl_id=11&baseline_crawl_id=10')
  })

  test('renders the dedicated site crawls page', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((input) => {
      const url = String(input)
      if (url.includes('/sites/5/crawls')) {
        return jsonResponse(sitePayload.crawl_history)
      }
      if (url.includes('/sites/5')) {
        return jsonResponse(sitePayload)
      }
      throw new Error(`Unexpected request: ${url}`)
    })

    renderWorkspace('/sites/5/crawls?active_crawl_id=11&baseline_crawl_id=10')

    expect(await screen.findByText('Site crawls')).toBeInTheDocument()
    expect(screen.getByText('Crawl history')).toBeInTheDocument()
    expect(screen.getByText('#11')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Active' })).toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: 'Open pages' }).length).toBeGreaterThan(0)
    expect(
      screen
        .getAllByRole('link', { name: 'New Crawl' })
        .map((link) => link.getAttribute('href')),
    ).toContain('/sites/5/crawls/new?active_crawl_id=11&baseline_crawl_id=10')
  })

  test('renders the dedicated new crawl page and keeps the site workspace context', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((input, init) => {
      const url = String(input)
      if (url.includes('/sites/5/crawls') && init?.method === 'POST') {
        return jsonResponse({ id: 12, site_id: 5 })
      }
      if (url.includes('/sites/5')) {
        return jsonResponse(sitePayload)
      }
      throw new Error(`Unexpected request: ${url}`)
    })

    renderWorkspace('/sites/5/crawls/new?active_crawl_id=11&baseline_crawl_id=10')

    expect(await screen.findByText('Launch another crawl snapshot')).toBeInTheDocument()
    expect(screen.getByDisplayValue('https://example.com')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Back to history' })).toHaveAttribute(
      'href',
      '/sites/5/crawls?active_crawl_id=11&baseline_crawl_id=10',
    )
  })

  test('renders the progress dashboard with implementation timeline and subtle compare helper', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((input) => {
      const url = String(input)
      if (url.includes('/sites/5/content-recommendations')) {
        return jsonResponse(siteContentRecommendationsPayload)
      }
      if (url.includes('/sites/5/gsc/summary')) {
        return jsonResponse(siteGscSummaryPayload)
      }
      if (url.includes('/sites/5/pages')) {
        return jsonResponse(sitePagesComparePayload)
      }
      if (url.includes('/sites/5/audit')) {
        return jsonResponse(siteAuditComparePayload)
      }
      if (url.includes('/sites/5/opportunities')) {
        return jsonResponse(siteOpportunitiesComparePayload)
      }
      if (url.includes('/sites/5/internal-linking')) {
        return jsonResponse(siteInternalLinkingComparePayload)
      }
      if (url.includes('/crawl-jobs/11/opportunities')) {
        return jsonResponse(opportunitiesSummaryPayload)
      }
      if (url.includes('/crawl-jobs/11/internal-linking/overview')) {
        return jsonResponse(internalLinkingOverviewPayload)
      }
      if (url.includes('/sites/5') && !url.includes('/crawls')) {
        return jsonResponse(sitePayload)
      }
      throw new Error(`Unexpected request: ${url}`)
    })

    renderWorkspace('/sites/5/progress?active_crawl_id=11&baseline_crawl_id=10')

    expect(await screen.findByText('Are we moving forward?')).toBeInTheDocument()
    expect(screen.getByText('Trend KPIs')).toBeInTheDocument()
    expect(screen.getByText('What improved')).toBeInTheDocument()
    expect(screen.getByText('What worsened')).toBeInTheDocument()
    expect(screen.getByText('Implementation progress')).toBeInTheDocument()
    expect(screen.getByText('Recent timeline')).toBeInTheDocument()
    expect(await screen.findByText('Clicks and impressions are improving.')).toBeInTheDocument()
    expect(await screen.findByText('GSC imported for Last 28 days')).toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: 'Open Changes' })[0]).toHaveAttribute(
      'href',
      '/sites/5/changes?active_crawl_id=11&baseline_crawl_id=10',
    )
    expect(screen.getByRole('link', { name: 'Open Content Recommendations' })).toHaveAttribute(
      'href',
      '/sites/5/content-recommendations?active_crawl_id=11&baseline_crawl_id=10',
    )
  })

  test('renders graceful progress empty states when the site has only one crawl', async () => {
    const oneCrawlSitePayload = {
      ...sitePayload,
      summary: {
        ...sitePayload.summary,
        total_crawls: 1,
        finished_crawls: 0,
        last_crawl_at: '2026-03-14T12:00:00Z',
      },
      baseline_crawl_id: null,
      baseline_crawl: null,
      crawl_history: [sitePayload.crawl_history[0]],
    }

    vi.spyOn(globalThis, 'fetch').mockImplementation((input) => {
      const url = String(input)
      if (url.includes('/sites/5/content-recommendations')) {
        return jsonResponse(siteContentRecommendationsPayload)
      }
      if (url.includes('/sites/5/gsc/summary')) {
        return jsonResponse(siteGscSummaryPayload)
      }
      if (url.includes('/crawl-jobs/11/opportunities')) {
        return jsonResponse(opportunitiesSummaryPayload)
      }
      if (url.includes('/crawl-jobs/11/internal-linking/overview')) {
        return jsonResponse(internalLinkingOverviewPayload)
      }
      if (
        url.includes('/sites/5/pages') ||
        url.includes('/sites/5/audit') ||
        url.includes('/sites/5/opportunities?') ||
        url.includes('/sites/5/internal-linking')
      ) {
        throw new Error(`Compare request should stay disabled: ${url}`)
      }
      if (url.includes('/sites/5') && !url.includes('/crawls')) {
        return jsonResponse(oneCrawlSitePayload)
      }
      throw new Error(`Unexpected request: ${url}`)
    })

    renderWorkspace('/sites/5/progress?active_crawl_id=11')

    expect(await screen.findAllByText('Add another crawl to measure change')).toHaveLength(2)
    expect(screen.getByText('No baseline selected')).toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: 'Open crawl history' })[0]).toHaveAttribute(
      'href',
      '/sites/5/crawls?active_crawl_id=11',
    )
  })

  test('renders the changes hub as the main compare entry point with canonical /changes links', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((input) => {
      const url = String(input)
      if (url.includes('/sites/5/pages')) {
        return jsonResponse(sitePagesComparePayload)
      }
      if (url.includes('/sites/5/audit')) {
        return jsonResponse(siteAuditComparePayload)
      }
      if (url.includes('/sites/5/opportunities')) {
        return jsonResponse(siteOpportunitiesComparePayload)
      }
      if (url.includes('/sites/5/internal-linking')) {
        return jsonResponse(siteInternalLinkingComparePayload)
      }
      if (url.includes('/sites/5') && !url.includes('/crawls')) {
        return jsonResponse(sitePayload)
      }
      throw new Error(`Unexpected request: ${url}`)
    })

    renderWorkspace('/sites/5/changes?active_crawl_id=11&baseline_crawl_id=10')

    expect(await screen.findByText('What changed between crawls?')).toBeInTheDocument()
    expect(screen.getByText('Current changes context')).toBeInTheDocument()
    expect(await screen.findByText('New URLs')).toBeInTheDocument()
    expect(await screen.findByRole('link', { name: /Pages changes/i })).toHaveAttribute(
      'href',
      '/sites/5/changes/pages?active_crawl_id=11&baseline_crawl_id=10',
    )
    expect(await screen.findByRole('link', { name: /Audit changes/i })).toHaveAttribute(
      'href',
      '/sites/5/changes/audit?active_crawl_id=11&baseline_crawl_id=10',
    )
    expect(await screen.findByRole('link', { name: /SEO opportunities changes/i })).toHaveAttribute(
      'href',
      '/sites/5/changes/opportunities?active_crawl_id=11&baseline_crawl_id=10',
    )
    expect(await screen.findByRole('link', { name: /Internal linking changes/i })).toHaveAttribute(
      'href',
      '/sites/5/changes/internal-linking?active_crawl_id=11&baseline_crawl_id=10',
    )
    expect(screen.getByText('Resolved issues')).toBeInTheDocument()
    expect(screen.getByText('New opportunities')).toBeInTheDocument()
    expect(screen.getByText('New orphan-like')).toBeInTheDocument()
  })

  test('keeps the changes hub non-clickable until a baseline crawl exists', async () => {
    const oneCrawlSitePayload = {
      ...sitePayload,
      summary: {
        ...sitePayload.summary,
        total_crawls: 1,
        finished_crawls: 0,
      },
      baseline_crawl_id: null,
      baseline_crawl: null,
      crawl_history: [sitePayload.crawl_history[0]],
    }

    vi.spyOn(globalThis, 'fetch').mockImplementation((input) => {
      const url = String(input)
      if (
        url.includes('/sites/5/pages') ||
        url.includes('/sites/5/audit') ||
        url.includes('/sites/5/opportunities') ||
        url.includes('/sites/5/internal-linking')
      ) {
        throw new Error(`Compare request should stay disabled: ${url}`)
      }
      if (url.includes('/sites/5') && !url.includes('/crawls')) {
        return jsonResponse(oneCrawlSitePayload)
      }
      throw new Error(`Unexpected request: ${url}`)
    })

    renderWorkspace('/sites/5/changes?active_crawl_id=11')

    expect(await screen.findByText('Choose a baseline crawl to compare changes')).toBeInTheDocument()
    expect(screen.getAllByText('Waiting').length).toBeGreaterThan(0)
    expect(screen.queryByRole('link', { name: /Pages changes/i })).not.toBeInTheDocument()
  })

  test('renders top-level pages as current-state and keeps compare under Changes', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((input) => {
      const url = String(input)
      if (url.includes('/crawl-jobs/11/page-taxonomy/summary')) {
        return jsonResponse(pageTaxonomySummaryPayload)
      }
      if (url.includes('/crawl-jobs/11/pages')) {
        return jsonResponse(sitePagesCurrentPayload)
      }
      if (url.includes('/sites/5') && !url.includes('/crawls')) {
        return jsonResponse(sitePayload)
      }
      throw new Error(`Unexpected request: ${url}`)
    })

    renderWorkspace('/sites/5/pages?active_crawl_id=11&baseline_crawl_id=10')

    expect(await screen.findByRole('heading', { name: 'Pages' })).toBeInTheDocument()
    expect(screen.queryByText((_, element) => element?.textContent === 'Compare: Ready to compare')).not.toBeInTheDocument()
    expect(
      screen
        .getAllByRole('link', { name: 'Open active crawl' })
        .map((link) => link.getAttribute('href')),
    ).toContain('/jobs/11')
    expect(screen.getByRole('link', { name: 'Export current view CSV' })).toHaveAttribute(
      'href',
      expect.stringContaining('/crawl-jobs/11/export/pages.csv'),
    )
    expect(screen.getByTestId('location-probe')).toHaveTextContent(
      '/sites/5/pages?active_crawl_id=11&baseline_crawl_id=10',
    )
  })

  test('renders top-level audit as current-state and keeps compare canonical under Changes', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((input) => {
      const url = String(input)
      if (url.includes('/crawl-jobs/11/audit')) {
        return jsonResponse(siteAuditCurrentPayload)
      }
      if (url.includes('/sites/5') && !url.includes('/crawls')) {
        return jsonResponse(sitePayload)
      }
      throw new Error(`Unexpected request: ${url}`)
    })

    renderWorkspace('/sites/5/audit?active_crawl_id=11&baseline_crawl_id=10')

    expect(await screen.findByRole('heading', { name: 'Audit' })).toBeInTheDocument()
    fireEvent.click(screen.getAllByText('Operations')[1])
    expect(
      screen
        .getAllByRole('link', { name: 'Open Changes' })
        .map((link) => link.getAttribute('href')),
    ).toContain('/sites/5/changes/audit?active_crawl_id=11&baseline_crawl_id=10')
    expect(screen.getByText('Pages missing title')).toBeInTheDocument()
    expect(screen.getByTestId('location-probe')).toHaveTextContent(
      '/sites/5/audit?active_crawl_id=11&baseline_crawl_id=10',
    )
  })

  test('renders top-level opportunities as current-state and keeps compare under /changes', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((input) => {
      const url = String(input)
      if (url.includes('/crawl-jobs/11/opportunities')) {
        return jsonResponse(opportunitiesSummaryPayload)
      }
      if (url.includes('/sites/5') && !url.includes('/crawls')) {
        return jsonResponse(sitePayload)
      }
      throw new Error(`Unexpected request: ${url}`)
    })

    renderWorkspace('/sites/5/opportunities?active_crawl_id=11&baseline_crawl_id=10')

    expect(await screen.findByRole('heading', { name: 'SEO Opportunities' })).toBeInTheDocument()
    fireEvent.click(screen.getAllByText('Operations')[1])
    expect(
      screen
        .getAllByRole('link', { name: 'Open Changes' })
        .map((link) => link.getAttribute('href')),
    ).toContain('/sites/5/changes/opportunities?active_crawl_id=11&baseline_crawl_id=10')
    expect(
      screen
        .getAllByRole('link', { name: 'Open records' })
        .map((link) => link.getAttribute('href')),
    ).toContain('/sites/5/opportunities/records?active_crawl_id=11&baseline_crawl_id=10')
    expect(screen.getAllByText('Quick win rationale.').length).toBeGreaterThan(0)
    expect(screen.getByTestId('location-probe')).toHaveTextContent(
      '/sites/5/opportunities?active_crawl_id=11&baseline_crawl_id=10',
    )
  })

  test('renders top-level internal linking current-state and dedicated issues subroute', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((input) => {
      const url = String(input)
      if (url.includes('/crawl-jobs/11/internal-linking/overview')) {
        return jsonResponse(internalLinkingOverviewPayload)
      }
      if (url.includes('/crawl-jobs/11/internal-linking/issues')) {
        return jsonResponse(internalLinkingIssuesPayload)
      }
      if (url.includes('/sites/5') && !url.includes('/crawls')) {
        return jsonResponse(sitePayload)
      }
      throw new Error(`Unexpected request: ${url}`)
    })

    renderWorkspace('/sites/5/internal-linking/issues?active_crawl_id=11&baseline_crawl_id=10')

    expect(await screen.findByRole('heading', { name: 'Internal Linking Issues' })).toBeInTheDocument()
    expect(
      screen
        .getAllByRole('link', { name: 'Open overview' })
        .map((link) => link.getAttribute('href')),
    ).toContain('/sites/5/internal-linking?active_crawl_id=11&baseline_crawl_id=10')
    fireEvent.click(screen.getAllByText('Operations')[1])
    expect(
      screen
        .getAllByRole('link', { name: 'Open Changes' })
        .map((link) => link.getAttribute('href')),
    ).toContain('/sites/5/changes/internal-linking?active_crawl_id=11&baseline_crawl_id=10')
    expect(screen.getByText('Orphan-like with weak link equity.')).toBeInTheDocument()
    expect(screen.getByTestId('location-probe')).toHaveTextContent(
      '/sites/5/internal-linking/issues?active_crawl_id=11&baseline_crawl_id=10',
    )
  })
})
