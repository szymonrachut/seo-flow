import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { I18nextProvider } from 'react-i18next'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { afterEach, describe, expect, test, vi } from 'vitest'

import i18n from '../../i18n'
import { createTestQueryClient, jsonResponse } from '../../test/testUtils'
import type { SiteDetail } from '../../types/api'
import { SitePagesWorkspaceView } from './SitePagesWorkspaceView'

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
    finished_at: '2026-03-14T12:09:00Z',
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
      pages_with_render_errors: 1,
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
      errors_count: 1,
    },
  },
  crawl_history: [],
} as SiteDetail

const pagesPayload = {
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

const taxonomySummaryPayload = {
  crawl_job_id: 11,
  page_type_version: '11.1-v1',
  total_pages: 12,
  classified_pages: 12,
  counts_by_page_type: {
    home: 1,
    category: 2,
    product: 3,
    service: 1,
    blog_article: 2,
    blog_index: 1,
    contact: 1,
    about: 0,
    faq: 0,
    location: 0,
    legal: 0,
    utility: 1,
    other: 0,
  },
  counts_by_page_bucket: {
    commercial: 7,
    informational: 3,
    utility: 1,
    trust: 1,
    other: 0,
  },
}

function LocationEcho() {
  const location = useLocation()

  return <output data-testid="location-search">{location.search}</output>
}

function renderPagesView(mode: 'overview' | 'records', route = '/sites/5/pages?active_crawl_id=11&baseline_crawl_id=10') {
  const queryClient = createTestQueryClient()
  const user = userEvent.setup()

  render(
    <I18nextProvider i18n={i18n}>
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[route]}>
          <SitePagesWorkspaceView site={sitePayload} mode={mode} />
          <LocationEcho />
        </MemoryRouter>
      </QueryClientProvider>
    </I18nextProvider>,
  )

  return { user }
}

function mockPagesRequests() {
  vi.spyOn(globalThis, 'fetch').mockImplementation((input) => {
    const url = typeof input === 'string' ? input : input instanceof Request ? input.url : String(input)
    if (url.includes('/page-taxonomy/summary')) {
      return jsonResponse(taxonomySummaryPayload)
    }
    if (url.includes('/crawl-jobs/11/pages')) {
      return jsonResponse(pagesPayload)
    }
    throw new Error(`Unhandled fetch in SitePagesWorkspaceView.test.tsx: ${url}`)
  })
}

describe('SitePagesWorkspaceView', () => {
  test('renders the current-state overview with active crawl context', async () => {
    mockPagesRequests()

    const { user } = renderPagesView('overview')

    expect(await screen.findByRole('heading', { name: 'Pages' })).toBeInTheDocument()
    expect(screen.getByText((_, element) => element?.textContent === 'Active: #11')).toBeInTheDocument()
    expect(screen.queryByText((_, element) => element?.textContent === 'Baseline: #10')).not.toBeInTheDocument()
    expect(screen.queryByText((_, element) => element?.textContent === 'Compare: Ready to compare')).not.toBeInTheDocument()
    expect(screen.getByText('Active crawl pages')).toBeInTheDocument()
    expect(screen.getByText('Matching rows')).toBeInTheDocument()
    expect(await screen.findByText('Alpha')).toBeInTheDocument()
    await user.click(screen.getByText('Export'))
    expect(screen.getByRole('link', { name: 'Export full CSV' })).toHaveAttribute(
      'href',
      expect.stringContaining('/crawl-jobs/11/export/pages.csv'),
    )
    expect(screen.getByRole('link', { name: 'Export current view CSV' })).toHaveAttribute(
      'href',
      expect.stringContaining('page_size=8'),
    )
    await user.click(screen.getByText('Operations'))
    expect(screen.getByRole('link', { name: 'Open active crawl' })).toHaveAttribute('href', '/jobs/11')
    expect(screen.getByRole('link', { name: 'Open in job pages' })).toHaveAttribute(
      'href',
      '/jobs/11/pages?url_contains=https%3A%2F%2Fexample.com%2Fblog%2Falpha',
    )

    await screen.findByRole('button', { name: 'Show all filters' })
  })

  test('supports quick filter toggle on/off and multi-select in the URL', async () => {
    mockPagesRequests()

    const { user } = renderPagesView('records', '/sites/5/pages?active_crawl_id=11&baseline_crawl_id=10&page=2')

    await screen.findByRole('heading', { name: 'Pages Records' })
    await user.click(screen.getByRole('button', { name: 'High priority' }))
    await user.click(screen.getByRole('button', { name: 'Quick wins' }))

    await waitFor(() => expect(screen.getByTestId('location-search')).toHaveTextContent('priority_score_min=45'))
    expect(screen.getByTestId('location-search')).toHaveTextContent('opportunity_type=QUICK_WINS')
    expect(screen.getByTestId('location-search')).toHaveTextContent('sort_by=priority_score')
    expect(screen.getByTestId('location-search')).toHaveTextContent('page=1')

    await user.click(screen.getByRole('button', { name: 'High priority' }))

    await waitFor(() => expect(screen.getByTestId('location-search')).not.toHaveTextContent('priority_score_min=45'))
    expect(screen.getByTestId('location-search')).toHaveTextContent('opportunity_type=QUICK_WINS')
  })

  test('reveals advanced filters when requested', async () => {
    mockPagesRequests()

    const { user } = renderPagesView('overview')

    await screen.findByRole('heading', { name: 'Pages' })
    expect(screen.queryByRole('spinbutton', { name: 'Taxonomy confidence min (%)' })).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Show all filters' }))

    expect(screen.getByRole('spinbutton', { name: 'Taxonomy confidence min (%)' })).toBeInTheDocument()
    expect(screen.getByLabelText('Has cannibalization')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Hide extra filters' })).toBeInTheDocument()
  })

  test('renders the records view with the denser page size', async () => {
    mockPagesRequests()

    renderPagesView('records')

    expect(await screen.findByRole('heading', { name: 'Pages Records' })).toBeInTheDocument()
    expect(screen.getByText('Matching rows')).toBeInTheDocument()
    expect(screen.getByText((_, element) => element?.textContent === 'Active: #11')).toBeInTheDocument()
    expect(screen.queryByText((_, element) => element?.textContent === 'Baseline: #10')).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Open in job pages' })).toBeInTheDocument()
  })
})
