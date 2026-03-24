import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, test, vi } from 'vitest'

import { jsonResponse, renderRoute } from '../../test/testUtils'
import { InternalLinkingPage } from './InternalLinkingPage'

afterEach(() => {
  vi.restoreAllMocks()
})

const overviewPayload = {
  crawl_job_id: 7,
  gsc_date_range: 'last_28_days',
  total_internal_pages: 9,
  issue_pages: 4,
  orphan_like_pages: 1,
  weakly_linked_important_pages: 1,
  low_anchor_diversity_pages: 1,
  exact_match_anchor_concentration_pages: 1,
  boilerplate_dominated_pages: 1,
  low_link_equity_pages: 1,
  median_link_equity_score: 42.3,
  average_anchor_diversity_score: 47.1,
  average_body_like_share: 0.38,
}

const issuesPayload = {
  crawl_job_id: 7,
  gsc_date_range: 'last_28_days',
  items: [
    {
      page_id: 21,
      url: 'https://example.com/orphan',
      normalized_url: 'https://example.com/orphan',
      priority_score: 56,
      priority_level: 'high',
      priority_rationale: 'URL shows demand but has weak internal linking support.',
      primary_opportunity_type: 'UNDERLINKED_OPPORTUNITIES',
      opportunity_types: ['UNDERLINKED_OPPORTUNITIES'],
      technical_issue_count: 0,
      clicks: 12,
      impressions: 240,
      ctr: 0.05,
      position: 9.4,
      incoming_internal_links: 1,
      incoming_internal_linking_pages: 1,
      incoming_follow_links: 0,
      incoming_follow_linking_pages: 0,
      incoming_nofollow_links: 1,
      body_like_links: 0,
      body_like_linking_pages: 0,
      boilerplate_like_links: 0,
      boilerplate_like_linking_pages: 0,
      body_like_share: 0,
      boilerplate_like_share: 0,
      unique_anchor_count: 0,
      anchor_diversity_score: 0,
      exact_match_anchor_count: 0,
      exact_match_anchor_ratio: 0,
      link_equity_score: 12.4,
      link_equity_rank: 9,
      internal_linking_score: 88,
      issue_count: 2,
      orphan_like: true,
      weakly_linked_important: false,
      low_anchor_diversity: false,
      exact_match_anchor_concentration: false,
      boilerplate_dominated: false,
      low_link_equity: true,
      issue_types: ['ORPHAN_LIKE', 'LOW_LINK_EQUITY'],
      primary_issue_type: 'ORPHAN_LIKE',
      top_anchor_samples: [
        {
          anchor_text: 'SEO services',
          links: 4,
          linking_pages: 4,
          exact_match: true,
          boilerplate_likely: true,
        },
      ],
      rationale: 'no followed internal links from crawled pages; link equity proxy is low at 12.4',
    },
  ],
  page: 1,
  page_size: 25,
  total_items: 1,
  total_pages: 1,
}

describe('InternalLinkingPage', () => {
  test('renders summary cards, results, export link and deep links', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((input) => {
      const url = String(input)
      if (url.includes('/crawl-jobs/7/internal-linking/overview')) {
        return jsonResponse(overviewPayload)
      }
      if (url.includes('/crawl-jobs/7/internal-linking/issues')) {
        return jsonResponse(issuesPayload)
      }

      throw new Error(`Unexpected request: ${url}`)
    })

    renderRoute(<InternalLinkingPage />, {
      path: '/jobs/:jobId/internal-linking',
      route: '/jobs/7/internal-linking',
    })

    expect(screen.getByText('Internal linking for job #7')).toBeInTheDocument()
    expect(await screen.findByText('https://example.com/orphan')).toBeInTheDocument()
    expect(screen.getByLabelText('Issue type')).toBeInTheDocument()
    expect(screen.getByLabelText('URL contains')).toBeInTheDocument()

    const issuePagesCard = screen.getByText('Issue pages').closest('article')
    expect(issuePagesCard).not.toBeNull()
    expect(within(issuePagesCard!).getByText('4')).toBeInTheDocument()

    expect(screen.getByRole('link', { name: 'Export internal linking CSV' })).toHaveAttribute(
      'href',
      expect.stringContaining('/crawl-jobs/7/export/internal-linking.csv'),
    )
    expect(screen.getByRole('link', { name: 'Open pages' })).toHaveAttribute(
      'href',
      expect.stringContaining('/jobs/7/pages?gsc_date_range=last_28_days&sort_by=priority_score&sort_order=desc&url_contains='),
    )
    expect(screen.getByRole('link', { name: 'Open opportunities' })).toHaveAttribute(
      'href',
      expect.stringContaining('/jobs/7/opportunities?gsc_date_range=last_28_days&opportunity_type=UNDERLINKED_OPPORTUNITIES'),
    )
    expect(screen.getByText('SEO services | 4')).toBeInTheDocument()
  })

  test('quick filters keep query-string state and export current filters', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((input) => {
      const url = String(input)
      if (url.includes('/crawl-jobs/7/internal-linking/overview')) {
        return jsonResponse(overviewPayload)
      }
      if (url.includes('/crawl-jobs/7/internal-linking/issues')) {
        return jsonResponse(issuesPayload)
      }

      throw new Error(`Unexpected request: ${url}`)
    })

    const { user } = renderRoute(<InternalLinkingPage />, {
      path: '/jobs/:jobId/internal-linking',
      route: '/jobs/7/internal-linking?page=2',
      showLocation: true,
    })

    await screen.findByText('https://example.com/orphan')
    await user.click(screen.getByRole('button', { name: 'Orphan-like' }))

    await waitFor(() => expect(screen.getByTestId('location-search')).toHaveTextContent('issue_type=ORPHAN_LIKE'))
    expect(screen.getByTestId('location-search')).toHaveTextContent('page=1')
    expect(screen.getByRole('link', { name: 'Export internal linking CSV' })).toHaveAttribute(
      'href',
      expect.stringContaining('issue_type=ORPHAN_LIKE'),
    )
    expect(screen.getByRole('link', { name: 'Export internal linking CSV' })).toHaveAttribute(
      'href',
      expect.not.stringContaining('page='),
    )
  })

  test('shows the empty state when no issues match filters', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((input) => {
      const url = String(input)
      if (url.includes('/crawl-jobs/7/internal-linking/overview')) {
        return jsonResponse({
          ...overviewPayload,
          issue_pages: 0,
          orphan_like_pages: 0,
          weakly_linked_important_pages: 0,
          low_anchor_diversity_pages: 0,
          exact_match_anchor_concentration_pages: 0,
          boilerplate_dominated_pages: 0,
          low_link_equity_pages: 0,
        })
      }
      if (url.includes('/crawl-jobs/7/internal-linking/issues')) {
        return jsonResponse({
          ...issuesPayload,
          items: [],
          total_items: 0,
          total_pages: 0,
        })
      }

      throw new Error(`Unexpected request: ${url}`)
    })

    renderRoute(<InternalLinkingPage />, {
      path: '/jobs/:jobId/internal-linking',
      route: '/jobs/7/internal-linking?issue_type=LOW_ANCHOR_DIVERSITY',
    })

    expect(await screen.findByText('No internal linking issues matched the current view')).toBeInTheDocument()
  })
})
