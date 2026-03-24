import { screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, test, vi } from 'vitest'

import { jsonResponse, renderRoute } from '../../test/testUtils'
import { CannibalizationPage } from './CannibalizationPage'

afterEach(() => {
  vi.restoreAllMocks()
})

const clustersPayload = {
  summary: {
    crawl_job_id: 9,
    gsc_date_range: 'last_28_days',
    total_candidate_pages: 4,
    pages_in_conflicts: 4,
    clusters_count: 2,
    critical_clusters: 0,
    high_severity_clusters: 1,
    high_impact_clusters: 1,
    no_clear_primary_clusters: 1,
    merge_candidates: 1,
    split_intent_candidates: 1,
    reinforce_primary_candidates: 0,
    low_value_overlap_clusters: 0,
    average_weighted_overlap: 0.76,
  },
  items: [
    {
      cluster_id: 'cannibalization-9-31',
      urls_count: 2,
      shared_queries_count: 2,
      shared_query_impressions: 180,
      shared_query_clicks: 18,
      weighted_overlap: 0.96,
      severity: 'high',
      impact_level: 'medium',
      recommendation_type: 'MERGE_CANDIDATE',
      has_clear_primary: true,
      dominant_url: 'https://example.com/alpha-primary',
      dominant_url_page_id: 31,
      dominant_url_confidence: 0.74,
      dominant_url_score: 0.67,
      sample_queries: ['alpha query', 'alpha guide'],
      candidate_urls: [
        {
          page_id: 31,
          url: 'https://example.com/alpha-primary',
          priority_score: 66,
          priority_level: 'high',
          primary_opportunity_type: 'QUICK_WINS',
          clicks: 25,
          impressions: 300,
          position: 4.5,
          query_count: 3,
          shared_query_count: 2,
          exclusive_query_count: 1,
          click_share: 0.74,
          impression_share: 0.68,
          avg_shared_position: 3.5,
          strongest_competing_url: 'https://example.com/alpha-support',
          is_dominant: true,
        },
        {
          page_id: 32,
          url: 'https://example.com/alpha-support',
          priority_score: 41,
          priority_level: 'medium',
          primary_opportunity_type: 'LOW_HANGING_FRUIT',
          clicks: 8,
          impressions: 95,
          position: 7.4,
          query_count: 2,
          shared_query_count: 2,
          exclusive_query_count: 0,
          click_share: 0.26,
          impression_share: 0.32,
          avg_shared_position: 6.7,
          strongest_competing_url: 'https://example.com/alpha-primary',
          is_dominant: false,
        },
      ],
      rationale: 'Two URLs share 2 meaningful queries and one clear primary URL leads the cluster.',
    },
  ],
  page: 1,
  page_size: 25,
  total_items: 1,
  total_pages: 1,
}

const detailsPayload = {
  crawl_job_id: 9,
  gsc_date_range: 'last_28_days',
  page_id: 32,
  url: 'https://example.com/alpha-support',
  normalized_url: 'https://example.com/alpha-support',
  has_cannibalization: true,
  cluster_id: 'cannibalization-9-31',
  severity: 'high',
  impact_level: 'medium',
  recommendation_type: 'MERGE_CANDIDATE',
  rationale: 'Two URLs share 2 meaningful queries and one clear primary URL leads the cluster.',
  competing_urls_count: 1,
  strongest_competing_url: 'https://example.com/alpha-primary',
  strongest_competing_page_id: 31,
  common_queries_count: 2,
  weighted_overlap_by_impressions: 1,
  weighted_overlap_by_clicks: 1,
  overlap_ratio: 1,
  overlap_strength: 0.98,
  shared_top_queries: ['alpha query', 'alpha guide'],
  dominant_competing_url: 'https://example.com/alpha-primary',
  dominant_competing_page_id: 31,
  overlaps: [
    {
      competing_page_id: 31,
      competing_url: 'https://example.com/alpha-primary',
      common_queries_count: 2,
      weighted_overlap_by_impressions: 1,
      weighted_overlap_by_clicks: 1,
      overlap_ratio: 1,
      pair_overlap_score: 0.98,
      shared_query_impressions: 70,
      shared_query_clicks: 7,
      shared_top_queries: ['alpha query', 'alpha guide'],
      dominant_url: 'https://example.com/alpha-primary',
      dominance_score: 0.71,
      dominance_confidence: 0.74,
      competitor_priority_score: 66,
      competitor_priority_level: 'high',
      competitor_primary_opportunity_type: 'QUICK_WINS',
      competitor_clicks: 25,
      competitor_impressions: 300,
      competitor_position: 4.5,
    },
  ],
}

describe('CannibalizationPage', () => {
  test('renders summary cards, clusters and deep links', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((input) => {
      const url = String(input)
      if (url.includes('/crawl-jobs/9/cannibalization?')) {
        return jsonResponse(clustersPayload)
      }
      throw new Error(`Unexpected request: ${url}`)
    })

    renderRoute(<CannibalizationPage />, {
      path: '/jobs/:jobId/cannibalization',
      route: '/jobs/9/cannibalization',
    })

    expect(screen.getByText('Cannibalization for job #9')).toBeInTheDocument()
    expect((await screen.findAllByText('https://example.com/alpha-primary')).length).toBeGreaterThan(0)
    expect(screen.getByText('Clusters')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Export cannibalization CSV' })).toHaveAttribute(
      'href',
      expect.stringContaining('/crawl-jobs/9/export/cannibalization.csv'),
    )
    expect(screen.getAllByRole('link', { name: 'Open page' })[0]).toHaveAttribute(
      'href',
      expect.stringContaining('/jobs/9/pages?gsc_date_range=last_28_days&url_contains=https%3A%2F%2Fexample.com%2Falpha-primary'),
    )
    expect(screen.getAllByRole('button', { name: 'Inspect overlap' }).length).toBeGreaterThan(0)
  })

  test('keeps filters and sorting in the query string', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((input) => {
      const url = String(input)
      if (url.includes('/crawl-jobs/9/cannibalization?')) {
        return jsonResponse(clustersPayload)
      }
      throw new Error(`Unexpected request: ${url}`)
    })

    const { user } = renderRoute(<CannibalizationPage />, {
      path: '/jobs/:jobId/cannibalization',
      route: '/jobs/9/cannibalization?page=2',
      showLocation: true,
    })

    expect((await screen.findAllByText('https://example.com/alpha-primary')).length).toBeGreaterThan(0)
    await user.click(screen.getByRole('button', { name: 'Merge candidate' }))

    await waitFor(() => expect(screen.getByTestId('location-search')).toHaveTextContent('recommendation_type=MERGE_CANDIDATE'))
    expect(screen.getByTestId('location-search')).toHaveTextContent('page=1')

    await user.click(screen.getByRole('button', { name: 'Sort by Dominant URL' }))
    await waitFor(() => expect(screen.getByTestId('location-search')).toHaveTextContent('sort_by=dominant_url_confidence'))
  })

  test('renders empty state and focused page details deep-link', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((input) => {
      const url = String(input)
      if (url.includes('/crawl-jobs/9/cannibalization/pages/32')) {
        return jsonResponse(detailsPayload)
      }
      if (url.includes('/crawl-jobs/9/cannibalization?')) {
        return jsonResponse({
          ...clustersPayload,
          items: [],
          total_items: 0,
          total_pages: 0,
        })
      }
      throw new Error(`Unexpected request: ${url}`)
    })

    renderRoute(<CannibalizationPage />, {
      path: '/jobs/:jobId/cannibalization',
      route: '/jobs/9/cannibalization?page_id=32',
    })

    expect(await screen.findByText('https://example.com/alpha-support')).toBeInTheDocument()
    expect(screen.getByText('Focused overlap')).toBeInTheDocument()
    expect(screen.getByText('No cannibalization clusters matched the current view')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Open competitor' })).toHaveAttribute(
      'href',
      expect.stringContaining('/jobs/9/pages?gsc_date_range=last_28_days&url_contains=https%3A%2F%2Fexample.com%2Falpha-primary'),
    )
  })
})
