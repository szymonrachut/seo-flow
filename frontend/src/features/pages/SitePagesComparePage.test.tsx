import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { I18nextProvider } from 'react-i18next'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { afterEach, describe, expect, test, vi } from 'vitest'

import i18n from '../../i18n'
import { createTestQueryClient, jsonResponse } from '../../test/testUtils'
import { formatCrawlDateTime } from '../../utils/format'
import { SiteWorkspaceLayout } from '../sites/SiteWorkspaceLayout'
import { SitePagesComparePage } from './SitePagesComparePage'

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
      finished_at: '2026-03-14T12:09:00Z',
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

const comparePayload = {
  context: {
    site_id: 5,
    site_domain: 'example.com',
    active_crawl_id: 11,
    baseline_crawl_id: 10,
    compare_available: true,
    compare_unavailable_reason: null,
    active_crawl: {
      id: 11,
      status: 'finished',
      created_at: '2026-03-14T12:00:00Z',
      started_at: '2026-03-14T12:01:00Z',
      finished_at: '2026-03-14T12:09:00Z',
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
    shared_urls: 39,
    new_urls: 2,
    missing_urls: 1,
    changed_urls: 5,
    improved_urls: 3,
    worsened_urls: 2,
    unchanged_urls: 34,
    status_changed_urls: 1,
    title_changed_urls: 2,
    meta_description_changed_urls: 1,
    h1_changed_urls: 1,
    canonical_changed_urls: 0,
    noindex_changed_urls: 0,
    priority_improved_urls: 2,
    priority_worsened_urls: 1,
    internal_linking_improved_urls: 2,
    internal_linking_worsened_urls: 1,
    content_growth_urls: 1,
    content_drop_urls: 1,
  },
  items: [
    {
      url: 'https://example.com/improved',
      normalized_url: 'https://example.com/improved',
      active_page_id: 101,
      baseline_page_id: 91,
      change_type: 'improved',
      changed_fields: ['title', 'h1', 'priority_score'],
      change_rationale: 'title refined and internal links improved',
      active_status_code: 200,
      baseline_status_code: 200,
      status_code_changed: false,
      active_title: 'Improved title',
      baseline_title: 'Old title',
      title_changed: true,
      active_meta_description: 'Updated meta',
      baseline_meta_description: 'Old meta',
      meta_description_changed: true,
      active_h1: 'Improved heading',
      baseline_h1: 'Old heading',
      h1_changed: true,
      active_canonical_url: 'https://example.com/improved',
      baseline_canonical_url: 'https://example.com/improved',
      canonical_changed: false,
      active_noindex_like: false,
      baseline_noindex_like: false,
      noindex_changed: false,
      active_word_count: 450,
      baseline_word_count: 300,
      delta_word_count: 150,
      word_count_trend: 'improved',
      active_response_time_ms: 120,
      baseline_response_time_ms: 180,
      delta_response_time_ms: -60,
      response_time_trend: 'improved',
      active_incoming_internal_links: 8,
      baseline_incoming_internal_links: 3,
      delta_incoming_internal_links: 5,
      active_incoming_internal_linking_pages: 4,
      baseline_incoming_internal_linking_pages: 2,
      delta_incoming_internal_linking_pages: 2,
      internal_linking_trend: 'improved',
      active_priority_score: 72,
      baseline_priority_score: 55,
      delta_priority_score: 17,
      priority_trend: 'improved',
      active_priority_level: 'high',
      baseline_priority_level: 'medium',
      active_primary_opportunity_type: 'QUICK_WINS',
    },
  ],
  page: 1,
  page_size: 25,
  total_items: 1,
  total_pages: 1,
}

function LocationEcho() {
  const location = useLocation()
  return <output data-testid="location-search">{location.search}</output>
}

function renderWorkspace(route: string) {
  const queryClient = createTestQueryClient()
  const user = userEvent.setup()

  const result = render(
    <I18nextProvider i18n={i18n}>
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[route]}>
          <Routes>
            <Route path="/sites/:siteId" element={<SiteWorkspaceLayout />}>
              <Route path="changes/pages" element={<><SitePagesComparePage /><LocationEcho /></>} />
            </Route>
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    </I18nextProvider>,
  )

  return {
    user,
    ...result,
  }
}

describe('SitePagesComparePage', () => {
  test('renders pages compare rows and deep links', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((input) => {
      const url = String(input)
      if (url.includes('/sites/5/pages')) {
        return jsonResponse(comparePayload)
      }
      if (url.includes('/sites/5')) {
        return jsonResponse(sitePayload)
      }
      throw new Error(`Unexpected request: ${url}`)
    })

    renderWorkspace('/sites/5/changes/pages?active_crawl_id=11&baseline_crawl_id=10')

    expect(await screen.findByText('Pages Changes')).toBeInTheDocument()
    expect(
      screen.getByText(
        i18n.t('pagesCompare.description', {
          active: formatCrawlDateTime(comparePayload.context.active_crawl),
          baseline: formatCrawlDateTime(comparePayload.context.baseline_crawl),
        }),
      ),
    ).toBeInTheDocument()
    expect((await screen.findAllByText('https://example.com/improved')).length).toBeGreaterThan(0)
    expect(screen.getByText('Improved title')).toBeInTheDocument()
    expect(screen.getByText('Old title')).toBeInTheDocument()
    expect(
      screen
        .getAllByRole('link', { name: 'Open active pages' })
        .some((link) => link.getAttribute('href') === '/jobs/11/pages?url_contains=https%3A%2F%2Fexample.com%2Fimproved'),
    ).toBe(true)
    expect(
      screen
        .getAllByRole('link', { name: 'Open opportunities compare' })
        .some((link) => link.getAttribute('href') === '/sites/5/changes/opportunities?active_crawl_id=11&baseline_crawl_id=10'),
    ).toBe(true)
  })

  test('keeps compare filters in the URL', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((input) => {
      const url = String(input)
      if (url.includes('/sites/5/pages')) {
        return jsonResponse(comparePayload)
      }
      if (url.includes('/sites/5')) {
        return jsonResponse(sitePayload)
      }
      throw new Error(`Unexpected request: ${url}`)
    })

    const { user } = renderWorkspace('/sites/5/changes/pages?active_crawl_id=11&baseline_crawl_id=10&page=2')

    await screen.findAllByText('https://example.com/improved')
    await user.click(screen.getByRole('button', { name: 'New URLs' }))

    await waitFor(() => expect(screen.getByTestId('location-search')).toHaveTextContent('change_type=new'))
    expect(screen.getByTestId('location-search')).toHaveTextContent('page=1')
  })
})
