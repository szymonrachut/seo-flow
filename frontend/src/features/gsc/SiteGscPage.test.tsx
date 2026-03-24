import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { I18nextProvider } from 'react-i18next'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, test, vi } from 'vitest'

import i18n from '../../i18n'
import { createTestQueryClient, jsonResponse } from '../../test/testUtils'
import { SiteWorkspaceLayout } from '../sites/SiteWorkspaceLayout'
import { SiteGscPage } from './SiteGscPage'

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
  baseline_crawl: null,
  crawl_history: [],
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
  active_crawl_has_gsc_data: false,
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
      imported_pages: 12,
      pages_with_impressions: 7,
      pages_with_clicks: 4,
      pages_with_top_queries: 3,
      total_top_queries: 18,
      opportunities_with_impressions: 2,
      opportunities_with_clicks: 1,
      last_imported_at: '2026-03-14T09:00:00Z',
    },
    {
      date_range_label: 'last_90_days',
      imported_pages: 20,
      pages_with_impressions: 14,
      pages_with_clicks: 9,
      pages_with_top_queries: 6,
      total_top_queries: 33,
      opportunities_with_impressions: 5,
      opportunities_with_clicks: 3,
      last_imported_at: null,
    },
  ],
}

const propertiesPayload = [
  {
    property_uri: 'sc-domain:example.com',
    permission_level: 'siteOwner',
    matches_site: true,
    is_selected: true,
  },
]

function mockSiteGscFetch(summary = siteGscSummaryPayload) {
  return vi.spyOn(globalThis, 'fetch').mockImplementation((input, init) => {
    const url = String(input)
    const method = init?.method ?? 'GET'

    if (method === 'GET' && url.includes('/sites/5/gsc/summary')) {
      return jsonResponse(summary)
    }
    if (method === 'GET' && url.includes('/sites/5/gsc/properties')) {
      return jsonResponse(propertiesPayload)
    }
    if (method === 'GET' && url.includes('/sites/5') && !url.includes('/gsc')) {
      return jsonResponse(sitePayload)
    }

    return jsonResponse({})
  })
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
              <Route path="gsc">
                <Route index element={<SiteGscPage />} />
                <Route path="settings" element={<SiteGscPage mode="settings" />} />
                <Route path="import" element={<SiteGscPage mode="import" />} />
              </Route>
            </Route>
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    </I18nextProvider>,
  )

  return {
    user,
    queryClient,
    ...result,
  }
}

describe('SiteGscPage', () => {
  test('renders the GSC overview with status cards and shortcuts', async () => {
    mockSiteGscFetch()

    renderWorkspace('/sites/5/gsc?active_crawl_id=11&baseline_crawl_id=10')

    expect(await screen.findByText('Google Search Console status')).toBeInTheDocument()
    expect(screen.getByText('Property and connection')).toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: 'Open settings' })[0]).toHaveAttribute(
      'href',
      '/sites/5/gsc/settings?active_crawl_id=11&baseline_crawl_id=10',
    )
    expect(screen.getAllByRole('link', { name: 'Open import' })[0]).toHaveAttribute(
      'href',
      '/sites/5/gsc/import?active_crawl_id=11&baseline_crawl_id=10',
    )
    expect(screen.getByRole('link', { name: 'Open snapshot GSC details' })).toHaveAttribute('href', '/jobs/11/gsc')
  })

  test('renders the settings view and keeps property selection site-level', async () => {
    let selectedPropertyPayload: Record<string, unknown> | null = null

    vi.spyOn(globalThis, 'fetch').mockImplementation((input, init) => {
      const url = String(input)
      const method = init?.method ?? 'GET'

      if (method === 'GET' && url.includes('/sites/5/gsc/summary')) {
        return jsonResponse(siteGscSummaryPayload)
      }
      if (method === 'GET' && url.includes('/sites/5/gsc/properties')) {
        return jsonResponse(propertiesPayload)
      }
      if (method === 'GET' && url.includes('/sites/5') && !url.includes('/gsc')) {
        return jsonResponse(sitePayload)
      }
      if (method === 'PUT' && url.includes('/sites/5/gsc/property')) {
        selectedPropertyPayload = JSON.parse(String(init?.body ?? '{}')) as Record<string, unknown>
        return jsonResponse({ property_uri: 'sc-domain:example.com' })
      }

      throw new Error(`Unexpected request: ${method} ${url}`)
    })

    const { user } = renderWorkspace('/sites/5/gsc/settings?active_crawl_id=11')

    expect(await screen.findByText('Configure site property')).toBeInTheDocument()
    expect(screen.getByText('Property reuse across future crawls')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Save site property' }))

    await waitFor(() => expect(selectedPropertyPayload).toEqual({ property_uri: 'sc-domain:example.com' }))
  })

  test('renders the import view and imports into the active crawl snapshot', async () => {
    let importPayload: Record<string, unknown> | null = null
    let importUrl = ''

    vi.spyOn(globalThis, 'fetch').mockImplementation((input, init) => {
      const url = String(input)
      const method = init?.method ?? 'GET'

      if (method === 'GET' && url.includes('/sites/5/gsc/summary')) {
        return jsonResponse(siteGscSummaryPayload)
      }
      if (method === 'GET' && url.includes('/sites/5/gsc/properties')) {
        return jsonResponse(propertiesPayload)
      }
      if (method === 'GET' && url.includes('/sites/5') && !url.includes('/gsc')) {
        return jsonResponse(sitePayload)
      }
      if (method === 'POST' && url.includes('/sites/5/gsc/import')) {
        importUrl = url
        importPayload = JSON.parse(String(init?.body ?? '{}')) as Record<string, unknown>
        return jsonResponse({
          crawl_job_id: 11,
          property_uri: 'sc-domain:example.com',
          imported_at: '2026-03-14T09:00:00Z',
          ranges: [],
        })
      }

      throw new Error(`Unexpected request: ${method} ${url}`)
    })

    const { user } = renderWorkspace('/sites/5/gsc/import?active_crawl_id=11')

    expect(await screen.findByText('Import data into the active crawl')).toBeInTheDocument()

    const limitInput = await screen.findByRole('spinbutton', { name: 'Max top queries / URL' })
    await user.type(limitInput, '75')
    await user.click(screen.getByRole('button', { name: 'Import active crawl range' }))

    await waitFor(() => expect(importPayload).not.toBeNull())
    expect(importUrl).toContain('/sites/5/gsc/import?active_crawl_id=11')
    expect(importPayload).toEqual({
      date_ranges: ['last_28_days'],
      top_queries_limit: 75,
    })
  })
})
