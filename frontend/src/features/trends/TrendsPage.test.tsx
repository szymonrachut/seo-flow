import { screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, test, vi } from 'vitest'

import { jsonResponse, renderRoute } from '../../test/testUtils'
import { TrendsPage } from './TrendsPage'

afterEach(() => {
  vi.restoreAllMocks()
})

const overviewPayload = {
  crawl_job_id: 8,
  site_id: 1,
  site_domain: 'example.com',
  default_baseline_job_id: 7,
  baseline_candidates: [
    {
      id: 7,
      status: 'finished',
      created_at: '2026-03-10T10:00:00Z',
      started_at: '2026-03-10T10:01:00Z',
      finished_at: '2026-03-10T10:03:00Z',
      root_url: 'https://example.com/',
    },
  ],
  available_gsc_ranges: ['last_28_days', 'last_90_days'],
}

const crawlComparePayload = {
  baseline_job: overviewPayload.baseline_candidates[0],
  target_job: {
    id: 8,
    status: 'finished',
    created_at: '2026-03-14T10:00:00Z',
    started_at: '2026-03-14T10:01:00Z',
    finished_at: '2026-03-14T10:03:00Z',
    root_url: 'https://example.com/',
  },
  summary: {
    baseline_job_id: 7,
    target_job_id: 8,
    gsc_date_range: 'last_28_days',
    shared_urls: 4,
    new_urls: 1,
    missing_urls: 1,
    improved_urls: 1,
    worsened_urls: 1,
    unchanged_urls: 2,
    resolved_issues_total: 2,
    added_issues_total: 1,
  },
  items: [
    {
      url: 'https://example.com/improved',
      normalized_url: 'https://example.com/improved',
      baseline_page_id: 11,
      target_page_id: 21,
      new_in_target: false,
      missing_in_target: false,
      present_in_both: true,
      change_type: 'improved',
      issues_resolved_count: 1,
      issues_added_count: 0,
      resolved_issues: ['non_indexable_like'],
      added_issues: [],
      change_rationale: 'resolved non_indexable_like and gained 2 internal links',
      baseline_status_code: 200,
      target_status_code: 200,
      baseline_canonical_url: 'https://example.com/improved',
      target_canonical_url: 'https://example.com/improved',
      baseline_noindex_like: true,
      target_noindex_like: false,
      baseline_non_indexable_like: true,
      target_non_indexable_like: false,
      baseline_title_length: 40,
      target_title_length: 41,
      baseline_meta_description_length: 90,
      target_meta_description_length: 91,
      baseline_h1_count: 1,
      target_h1_count: 1,
      baseline_word_count: 110,
      target_word_count: 240,
      baseline_images_missing_alt_count: 2,
      target_images_missing_alt_count: 0,
      baseline_schema_count: 0,
      target_schema_count: 2,
      baseline_html_size_bytes: 2200,
      target_html_size_bytes: 2400,
      baseline_was_rendered: false,
      target_was_rendered: false,
      baseline_js_heavy_like: false,
      target_js_heavy_like: false,
      baseline_response_time_ms: 520,
      target_response_time_ms: 160,
      baseline_incoming_internal_links: 1,
      target_incoming_internal_links: 3,
      baseline_incoming_internal_linking_pages: 1,
      target_incoming_internal_linking_pages: 3,
      baseline_priority_score: 22,
      target_priority_score: 48,
      baseline_priority_level: 'low',
      target_priority_level: 'high',
      baseline_opportunity_count: 0,
      target_opportunity_count: 1,
      baseline_primary_opportunity_type: null,
      target_primary_opportunity_type: 'QUICK_WINS',
      baseline_opportunity_types: [],
      target_opportunity_types: ['QUICK_WINS'],
      delta_priority_score: 26,
      delta_word_count: 130,
      delta_schema_count: 2,
      delta_response_time_ms: -360,
      delta_incoming_internal_links: 2,
      delta_incoming_internal_linking_pages: 2,
    },
  ],
  page: 1,
  page_size: 25,
  total_items: 1,
  total_pages: 1,
}

const gscComparePayload = {
  summary: {
    crawl_job_id: 8,
    baseline_gsc_range: 'last_90_days',
    target_gsc_range: 'last_28_days',
    baseline: { clicks: 60, impressions: 650, ctr: 0.0923, position: 7.1, top_queries_count: 4 },
    target: { clicks: 72, impressions: 723, ctr: 0.0996, position: 6.5, top_queries_count: 7 },
    delta_clicks: 12,
    delta_impressions: 73,
    delta_ctr: 0.0073,
    delta_position: -0.6,
    delta_top_queries_count: 3,
    improved_urls: 2,
    worsened_urls: 1,
    flat_urls: 1,
  },
  items: [
    {
      page_id: 21,
      url: 'https://example.com/improved',
      normalized_url: 'https://example.com/improved',
      has_baseline_data: true,
      has_target_data: true,
      baseline_clicks: 30,
      target_clicks: 40,
      delta_clicks: 10,
      baseline_impressions: 300,
      target_impressions: 500,
      delta_impressions: 200,
      baseline_ctr: 0.1,
      target_ctr: 0.08,
      delta_ctr: -0.02,
      baseline_position: 10,
      target_position: 6,
      delta_position: -4,
      baseline_top_queries_count: 2,
      target_top_queries_count: 4,
      delta_top_queries_count: 2,
      overall_trend: 'improved',
      clicks_trend: 'improved',
      impressions_trend: 'improved',
      ctr_trend: 'worsened',
      position_trend: 'improved',
      top_queries_trend: 'improved',
      rationale: 'clicks up by 10 and position improved by 4.00',
      has_technical_issue: false,
      priority_score: 48,
      priority_level: 'high',
      primary_opportunity_type: 'QUICK_WINS',
    },
  ],
  page: 1,
  page_size: 25,
  total_items: 1,
  total_pages: 1,
}

function resolveUrl(input: string | URL | RequestInfo): string {
  if (typeof input === 'string') {
    return input
  }

  if (input instanceof Request) {
    return input.url
  }

  if (input instanceof URL) {
    return input.toString()
  }

  return String(input)
}

describe('TrendsPage', () => {
  test('renders trends view with both compare sections and export links', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((input) => {
      const url = resolveUrl(input)
      if (url.includes('/crawl-jobs/8/trends/overview')) {
        return jsonResponse(overviewPayload)
      }
      if (url.includes('/crawl-jobs/8/trends/crawl')) {
        return jsonResponse(crawlComparePayload)
      }
      if (url.includes('/crawl-jobs/8/trends/gsc')) {
        return jsonResponse(gscComparePayload)
      }
      throw new Error(`Unexpected request: ${url}`)
    })

    renderRoute(<TrendsPage />, {
      path: '/jobs/:jobId/trends',
      route: '/jobs/8/trends?baseline_job_id=7',
    })

    expect(screen.getByText('Trends for job #8')).toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: 'Crawl compare' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'GSC compare' })).toBeInTheDocument()
    expect(screen.getByText('resolved non_indexable_like and gained 2 internal links')).toBeInTheDocument()
    expect(screen.getByText('clicks up by 10 and position improved by 4.00')).toBeInTheDocument()

    expect(screen.getByRole('link', { name: 'Export crawl compare CSV' })).toHaveAttribute(
      'href',
      expect.stringContaining('baseline_job_id=7'),
    )
    expect(screen.getByRole('link', { name: 'Export GSC compare CSV' })).toHaveAttribute(
      'href',
      expect.stringContaining('gsc-compare.csv'),
    )
  })

  test('quick filters keep trends state in the URL', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((input) => {
      const url = resolveUrl(input)
      if (url.includes('/crawl-jobs/8/trends/overview')) {
        return jsonResponse(overviewPayload)
      }
      if (url.includes('/crawl-jobs/8/trends/crawl')) {
        return jsonResponse(crawlComparePayload)
      }
      if (url.includes('/crawl-jobs/8/trends/gsc')) {
        return jsonResponse(gscComparePayload)
      }
      throw new Error(`Unexpected request: ${url}`)
    })

    const { user } = renderRoute(<TrendsPage />, {
      path: '/jobs/:jobId/trends',
      route: '/jobs/8/trends?baseline_job_id=7',
      showLocation: true,
    })

    await screen.findByRole('heading', { name: 'Crawl compare' })
    await user.click(screen.getByRole('button', { name: 'Worsened' }))

    await waitFor(() => expect(screen.getByTestId('location-search')).toHaveTextContent('change_type=worsened'))

    await user.click(screen.getByRole('button', { name: 'Clicks up' }))

    await waitFor(() => expect(screen.getByTestId('location-search')).toHaveTextContent('clicks_trend=improved'))
  })

  test('shows empty crawl baseline state when no compare candidate exists', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((input) => {
      const url = resolveUrl(input)
      if (url.includes('/crawl-jobs/8/trends/overview')) {
        return jsonResponse({
          ...overviewPayload,
          default_baseline_job_id: null,
          baseline_candidates: [],
        })
      }
      if (url.includes('/crawl-jobs/8/trends/gsc')) {
        return jsonResponse({ ...gscComparePayload, items: [], total_items: 0, total_pages: 0 })
      }
      throw new Error(`Unexpected request: ${url}`)
    })

    renderRoute(<TrendsPage />, {
      path: '/jobs/:jobId/trends',
      route: '/jobs/8/trends',
    })

    expect(await screen.findByText('No baseline crawl job available')).toBeInTheDocument()
    expect(screen.getByText('No GSC compare rows matched the current filters')).toBeInTheDocument()
  })
})
