import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, test, vi } from 'vitest'

import { jsonResponse, renderRoute } from '../../test/testUtils'
import { GscPage } from './GscPage'

afterEach(() => {
  vi.restoreAllMocks()
})

function requestUrl(input: string | URL | RequestInfo): string {
  if (typeof input === 'string') {
    return input
  }
  if (input instanceof Request) {
    return input.url
  }
  return String(input)
}

const summaryPayload = {
  crawl_job_id: 3,
  site_id: 1,
  auth_connected: true,
  selected_property_uri: 'sc-domain:example.com',
  selected_property_permission_level: 'siteOwner',
  available_date_ranges: ['last_28_days', 'last_90_days'],
  ranges: [
    {
      date_range_label: 'last_28_days',
      imported_pages: 1,
      pages_with_impressions: 1,
      pages_with_clicks: 1,
      pages_with_top_queries: 1,
      total_top_queries: 2,
      opportunities_with_impressions: 1,
      opportunities_with_clicks: 1,
      last_imported_at: '2026-03-14T08:00:00Z',
    },
    {
      date_range_label: 'last_90_days',
      imported_pages: 1,
      pages_with_impressions: 1,
      pages_with_clicks: 1,
      pages_with_top_queries: 1,
      total_top_queries: 4,
      opportunities_with_impressions: 1,
      opportunities_with_clicks: 1,
      last_imported_at: '2026-03-14T08:00:00Z',
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

const pagesPayload = {
  items: [
    {
      id: 1,
      crawl_job_id: 3,
      url: 'https://example.com/a',
      normalized_url: 'https://example.com/a',
      final_url: 'https://example.com/a',
      status_code: 200,
      title: 'Alpha',
      title_length: 45,
      meta_description: 'Meta A',
      meta_description_length: 95,
      h1: 'Heading A',
      h1_length: 9,
      h1_count: 1,
      h2_count: 3,
      canonical_url: 'https://example.com/a',
      canonical_target_url: 'https://example.com/a',
      canonical_target_status_code: 200,
      robots_meta: 'index,follow',
      x_robots_tag: null,
      content_type: 'text/html',
      word_count: 320,
      content_text_hash: 'hash-a',
      images_count: 4,
      images_missing_alt_count: 1,
      html_size_bytes: 2048,
      was_rendered: false,
      render_attempted: false,
      fetch_mode_used: 'http',
      js_heavy_like: false,
      render_reason: null,
      render_error_message: null,
      schema_present: true,
      schema_count: 1,
      schema_types_json: ['Article'],
      schema_types_text: 'Article',
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
      title_too_short: false,
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
      thin_content: true,
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
      gsc_fetched_at_28d: '2026-03-14T08:00:00Z',
      top_queries_count_28d: 2,
      has_gsc_28d: true,
      clicks_90d: 30,
      impressions_90d: 920,
      ctr_90d: 0.0326,
      position_90d: 9.1,
      gsc_fetched_at_90d: '2026-03-14T08:00:00Z',
      top_queries_count_90d: 4,
      has_gsc_90d: true,
      has_technical_issue: true,
      technical_issue_count: 2,
      created_at: '2026-03-13T12:00:00Z',
    },
  ],
  page: 1,
  page_size: 25,
  total_items: 1,
  total_pages: 1,
  available_status_codes: [200],
  has_gsc_integration: true,
}

const topQueriesPayload = {
  items: [
    {
      id: 1,
      page_id: 1,
      url: 'https://example.com/a',
      date_range_label: 'last_28_days',
      query: 'seo alpha',
      clicks: 10,
      impressions: 120,
      ctr: 0.0833,
      position: 6.1,
      fetched_at: '2026-03-14T08:00:00Z',
    },
    {
      id: 2,
      page_id: 1,
      url: 'https://example.com/a',
      date_range_label: 'last_28_days',
      query: 'alpha guide',
      clicks: 2,
      impressions: 80,
      ctr: 0.025,
      position: 9.4,
      fetched_at: '2026-03-14T08:00:00Z',
    },
  ],
  page: 1,
  page_size: 10,
  total_items: 2,
  total_pages: 1,
  page_context: {
    id: 1,
    url: 'https://example.com/a',
    title: 'Alpha',
    normalized_url: 'https://example.com/a',
    clicks_28d: 12,
    impressions_28d: 340,
    ctr_28d: 0.0353,
    position_28d: 8.4,
    clicks_90d: 30,
    impressions_90d: 920,
    ctr_90d: 0.0326,
    position_90d: 9.1,
    has_technical_issue: true,
    technical_issue_count: 2,
    top_queries_count_28d: 2,
    top_queries_count_90d: 4,
  },
}

describe('GscPage', () => {
  test('builds the OAuth start link for the current frontend origin', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation((input) => {
      const url = requestUrl(input)

      if (url.includes('/crawl-jobs/3/gsc/summary')) {
        return jsonResponse({ ...summaryPayload, auth_connected: false, selected_property_uri: null })
      }
      if (url.includes('/crawl-jobs/3/pages')) {
        return jsonResponse(pagesPayload)
      }

      throw new Error(`Unexpected request: ${url}`)
    })

    renderRoute(<GscPage />, {
      path: '/jobs/:jobId/gsc',
      route: '/jobs/3/gsc',
    })

    const connectLink = await screen.findByRole('link', { name: 'Connect GSC' }, { timeout: 5000 })
    const expectedRedirect = encodeURIComponent(`${window.location.origin}/jobs/3/gsc`)
    expect(connectLink).toHaveAttribute(
      'href',
      expect.stringContaining(`/crawl-jobs/3/gsc/oauth/start?frontend_redirect_url=${expectedRedirect}`),
    )

    expect(fetchMock).toHaveBeenCalled()
  })

  test('renders the GSC section, top queries and exports', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation((input) => {
      const url = requestUrl(input)

      if (url.includes('/crawl-jobs/3/gsc/summary')) {
        return jsonResponse(summaryPayload)
      }
      if (url.includes('/crawl-jobs/3/gsc/properties')) {
        return jsonResponse(propertiesPayload)
      }
      if (url.includes('/crawl-jobs/3/pages')) {
        return jsonResponse(pagesPayload)
      }
      if (url.includes('/crawl-jobs/3/gsc/top-queries')) {
        return jsonResponse(topQueriesPayload)
      }

      throw new Error(`Unexpected request: ${url}`)
    })

    const { user } = renderRoute(<GscPage />, {
      path: '/jobs/:jobId/gsc',
      route: '/jobs/3/gsc?page_id=1&gsc_date_range=last_28_days',
      showLocation: true,
    })

    expect(screen.getByText('GSC opportunities for job #3')).toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: 'Top queries per URL' })).toBeInTheDocument()
    expect(screen.getByText('sc-domain:example.com')).toBeInTheDocument()

    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByText('Alpha')).toBeInTheDocument()
    expect(within(dialog).getByText('https://example.com/a')).toBeInTheDocument()
    expect(within(dialog).getByText('seo alpha')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Export top queries' })).toHaveAttribute(
      'href',
      expect.stringContaining('/crawl-jobs/3/export/gsc-top-queries.csv'),
    )

    await user.type(within(dialog).getByRole('textbox', { name: 'Exclude phrase' }), 'guide')

    await waitFor(() => expect(screen.getByTestId('location-search')).toHaveTextContent('query_excludes=guide'))
    expect(fetchMock.mock.calls.some(([input]) => requestUrl(input).includes('query_excludes=guide'))).toBe(true)
    expect(screen.getByRole('link', { name: 'Export top queries' })).toHaveAttribute(
      'href',
      expect.stringContaining('query_excludes=guide'),
    )

    await user.click(screen.getByRole('button', { name: 'Impressions + issue' }))

    await waitFor(() => expect(screen.getByTestId('location-search')).toHaveTextContent('has_technical_issue=true'))
    expect(screen.getByTestId('location-search')).toHaveTextContent('gsc_impressions_min=1')

    await user.click(within(dialog).getByRole('button', { name: 'Sort by CTR' }))

    await waitFor(() => expect(screen.getByTestId('location-search')).toHaveTextContent('queries_sort_by=ctr'))
    expect(fetchMock.mock.calls.some(([input]) => requestUrl(input).includes('/crawl-jobs/3/gsc/top-queries'))).toBe(
      true,
    )

    await user.click(within(dialog).getByRole('button', { name: 'Close top queries' }))

    await waitFor(() => expect(screen.getByTestId('location-search')).not.toHaveTextContent('page_id=1'))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  }, 10000)

  test('sends custom top queries limit in the GSC import payload', async () => {
    let importPayload: Record<string, unknown> | null = null

    vi.spyOn(globalThis, 'fetch').mockImplementation((input, init) => {
      const url = requestUrl(input)

      if (url.includes('/crawl-jobs/3/gsc/summary')) {
        return jsonResponse(summaryPayload)
      }
      if (url.includes('/crawl-jobs/3/gsc/properties')) {
        return jsonResponse(propertiesPayload)
      }
      if (url.includes('/crawl-jobs/3/pages')) {
        return jsonResponse(pagesPayload)
      }
      if (url.includes('/crawl-jobs/3/gsc/import')) {
        importPayload = JSON.parse(String(init?.body ?? '{}')) as Record<string, unknown>
        return jsonResponse({
          crawl_job_id: 3,
          property_uri: 'sc-domain:example.com',
          imported_at: '2026-03-14T09:00:00Z',
          ranges: [
            {
              date_range_label: 'last_28_days',
              imported_url_metrics: 1,
              imported_top_queries: 1,
              pages_with_top_queries: 1,
              failed_pages: 0,
              errors: [],
            },
          ],
        })
      }

      throw new Error(`Unexpected request: ${url}`)
    })

    const { user } = renderRoute(<GscPage />, {
      path: '/jobs/:jobId/gsc',
      route: '/jobs/3/gsc?gsc_date_range=last_28_days',
    })

    const limitInput = await screen.findByRole('spinbutton', { name: 'Max top queries / URL' })
    await user.type(limitInput, '75')
    await user.click(screen.getByRole('button', { name: 'Import active range' }))

    await waitFor(() => expect(importPayload).not.toBeNull())
    expect(importPayload).toEqual({
      date_ranges: ['last_28_days'],
      top_queries_limit: 75,
    })
    expect(await screen.findByText('Pages with top queries: 1')).toBeInTheDocument()
    expect(screen.getByText('Stored top queries: 1')).toBeInTheDocument()
  })
})
