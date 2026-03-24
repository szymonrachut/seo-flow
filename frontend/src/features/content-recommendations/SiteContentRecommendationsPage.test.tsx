import { QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { I18nextProvider } from 'react-i18next'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { afterEach, describe, expect, test, vi } from 'vitest'

import i18n from '../../i18n'
import { createTestQueryClient, jsonResponse } from '../../test/testUtils'
import { IMPLEMENTED_CONTENT_RECOMMENDATION_STATUS_ORDER, type ContentRecommendationOutcomeStatus } from '../../types/api'
import { SiteWorkspaceLayout } from '../sites/SiteWorkspaceLayout'
import { SiteContentRecommendationsPage } from './SiteContentRecommendationsPage'

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

const recommendationsPayload = {
  context: {
    site_id: 5,
    site_domain: 'example.com',
    active_crawl_id: 11,
    baseline_crawl_id: 10,
    gsc_date_range: 'last_28_days',
    active_crawl: {
      id: 11,
      status: 'finished',
      created_at: '2026-03-14T12:00:00Z',
      started_at: '2026-03-14T12:01:00Z',
      finished_at: '2026-03-14T12:10:00Z',
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
  summary: {
    total_recommendations: 2,
    implemented_recommendations: 1,
    high_priority_recommendations: 1,
    clusters_covered: 2,
    create_new_page_recommendations: 1,
    expand_existing_page_recommendations: 1,
    strengthen_cluster_recommendations: 0,
    improve_internal_support_recommendations: 0,
    counts_by_type: {
      MISSING_SUPPORTING_CONTENT: 0,
      THIN_CLUSTER: 0,
      EXPAND_EXISTING_PAGE: 1,
      MISSING_STRUCTURAL_PAGE_TYPE: 1,
      INTERNAL_LINKING_SUPPORT: 0,
    },
    counts_by_page_type: {
      home: 0,
      category: 1,
      product: 0,
      service: 1,
      blog_article: 0,
      blog_index: 0,
      contact: 0,
      about: 0,
      faq: 0,
      location: 0,
      legal: 0,
      utility: 0,
      other: 0,
    },
  },
  items: [
    {
      id: 'EXPAND_EXISTING_PAGE:content:4:service',
      recommendation_key: 'expand_existing_page:abc123',
      recommendation_type: 'EXPAND_EXISTING_PAGE',
      segment: 'expand_existing_page',
      cluster_key: 'content',
      cluster_label: 'Content strategy',
      target_page_id: 4,
      target_url: 'https://example.com/content-strategy',
      page_type: 'service',
      target_page_type: 'service',
      suggested_page_type: null,
      priority_score: 81,
      confidence: 0.83,
      impact: 'high',
      effort: 'medium',
      cluster_strength: 66,
      coverage_gap_score: 58,
      internal_support_score: 42,
      rationale:
        'Expand https://example.com/content-strategy: the page already attracts demand, but content depth and support still leave upside.',
      signals: ['Priority score: 68', 'Impressions: 180', 'Top queries: 4'],
      reasons: [
        'https://example.com/content-strategy already has demand signals, but the page is still too shallow or weakly supported.',
      ],
      prerequisites: ['Improve internal linking support around the target URL before scaling the cluster.'],
      supporting_urls: ['https://example.com/content-strategy/faq'],
      was_implemented_before: false,
      previously_implemented_at: null,
      url_improvement_helper: {
        target_url: 'https://example.com/content-strategy',
        title: 'Content strategy',
        page_type: 'service',
        page_bucket: 'commercial',
        open_issues: [
          'Thin content signal is still active for this URL.',
          'The URL is still weakly linked for its current importance.',
        ],
        improvement_actions: [
          'Expand content depth and strengthen heading coverage on the existing URL.',
          'Add more contextual internal links from relevant supporting URLs into this page.',
        ],
        supporting_signals: [
          'Priority score: 68 (high)',
          'Internal linking snapshot: 1 links from 1 pages',
        ],
        gsc_context: {
          available: true,
          impressions: 180,
          clicks: 14,
          ctr: 0.07,
          position: 6.8,
          top_queries_count: 4,
          notes: [],
        },
        internal_linking_context: {
          internal_linking_score: 54,
          issue_count: 2,
          issue_types: ['WEAKLY_LINKED_IMPORTANT', 'LOW_LINK_EQUITY'],
          incoming_internal_links: 1,
          incoming_internal_linking_pages: 1,
          link_equity_score: 22.5,
          anchor_diversity_score: 41.2,
        },
        cannibalization_context: {
          has_active_signals: true,
          severity: 'high',
          competing_urls_count: 2,
          common_queries_count: 3,
          strongest_competing_url: 'https://example.com/content-strategy/faq',
          shared_top_queries: ['content strategy'],
        },
        compare_context: {
          baseline_crawl_id: 10,
          signals: [
            {
              key: 'technical_issues',
              label: 'Technical issues',
              status: 'improved',
              detail: '2 issue(s) now vs 4 issue(s) in baseline.',
            },
            {
              key: 'cannibalization',
              label: 'Cannibalization',
              status: 'worsened',
              detail: 'high severity across 2 competing URL(s) now vs no active signals in baseline.',
            },
          ],
        },
      },
    },
    {
      id: 'MISSING_STRUCTURAL_PAGE_TYPE:audit:6:category',
      recommendation_key: 'missing_structural_page_type:def456',
      recommendation_type: 'MISSING_STRUCTURAL_PAGE_TYPE',
      segment: 'create_new_page',
      cluster_key: 'audit',
      cluster_label: 'Audit',
      target_page_id: 6,
      target_url: 'https://example.com/produkt/audit-lite',
      page_type: 'category',
      target_page_type: 'product',
      suggested_page_type: 'category',
      priority_score: 74,
      confidence: 0.8,
      impact: 'high',
      effort: 'high',
      cluster_strength: 61,
      coverage_gap_score: 77,
      internal_support_score: 39,
      rationale:
        'Create a category page for "Audit" so the existing URLs have a clearer hub and the cluster stops relying only on detail pages.',
      signals: ['Product pages: 2', 'Category pages: 0', 'Cluster strength: 61'],
      reasons: ['The topic already has product-level detail pages, but no category or collection hub.'],
      prerequisites: [],
      supporting_urls: ['https://example.com/produkt/audit-pro'],
      was_implemented_before: true,
      previously_implemented_at: '2026-03-15T09:00:00Z',
      url_improvement_helper: null,
    },
  ],
  implemented_items: [
    {
      recommendation_key: 'implemented-expand:xyz789',
      recommendation_type: 'EXPAND_EXISTING_PAGE',
      segment: 'expand_existing_page',
      target_url: 'https://example.com/content-strategy',
      normalized_target_url: 'https://example.com/content-strategy',
      target_title_snapshot: 'Content strategy',
      suggested_page_type: null,
      cluster_label: 'Content strategy',
      cluster_key: 'content',
      recommendation_text: 'Keep expanding the content strategy page and monitor post-implementation SEO outcomes.',
      signals_snapshot: ['Impressions: 120', 'Clicks: 9'],
      reasons_snapshot: ['The page already showed demand before implementation.'],
      helper_snapshot: {
        target_url: 'https://example.com/content-strategy',
        title: 'Content strategy',
        page_type: 'service',
        page_bucket: 'commercial',
        open_issues: ['Thin content signal was active at implementation time.'],
        improvement_actions: ['Add more contextual internal links from relevant supporting URLs into this page.'],
        supporting_signals: ['Priority score: 68 (high)'],
        gsc_context: {
          available: true,
          impressions: 120,
          clicks: 9,
          ctr: 0.075,
          position: 9.4,
          top_queries_count: 1,
          notes: [],
        },
        internal_linking_context: {
          internal_linking_score: 20,
          issue_count: 4,
          issue_types: ['WEAKLY_LINKED_IMPORTANT'],
          incoming_internal_links: 0,
          incoming_internal_linking_pages: 0,
          link_equity_score: 5,
          anchor_diversity_score: 10,
        },
        cannibalization_context: {
          has_active_signals: false,
          severity: null,
          competing_urls_count: 0,
          common_queries_count: 0,
          strongest_competing_url: null,
          shared_top_queries: [],
        },
        compare_context: null,
      },
      primary_outcome_kind: 'gsc',
      outcome_status: 'improved',
      outcome_summary: '+16 clicks',
      outcome_details: [
        { label: 'Impressions', before: '120', after: '200', change: '+80' },
        { label: 'Clicks', before: '9', after: '25', change: '+16' },
        { label: 'Avg position', before: '9.4', after: '6.8', change: '+2.6' },
      ],
      outcome_window: '30d',
      is_too_early: false,
      days_since_implemented: 44,
      eligible_for_window: true,
      implemented_at: '2026-02-01T09:00:00Z',
      implemented_crawl_job_id: 10,
      implemented_baseline_crawl_job_id: null,
      times_marked_done: 1,
    },
  ],
  implemented_total: 1,
  implemented_summary: {
    total_count: 1,
    status_counts: {
      improved: 1,
      worsened: 0,
      unchanged: 0,
      pending: 0,
      limited: 0,
      unavailable: 0,
      too_early: 0,
    },
    mode_counts: {
      gsc: 1,
      internal_linking: 0,
      cannibalization: 0,
      issue_flags: 0,
      mixed: 0,
      unknown: 0,
    },
  },
  page: 1,
  page_size: 25,
  total_items: 2,
  total_pages: 1,
}

function buildImplementedSummaryButtonLabels(
  totalCount: number,
  statusCounts: Record<ContentRecommendationOutcomeStatus, number>,
) {
  return [
    `In scope: ${totalCount}`,
    ...IMPLEMENTED_CONTENT_RECOMMENDATION_STATUS_ORDER.map(
      (status) => `${i18n.t(`contentRecommendations.implemented.status.${status}`)}: ${statusCounts[status]}`,
    ),
  ]
}

function renderContentRecommendations(route: string) {
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
              <Route path="content-recommendations">
                <Route
                  index
                  element={
                    <>
                      <SiteContentRecommendationsPage />
                      <LocationEcho />
                    </>
                  }
                />
                <Route
                  path="active"
                  element={
                    <>
                      <SiteContentRecommendationsPage mode="active" />
                      <LocationEcho />
                    </>
                  }
                />
                <Route
                  path="implemented"
                  element={
                    <>
                      <SiteContentRecommendationsPage mode="implemented" />
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

function mockRequests(payload = recommendationsPayload) {
  return vi.spyOn(globalThis, 'fetch').mockImplementation((input, init) => {
    const url = typeof input === 'string' ? input : input instanceof Request ? input.url : String(input)
    const method = input instanceof Request ? input.method : init?.method ?? 'GET'
    if (url.includes('/content-recommendations/mark-done') && method === 'POST') {
      return jsonResponse({
        recommendation_key: 'expand_existing_page:abc123',
        implemented_at: '2026-03-16T12:00:00Z',
        implemented_crawl_job_id: 11,
        implemented_baseline_crawl_job_id: 10,
        primary_outcome_kind: 'gsc',
        times_marked_done: 1,
      })
    }
    if (url.includes('/content-recommendations')) {
      return jsonResponse(payload)
    }
    if (url.includes('/sites/5')) {
      return jsonResponse(sitePayload)
    }
    throw new Error(`Unexpected request: ${url}`)
  })
}

function LocationEcho() {
  const location = useLocation()
  return <output data-testid="location-search">{location.search}</output>
}

describe('SiteContentRecommendationsPage', () => {
  test('renders the overview with lifecycle status and shortcuts', async () => {
    mockRequests()

    renderContentRecommendations(
      '/sites/5/content-recommendations?active_crawl_id=11&baseline_crawl_id=10&segment=expand_existing_page&page_type=service',
    )

    expect(await screen.findByRole('heading', { name: 'Content recommendations overview' })).toBeInTheDocument()
    expect(screen.getByText('Lifecycle status')).toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: 'Open active' })[0]).toHaveAttribute(
      'href',
      '/sites/5/content-recommendations/active?active_crawl_id=11&baseline_crawl_id=10',
    )
    expect(screen.getAllByRole('link', { name: 'Open implemented' })[0]).toHaveAttribute(
      'href',
      '/sites/5/content-recommendations/implemented?active_crawl_id=11&baseline_crawl_id=10',
    )
    expect(screen.getByRole('link', { name: 'Export recommendations CSV' })).toHaveAttribute(
      'href',
      expect.stringContaining('/sites/5/export/content-recommendations.csv'),
    )
  })

  test('quick filters and filters keep state in the query string', async () => {
    mockRequests()

    const { user } = renderContentRecommendations('/sites/5/content-recommendations/active?active_crawl_id=11&baseline_crawl_id=10')

    await screen.findByRole('button', { name: 'Content strategy' })
    await user.click(screen.getByRole('button', { name: 'Create new page' }))

    await waitFor(() => expect(screen.getByTestId('location-search')).toHaveTextContent('segment=create_new_page'))
    expect(screen.getByTestId('location-search')).toHaveTextContent('sort_by=priority_score')

    await user.selectOptions(screen.getByLabelText('Suggested page type'), 'product')
    await waitFor(() => expect(screen.getByTestId('location-search')).toHaveTextContent('page_type=product'))

    fireEvent.change(screen.getByLabelText('Cluster contains'), { target: { value: 'audit' } })
    await waitFor(() => expect(screen.getByTestId('location-search')).toHaveTextContent('cluster=audit'))
  })

  test('implemented filters render and keep state in the query string', async () => {
    mockRequests()

    const { user } = renderContentRecommendations('/sites/5/content-recommendations/implemented?active_crawl_id=11&baseline_crawl_id=10')

    await screen.findByLabelText('Outcome window')

    await user.selectOptions(screen.getByLabelText('Outcome window'), '90d')
    await user.selectOptions(screen.getByLabelText('Outcome status'), 'too_early')
    await user.selectOptions(screen.getByLabelText('Outcome mode'), 'gsc')
    fireEvent.input(screen.getByLabelText('Search implemented'), { target: { value: 'content' } })

    await waitFor(() =>
      expect(screen.getByTestId('location-search')).toHaveTextContent('implemented_outcome_window=90d'),
    )
    expect(screen.getByTestId('location-search')).toHaveTextContent('implemented_status_filter=too_early')
    expect(screen.getByTestId('location-search')).toHaveTextContent('implemented_mode_filter=gsc')
    expect(screen.getByTestId('location-search')).toHaveTextContent('implemented_search=content')
  })

  test('renders the URL improvement helper only when helper data is available', async () => {
    mockRequests()

    const { user } = renderContentRecommendations('/sites/5/content-recommendations/active?active_crawl_id=11&baseline_crawl_id=10')

    await screen.findByRole('button', { name: 'Content strategy' })
    expect(screen.getAllByText('What else can be improved for this URL')).toHaveLength(1)

    await user.click(screen.getByText('What else can be improved for this URL'))

    expect(screen.getByText('Thin content signal is still active for this URL.')).toBeInTheDocument()
    expect(screen.getAllByText('Add more contextual internal links from relevant supporting URLs into this page.').length).toBeGreaterThan(0)
    expect(screen.queryByText('2 issue(s) now vs 4 issue(s) in baseline.')).not.toBeInTheDocument()
  })

  test('calls the mark done mutation for an active recommendation', async () => {
    const fetchSpy = mockRequests()
    const { user } = renderContentRecommendations('/sites/5/content-recommendations/active?active_crawl_id=11&baseline_crawl_id=10')

    await screen.findByRole('button', { name: 'Content strategy' })
    await user.click(screen.getAllByRole('button', { name: 'Mark done' })[0])

    await waitFor(() =>
      expect(
        fetchSpy.mock.calls.some(([input, init]) => {
          const url = typeof input === 'string' ? input : input instanceof Request ? input.url : String(input)
          const method = input instanceof Request ? input.method : init?.method ?? 'GET'
          return url.includes('/content-recommendations/mark-done') && method === 'POST'
        }),
      ).toBe(true),
    )
  })

  test('renders implemented recommendations as collapsed rows with expandable details', async () => {
    mockRequests()

    const { user } = renderContentRecommendations('/sites/5/content-recommendations/implemented?active_crawl_id=11&baseline_crawl_id=10')

    expect(await screen.findByText('Implemented recommendations')).toBeInTheDocument()
    expect(
      screen.getByText('Keep expanding the content strategy page and monitor post-implementation SEO outcomes.'),
    ).toBeInTheDocument()
    expect(screen.getByText('+16 clicks')).toBeInTheDocument()

    await user.click(
      screen.getByText('Keep expanding the content strategy page and monitor post-implementation SEO outcomes.'),
    )

    expect(screen.getByText('Outcome details')).toBeInTheDocument()
    expect(screen.getByText('Thin content signal was active at implementation time.')).toBeInTheDocument()
    expect(screen.getByText('Before: 120')).toBeInTheDocument()
    expect(screen.getByText('After: 200')).toBeInTheDocument()
  })

  test('renders the implemented summary bar with current status counts', async () => {
    mockRequests({
      ...recommendationsPayload,
      summary: {
        ...recommendationsPayload.summary,
        implemented_recommendations: 8,
      },
      implemented_total: 1,
      implemented_summary: {
        total_count: 8,
        status_counts: {
          improved: 3,
          worsened: 1,
          unchanged: 1,
          pending: 1,
          limited: 1,
          unavailable: 0,
          too_early: 1,
        },
        mode_counts: {
          gsc: 7,
          internal_linking: 1,
          cannibalization: 0,
          issue_flags: 0,
          mixed: 0,
          unknown: 0,
        },
      },
    })

    renderContentRecommendations(
      '/sites/5/content-recommendations/implemented?active_crawl_id=11&baseline_crawl_id=10&implemented_status_filter=improved',
    )

    const summaryBar = await screen.findByTestId('implemented-summary-bar')
    const summaryButtons = within(summaryBar)
      .getAllByRole('button')
      .map((button) => button.getAttribute('aria-label'))

    expect(within(summaryBar).getByText('Implemented summary')).toBeInTheDocument()
    expect(summaryButtons).toEqual(
      buildImplementedSummaryButtonLabels(8, {
        improved: 3,
        unchanged: 1,
        pending: 1,
        too_early: 1,
        limited: 1,
        unavailable: 0,
        worsened: 1,
      }),
    )
  })

  test('clicking the Improved summary badge updates the status filter and resets page to 1', async () => {
    mockRequests({
      ...recommendationsPayload,
      summary: {
        ...recommendationsPayload.summary,
        implemented_recommendations: 8,
      },
      implemented_summary: {
        total_count: 8,
        status_counts: {
          improved: 3,
          worsened: 1,
          unchanged: 1,
          pending: 1,
          limited: 1,
          unavailable: 0,
          too_early: 1,
        },
        mode_counts: {
          gsc: 7,
          internal_linking: 1,
          cannibalization: 0,
          issue_flags: 0,
          mixed: 0,
          unknown: 0,
        },
      },
    })

    const { user } = renderContentRecommendations(
      '/sites/5/content-recommendations/implemented?active_crawl_id=11&baseline_crawl_id=10&page=4',
    )

    const summaryBar = await screen.findByTestId('implemented-summary-bar')
    const improvedButton = within(summaryBar).getByRole('button', { name: 'Improved: 3' })

    await user.click(improvedButton)

    await waitFor(() =>
      expect(screen.getByTestId('location-search')).toHaveTextContent('implemented_status_filter=improved'),
    )
    expect(screen.getByTestId('location-search')).toHaveTextContent('page=1')
    await waitFor(() =>
      expect(
        within(screen.getByTestId('implemented-summary-bar')).getByRole('button', { name: 'Improved: 3' }),
      ).toHaveAttribute('aria-pressed', 'true'),
    )
  })

  test('clicking the Total summary badge clears the quick filter to all and highlights the active badge', async () => {
    mockRequests({
      ...recommendationsPayload,
      summary: {
        ...recommendationsPayload.summary,
        implemented_recommendations: 8,
      },
      implemented_summary: {
        total_count: 8,
        status_counts: {
          improved: 3,
          worsened: 1,
          unchanged: 1,
          pending: 1,
          limited: 1,
          unavailable: 0,
          too_early: 1,
        },
        mode_counts: {
          gsc: 7,
          internal_linking: 1,
          cannibalization: 0,
          issue_flags: 0,
          mixed: 0,
          unknown: 0,
        },
      },
    })

    const { user } = renderContentRecommendations(
      '/sites/5/content-recommendations/implemented?active_crawl_id=11&baseline_crawl_id=10&implemented_status_filter=improved&page=5',
    )

    const summaryBar = await screen.findByTestId('implemented-summary-bar')
    const improvedButton = within(summaryBar).getByRole('button', { name: 'Improved: 3' })
    const totalButton = within(summaryBar).getByRole('button', { name: 'In scope: 8' })

    expect(improvedButton).toHaveAttribute('aria-pressed', 'true')
    expect(totalButton).toHaveAttribute('aria-pressed', 'false')

    await user.click(totalButton)

    await waitFor(() =>
      expect(screen.getByTestId('location-search')).toHaveTextContent('implemented_status_filter=all'),
    )
    expect(screen.getByTestId('location-search')).toHaveTextContent('page=1')
    await waitFor(() =>
      expect(within(screen.getByTestId('implemented-summary-bar')).getByRole('button', { name: 'In scope: 8' })).toHaveAttribute(
        'aria-pressed',
        'true',
      ),
    )
    expect(within(screen.getByTestId('implemented-summary-bar')).getByRole('button', { name: 'Improved: 3' })).toHaveAttribute(
      'aria-pressed',
      'false',
    )
  })

  test('shows a too early badge and explanation for fresh implemented items', async () => {
    mockRequests({
      ...recommendationsPayload,
      implemented_items: [
        {
          ...recommendationsPayload.implemented_items[0],
          outcome_status: 'too_early',
          outcome_summary: 'Too early to evaluate (30d window).',
          outcome_details: [],
          outcome_window: '30d',
          is_too_early: true,
          days_since_implemented: 11,
          eligible_for_window: false,
          implemented_at: '2026-03-05T09:00:00Z',
        },
      ],
    })

    const { user } = renderContentRecommendations('/sites/5/content-recommendations/implemented?active_crawl_id=11&baseline_crawl_id=10')

    expect((await screen.findAllByText('Too early to evaluate (30d window).')).length).toBeGreaterThan(0)
    expect(screen.getAllByText('Too early').length).toBeGreaterThan(0)

    await user.click(
      screen.getByText('Keep expanding the content strategy page and monitor post-implementation SEO outcomes.'),
    )

    expect(
      screen.getByText('Only 11 day(s) have passed since implementation, so the 30d window is still too early.'),
    ).toBeInTheDocument()
  })

  test('keeps the summary bar visible when status drilldown empties the implemented list', async () => {
    mockRequests({
      ...recommendationsPayload,
      implemented_items: [],
      implemented_total: 0,
    })

    renderContentRecommendations(
      '/sites/5/content-recommendations/implemented?active_crawl_id=11&baseline_crawl_id=10&implemented_status_filter=too_early',
    )

    const summaryBar = await screen.findByTestId('implemented-summary-bar')

    expect(within(summaryBar).getByRole('button', { name: 'In scope: 1' })).toBeInTheDocument()
    expect(within(summaryBar).getByRole('button', { name: 'Improved: 1' })).toBeInTheDocument()
    expect(within(summaryBar).getByRole('button', { name: 'Too early: 0' })).toHaveAttribute('aria-pressed', 'true')
    expect(await screen.findByText('No implemented recommendations for this status')).toBeInTheDocument()
    expect(
      screen.getByText('The summary still reflects the current window, mode, and search scope. Pick another status or clear the drilldown.'),
    ).toBeInTheDocument()
  })

  test('shows the scoped implemented empty state when window, mode, or search removes all tracked items', async () => {
    mockRequests({
      ...recommendationsPayload,
      implemented_items: [],
      implemented_total: 0,
      implemented_summary: {
        total_count: 0,
        status_counts: {
          improved: 0,
          worsened: 0,
          unchanged: 0,
          pending: 0,
          limited: 0,
          unavailable: 0,
          too_early: 0,
        },
        mode_counts: {
          gsc: 0,
          internal_linking: 0,
          cannibalization: 0,
          issue_flags: 0,
          mixed: 0,
          unknown: 0,
        },
      },
    })

    renderContentRecommendations(
      '/sites/5/content-recommendations/implemented?active_crawl_id=11&baseline_crawl_id=10&implemented_search=faq',
    )

    expect(await screen.findByText('No implemented recommendations in scope')).toBeInTheDocument()
    expect(screen.getByText('Try a broader window, mode, or search.')).toBeInTheDocument()
    expect(screen.queryByTestId('implemented-summary-bar')).not.toBeInTheDocument()
  })

  test('shows the empty state when no recommendations match filters', async () => {
    mockRequests({
      ...recommendationsPayload,
      summary: {
        ...recommendationsPayload.summary,
        total_recommendations: 0,
        implemented_recommendations: 0,
        high_priority_recommendations: 0,
        clusters_covered: 0,
        create_new_page_recommendations: 0,
        expand_existing_page_recommendations: 0,
        strengthen_cluster_recommendations: 0,
        improve_internal_support_recommendations: 0,
        counts_by_type: {
          MISSING_SUPPORTING_CONTENT: 0,
          THIN_CLUSTER: 0,
          EXPAND_EXISTING_PAGE: 0,
          MISSING_STRUCTURAL_PAGE_TYPE: 0,
          INTERNAL_LINKING_SUPPORT: 0,
        },
        counts_by_page_type: {
          home: 0,
          category: 0,
          product: 0,
          service: 0,
          blog_article: 0,
          blog_index: 0,
          contact: 0,
          about: 0,
          faq: 0,
          location: 0,
          legal: 0,
          utility: 0,
          other: 0,
        },
      },
      items: [],
      implemented_items: [],
      implemented_total: 0,
      total_items: 0,
      total_pages: 0,
    })

    renderContentRecommendations('/sites/5/content-recommendations/active?active_crawl_id=11&baseline_crawl_id=10')

    expect(await screen.findByText('No content recommendations matched the current view')).toBeInTheDocument()
  })
})
