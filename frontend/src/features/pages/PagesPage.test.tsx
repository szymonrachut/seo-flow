import { screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, test, vi } from 'vitest'

import { deferred, jsonResponse, renderRoute, setTestLanguage } from '../../test/testUtils'
import { PagesPage } from './PagesPage'

const { copyText } = vi.hoisted(() => ({
  copyText: vi.fn().mockResolvedValue(true),
}))

vi.mock('../../utils/clipboard', () => ({
  copyText,
}))

afterEach(() => {
  vi.restoreAllMocks()
  copyText.mockReset()
  copyText.mockResolvedValue(true)
})

const taxonomySummaryPayload = {
  crawl_job_id: 3,
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

const pagePayload = {
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
      x_robots_tag: 'noindex',
      content_type: 'text/html',
      word_count: 320,
      content_text_hash: 'hash-a',
      images_count: 4,
      images_missing_alt_count: 1,
      html_size_bytes: 2048,
      was_rendered: true,
      render_attempted: true,
      fetch_mode_used: 'playwright',
      js_heavy_like: true,
      render_reason: 'low_text_many_scripts(words=1,scripts=6,links=0)',
      render_error_message: 'Navigation timeout',
      schema_present: true,
      schema_count: 2,
      schema_types_json: ['Article', 'BreadcrumbList'],
      schema_types_text: 'Article, BreadcrumbList',
      page_type: 'blog_article',
      page_bucket: 'informational',
      page_type_confidence: 0.94,
      page_type_version: '11.1-v1',
      page_type_rationale: 'schema:article(+7.0) | path:first_segment:blog(+5.5)',
      has_render_error: true,
      has_x_robots_tag: true,
      response_time_ms: 44,
      is_internal: true,
      depth: 1,
      fetched_at: '2026-03-13T12:00:00Z',
      error_message: null,
      title_missing: false,
      meta_description_missing: false,
      h1_missing: false,
      title_too_short: false,
      title_too_long: true,
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
      cannibalization_strongest_competing_url: 'https://example.com/b',
      cannibalization_strongest_competing_page_id: 2,
      cannibalization_dominant_competing_url: 'https://example.com/b',
      cannibalization_dominant_competing_page_id: 2,
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
  page_size: 25,
  total_items: 1,
  total_pages: 1,
  available_status_codes: [200, 404],
  has_gsc_integration: true,
}

function mockPagesRequests({
  pages = pagePayload,
  taxonomySummary = taxonomySummaryPayload,
}: {
  pages?: typeof pagePayload
  taxonomySummary?: typeof taxonomySummaryPayload
} = {}) {
  return vi.spyOn(globalThis, 'fetch').mockImplementation((input) => {
    const url = typeof input === 'string' ? input : input instanceof Request ? input.url : String(input)
    if (url.includes('/page-taxonomy/summary')) {
      return jsonResponse(taxonomySummary)
    }
    if (url.includes('/crawl-jobs/3/pages')) {
      return jsonResponse(pages)
    }
    throw new Error(`Unhandled fetch in PagesPage.test.tsx: ${url}`)
  })
}

describe('PagesPage', () => {
  test('renders the pages view with export and URL actions', async () => {
    mockPagesRequests()

    renderRoute(<PagesPage />, {
      path: '/jobs/:jobId/pages',
      route: '/jobs/3/pages',
    })

    expect(screen.getByText('Crawled pages for job #3')).toBeInTheDocument()
    expect(await screen.findByText('Alpha')).toBeInTheDocument()
    expect(screen.getByText('44 ms')).toBeInTheDocument()
    expect(screen.getByText('320')).toBeInTheDocument()
    expect(screen.getAllByText('4').length).toBeGreaterThan(0)
    expect(screen.getByText('2.0 KB')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Export full CSV' })).toHaveAttribute(
      'href',
      expect.stringContaining('/crawl-jobs/3/export/pages.csv'),
    )
    expect(screen.getByRole('link', { name: 'Open' })).toHaveAttribute('href', 'https://example.com/a')
    expect(screen.getByText('340')).toBeInTheDocument()
    expect(screen.getByText('3.53%')).toBeInTheDocument()
    expect(screen.getAllByText('Rendered').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Schema').length).toBeGreaterThan(0)
    expect(screen.getAllByText('X-Robots').length).toBeGreaterThan(0)
    expect(screen.getByText('Score 68')).toBeInTheDocument()
    expect(screen.getAllByText('High impressions, low CTR').length).toBeGreaterThan(0)
    expect(screen.getByText('URL has high impressions and low CTR with snippet issues.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Open cannibalization' })).toHaveAttribute(
      'href',
      expect.stringContaining('/jobs/3/cannibalization?gsc_date_range=last_28_days&page_id=1'),
    )
  })

  test('renders translated page UI in Polish', async () => {
    await setTestLanguage('pl')
    mockPagesRequests()

    renderRoute(<PagesPage />, {
      path: '/jobs/:jobId/pages',
      route: '/jobs/3/pages',
    })

    expect(screen.getByText('Zcrawlowane strony dla zadania #3')).toBeInTheDocument()
    expect(screen.getByText('Szybkie filtry stron')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Za krotki title' })).toBeInTheDocument()
    expect(await screen.findByRole('link', { name: 'Eksportuj pelny CSV' })).toBeInTheDocument()
  })

  test('shows the loading state while the request is pending', async () => {
    const pendingPagesRequest = deferred<Response>()
    vi.spyOn(globalThis, 'fetch').mockImplementation((input) => {
      const url = typeof input === 'string' ? input : input instanceof Request ? input.url : String(input)
      if (url.includes('/page-taxonomy/summary')) {
        return jsonResponse(taxonomySummaryPayload)
      }
      return pendingPagesRequest.promise
    })

    renderRoute(<PagesPage />, {
      path: '/jobs/:jobId/pages',
      route: '/jobs/3/pages',
    })

    expect(screen.getByText('Loading pages...')).toBeInTheDocument()
    pendingPagesRequest.resolve(new Response(JSON.stringify(pagePayload), { headers: { 'Content-Type': 'application/json' } }))
    await screen.findByText('Alpha')
  })

  test('shows the empty state when no pages match filters', async () => {
    mockPagesRequests({
      pages: {
        items: [],
        page: 1,
        page_size: 25,
        total_items: 0,
        total_pages: 0,
        available_status_codes: [],
        has_gsc_integration: false,
      },
    })

    renderRoute(<PagesPage />, {
      path: '/jobs/:jobId/pages',
      route: '/jobs/3/pages',
    })

    expect(await screen.findByText('No pages matched the current filters')).toBeInTheDocument()
  })

  test('shows the default filters and can expand advanced filters', async () => {
    mockPagesRequests()

    const { user } = renderRoute(<PagesPage />, {
      path: '/jobs/:jobId/pages',
      route: '/jobs/3/pages',
    })

    await screen.findByText('Alpha')
    expect(screen.getByLabelText('HTTP status')).toBeInTheDocument()
    expect(screen.getByLabelText('URL contains')).toBeInTheDocument()
    expect(screen.getByLabelText('Title contains')).toBeInTheDocument()
    expect(screen.getByLabelText('GSC clicks min')).toBeInTheDocument()
    expect(screen.queryByLabelText('Was rendered')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Show all filters' }))

    expect(screen.getByLabelText('Was rendered')).toBeInTheDocument()
    expect(screen.getByLabelText('Taxonomy confidence min (%)')).toBeInTheDocument()
    expect(screen.getByLabelText('Taxonomy confidence max (%)')).toBeInTheDocument()
    expect(screen.getByLabelText('JS-heavy-like')).toBeInTheDocument()
    expect(screen.getByLabelText('Schema present')).toBeInTheDocument()
    expect(screen.getByLabelText('Has render error')).toBeInTheDocument()
    expect(screen.getByLabelText('Has X-Robots-Tag')).toBeInTheDocument()
    expect(screen.getByLabelText('Has technical issue')).toBeInTheDocument()
    expect(screen.getByLabelText('GSC impressions min')).toBeInTheDocument()
    expect(screen.getByLabelText('Has cannibalization')).toBeInTheDocument()
    expect(screen.getByLabelText('Priority level')).toBeInTheDocument()
    expect(screen.getByLabelText('Opportunity type')).toBeInTheDocument()
    expect(screen.getByLabelText('Priority score min')).toBeInTheDocument()
  })

  test('auto-expands advanced filters when hidden filters are active', async () => {
    mockPagesRequests()

    renderRoute(<PagesPage />, {
      path: '/jobs/:jobId/pages',
      route: '/jobs/3/pages?was_rendered=true',
    })

    await screen.findByText('Alpha')
    expect(screen.getByLabelText('Was rendered')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Hide extra filters' })).toBeInTheDocument()
  })

  test('opens the GSC section for a page', async () => {
    mockPagesRequests()

    renderRoute(<PagesPage />, {
      path: '/jobs/:jobId/pages',
      route: '/jobs/3/pages?gsc_date_range=last_90_days',
    })

    await screen.findByText('Alpha')
    expect(screen.getByRole('link', { name: 'Open top queries' })).toHaveAttribute(
      'href',
      expect.stringContaining('/jobs/3/gsc?page_id=1&gsc_date_range=last_90_days'),
    )
  })

  test('quick filters keep state in the URL', async () => {
    mockPagesRequests()

    const { user } = renderRoute(<PagesPage />, {
      path: '/jobs/:jobId/pages',
      route: '/jobs/3/pages?page=2',
      showLocation: true,
    })

    await screen.findByText('Alpha')
    await user.click(screen.getByRole('button', { name: 'Title too short' }))

    await waitFor(() => expect(screen.getByTestId('location-search')).toHaveTextContent('title_too_short=true'))
    expect(screen.getByTestId('location-search')).toHaveTextContent('page=1')
    expect(screen.queryByLabelText('Was rendered')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Show all filters' })).toBeInTheDocument()
  })

  test('taxonomy badges toggle the page type filter in the URL', async () => {
    mockPagesRequests()

    const { user } = renderRoute(<PagesPage />, {
      path: '/jobs/:jobId/pages',
      route: '/jobs/3/pages',
      showLocation: true,
    })

    await screen.findByText('Alpha')

    const productBadge = screen.getByRole('button', { name: 'Product: 3' })
    await user.click(productBadge)

    await waitFor(() => expect(screen.getByTestId('location-search')).toHaveTextContent('page_type=product'))

    await user.click(productBadge)

    await waitFor(() => expect(screen.getByTestId('location-search')).not.toHaveTextContent('page_type=product'))
  })

  test('priority quick filters set opportunity query params', async () => {
    mockPagesRequests()

    const { user } = renderRoute(<PagesPage />, {
      path: '/jobs/:jobId/pages',
      route: '/jobs/3/pages',
      showLocation: true,
    })

    await screen.findByText('Alpha')
    await user.click(screen.getByRole('button', { name: 'High priority' }))

    await waitFor(() => expect(screen.getByTestId('location-search')).toHaveTextContent('priority_score_min=45'))
    expect(screen.getByTestId('location-search')).toHaveTextContent('sort_by=priority_score')

    await user.click(screen.getByRole('button', { name: 'Quick wins' }))

    await waitFor(() => expect(screen.getByTestId('location-search')).toHaveTextContent('opportunity_type=QUICK_WINS'))
  })

  test('exports the current filtered view', async () => {
    mockPagesRequests()

    renderRoute(<PagesPage />, {
      path: '/jobs/:jobId/pages',
      route:
        '/jobs/3/pages?title_too_short=true&sort_by=title_length&sort_order=desc&schema_present=true&was_rendered=true&page_type=blog_article&page_bucket=informational',
    })

    await screen.findByText('Alpha')
    expect(screen.getByRole('link', { name: 'Export current view CSV' })).toHaveAttribute(
      'href',
      expect.stringContaining('title_too_short=true'),
    )
    expect(screen.getByRole('link', { name: 'Export current view CSV' })).toHaveAttribute(
      'href',
      expect.stringContaining('sort_by=title_length'),
    )
    expect(screen.getByRole('link', { name: 'Export current view CSV' })).toHaveAttribute(
      'href',
      expect.stringContaining('schema_present=true'),
    )
    expect(screen.getByRole('link', { name: 'Export current view CSV' })).toHaveAttribute(
      'href',
      expect.stringContaining('was_rendered=true'),
    )
    expect(screen.getByRole('link', { name: 'Export current view CSV' })).toHaveAttribute(
      'href',
      expect.stringContaining('page_type=blog_article'),
    )
    expect(screen.getByRole('link', { name: 'Export current view CSV' })).toHaveAttribute(
      'href',
      expect.stringContaining('page_bucket=informational'),
    )
  })

  test('copies a page URL to the clipboard', async () => {
    mockPagesRequests()
    copyText.mockResolvedValueOnce(true)

    const { user } = renderRoute(<PagesPage />, {
      path: '/jobs/:jobId/pages',
      route: '/jobs/3/pages',
    })

    await screen.findByText('Alpha')
    await user.click(screen.getByRole('button', { name: 'Copy' }))

    await waitFor(() => expect(copyText).toHaveBeenCalledWith('https://example.com/a'))
    expect(await screen.findByRole('button', { name: 'Copied' })).toBeInTheDocument()
  })

  test('changes sorting from the table header', async () => {
    mockPagesRequests()

    const { user } = renderRoute(<PagesPage />, {
      path: '/jobs/:jobId/pages',
      route: '/jobs/3/pages',
      showLocation: true,
    })

    await screen.findByText('Alpha')
    await user.click(screen.getByRole('button', { name: 'Sort by Meta description' }))

    await waitFor(() => expect(screen.getByTestId('location-search')).toHaveTextContent('sort_by=meta_description'))
    expect(screen.getByTestId('location-search')).toHaveTextContent('sort_order=asc')
  })

  test('renders taxonomy badges and summary cards', async () => {
    mockPagesRequests()

    renderRoute(<PagesPage />, {
      path: '/jobs/:jobId/pages',
      route: '/jobs/3/pages',
    })

    expect(await screen.findByText('Blog article')).toBeInTheDocument()
    expect(screen.getByText('Informational')).toBeInTheDocument()
    expect(await screen.findByText('Category pages')).toBeInTheDocument()
    expect(screen.getByText('Product pages')).toBeInTheDocument()
    expect(screen.getByText('Classifier version 11.1-v1')).toBeInTheDocument()
  })

  test('page taxonomy filters keep state in the query string', async () => {
    mockPagesRequests()

    const { user } = renderRoute(<PagesPage />, {
      path: '/jobs/:jobId/pages',
      route: '/jobs/3/pages',
      showLocation: true,
    })

    await screen.findByText('Alpha')
    await user.selectOptions(screen.getByLabelText('Page type'), 'blog_article')
    await user.selectOptions(screen.getByLabelText('Page bucket'), 'informational')

    await waitFor(() => expect(screen.getByTestId('location-search')).toHaveTextContent('page_type=blog_article'))
    expect(screen.getByTestId('location-search')).toHaveTextContent('page_bucket=informational')
  })

  test('reads taxonomy filters from the query string', async () => {
    mockPagesRequests()

    renderRoute(<PagesPage />, {
      path: '/jobs/:jobId/pages',
      route:
        '/jobs/3/pages?page_type=blog_article&page_bucket=informational&page_type_confidence_min=0.7&page_type_confidence_max=0.95',
    })

    await screen.findByText('Alpha')
    expect(screen.getByLabelText('Page type')).toHaveValue('blog_article')
    expect(screen.getByLabelText('Page bucket')).toHaveValue('informational')
    expect(screen.getByLabelText('Taxonomy confidence min (%)')).toHaveValue(70)
    expect(screen.getByLabelText('Taxonomy confidence max (%)')).toHaveValue(95)
  })

  test('wraps only long title and h1 values', async () => {
    const longTitle = 'Long title words '.repeat(8).trim()
    const longH1 = 'Long heading words '.repeat(8).trim()

    mockPagesRequests({
      pages: {
        ...pagePayload,
        items: [
          {
            ...pagePayload.items[0],
            title: longTitle,
            title_length: longTitle.length,
            h1: longH1,
            h1_length: longH1.length,
          },
        ],
      },
    })

    renderRoute(<PagesPage />, {
      path: '/jobs/:jobId/pages',
      route: '/jobs/3/pages',
    })

    const titleElement = await screen.findByText(longTitle)
    const h1Element = screen.getByText(longH1)
    const metaElement = screen.getByText('Meta A')

    expect(titleElement).toHaveClass('whitespace-normal')
    expect(titleElement).toHaveClass('break-words')
    expect(h1Element).toHaveClass('whitespace-normal')
    expect(h1Element).toHaveClass('break-words')
    expect(metaElement).toHaveClass('whitespace-nowrap')
  })

  test('sorts by the added length columns', async () => {
    mockPagesRequests()

    const { user } = renderRoute(<PagesPage />, {
      path: '/jobs/:jobId/pages',
      route: '/jobs/3/pages',
      showLocation: true,
    })

    await screen.findByText('Alpha')
    await user.click(screen.getByRole('button', { name: 'Sort by H1 length' }))

    await waitFor(() => expect(screen.getByTestId('location-search')).toHaveTextContent('sort_by=h1_length'))
    expect(screen.getByTestId('location-search')).toHaveTextContent('sort_order=asc')
  })

  test('opens the opportunities view for a page and sorts by priority', async () => {
    mockPagesRequests()

    const { user } = renderRoute(<PagesPage />, {
      path: '/jobs/:jobId/pages',
      route: '/jobs/3/pages',
      showLocation: true,
    })

    await screen.findByText('Alpha')
    expect(screen.getByRole('link', { name: 'Open opportunity view' })).toHaveAttribute(
      'href',
      expect.stringContaining('/jobs/3/opportunities?gsc_date_range=last_28_days&opportunity_type=HIGH_IMPRESSIONS_LOW_CTR'),
    )

    await user.click(screen.getByRole('button', { name: 'Sort by Priority' }))

    await waitFor(() => expect(screen.getByTestId('location-search')).toHaveTextContent('sort_by=priority_score'))
  })
})
