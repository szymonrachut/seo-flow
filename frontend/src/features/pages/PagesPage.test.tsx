import { screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, test, vi } from 'vitest'

import { deferred, jsonResponse, renderRoute } from '../../test/testUtils'
import { PagesPage } from './PagesPage'

afterEach(() => {
  vi.restoreAllMocks()
})

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
      meta_description: 'Meta A',
      h1: 'Heading A',
      canonical_url: 'https://example.com/a',
      robots_meta: 'index,follow',
      content_type: 'text/html',
      response_time_ms: 44,
      is_internal: true,
      depth: 1,
      fetched_at: '2026-03-13T12:00:00Z',
      error_message: null,
      created_at: '2026-03-13T12:00:00Z',
    },
  ],
  page: 1,
  page_size: 25,
  total_items: 1,
  total_pages: 1,
}

describe('PagesPage', () => {
  test('renders the pages view', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementationOnce(() => jsonResponse(pagePayload))

    renderRoute(<PagesPage />, {
      path: '/jobs/:jobId/pages',
      route: '/jobs/3/pages',
    })

    expect(screen.getByText('Crawled pages for job #3')).toBeInTheDocument()
    expect(await screen.findByText('Alpha')).toBeInTheDocument()
    expect(screen.getByText('44 ms')).toBeInTheDocument()
  })

  test('shows the loading state while the request is pending', async () => {
    const pendingRequest = deferred<Response>()
    vi.spyOn(globalThis, 'fetch').mockReturnValueOnce(pendingRequest.promise)

    renderRoute(<PagesPage />, {
      path: '/jobs/:jobId/pages',
      route: '/jobs/3/pages',
    })

    expect(screen.getByText('Loading pages...')).toBeInTheDocument()
    pendingRequest.resolve(new Response(JSON.stringify(pagePayload), { headers: { 'Content-Type': 'application/json' } }))
    await screen.findByText('Alpha')
  })

  test('shows the empty state when no pages match filters', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementationOnce(() =>
      jsonResponse({
        items: [],
        page: 1,
        page_size: 25,
        total_items: 0,
        total_pages: 0,
      }),
    )

    renderRoute(<PagesPage />, {
      path: '/jobs/:jobId/pages',
      route: '/jobs/3/pages',
    })

    expect(await screen.findByText('No pages matched the current filters')).toBeInTheDocument()
  })

  test('keeps filters in the URL', async () => {
    vi.spyOn(globalThis, 'fetch')
      .mockImplementationOnce(() => jsonResponse(pagePayload))
      .mockImplementationOnce(() => jsonResponse(pagePayload))

    const { user } = renderRoute(<PagesPage />, {
      path: '/jobs/:jobId/pages',
      route: '/jobs/3/pages?has_title=false&page=2',
      showLocation: true,
    })

    await screen.findByText('Alpha')
    await user.selectOptions(screen.getByLabelText('Has title'), 'true')

    await waitFor(() =>
      expect(screen.getByTestId('location-search')).toHaveTextContent('has_title=true'),
    )
    expect(screen.getByTestId('location-search')).toHaveTextContent('page=1')
  })

  test('changes pagination in the URL', async () => {
    vi.spyOn(globalThis, 'fetch')
      .mockImplementationOnce(() =>
        jsonResponse({
          ...pagePayload,
          total_items: 50,
          total_pages: 2,
        }),
      )
      .mockImplementationOnce(() =>
        jsonResponse({
          ...pagePayload,
          page: 2,
          total_items: 50,
          total_pages: 2,
        }),
      )

    const { user } = renderRoute(<PagesPage />, {
      path: '/jobs/:jobId/pages',
      route: '/jobs/3/pages',
      showLocation: true,
    })

    await screen.findByText('Alpha')
    await user.click(screen.getByRole('button', { name: 'Next' }))

    await waitFor(() => expect(screen.getByTestId('location-search')).toHaveTextContent('page=2'))
  })
})
