import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, test, vi } from 'vitest'

import { jsonResponse, renderRoute } from '../../test/testUtils'
import { LinksPage } from './LinksPage'

afterEach(() => {
  vi.restoreAllMocks()
})

const linksPayload = {
  items: [
    {
      id: 11,
      crawl_job_id: 5,
      source_page_id: 1,
      source_url: 'https://example.com/start',
      target_url: 'https://example.com/target',
      target_normalized_url: 'https://example.com/target',
      target_domain: 'example.com',
      anchor_text: 'Read more',
      rel_attr: '',
      is_nofollow: false,
      is_internal: true,
      target_status_code: 200,
      final_url: 'https://example.com/target',
      redirect_hops: 2,
      target_canonical_url: 'https://example.com/final-target',
      target_noindex_like: false,
      target_non_indexable_like: false,
      target_canonicalized: true,
      broken_internal: false,
      redirecting_internal: true,
      unresolved_internal: false,
      to_noindex_like: false,
      to_canonicalized: true,
      redirect_chain: true,
      created_at: '2026-03-13T12:00:00Z',
    },
  ],
  page: 1,
  page_size: 25,
  total_items: 40,
  total_pages: 2,
}

describe('LinksPage', () => {
  test('renders the links view with URL actions', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementationOnce(() => jsonResponse(linksPayload))

    renderRoute(<LinksPage />, {
      path: '/jobs/:jobId/links',
      route: '/jobs/5/links',
    })

    expect(screen.getByText('Link graph for job #5')).toBeInTheDocument()
    expect(await screen.findByText('Read more')).toBeInTheDocument()
    expect(within(screen.getByRole('table')).getByText('Yes')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Open target' })).toHaveAttribute('href', 'https://example.com/target')
    expect(within(screen.getByRole('table')).getByText('2')).toBeInTheDocument()
  })

  test('changes pagination in the URL', async () => {
    vi.spyOn(globalThis, 'fetch')
      .mockImplementationOnce(() => jsonResponse(linksPayload))
      .mockImplementationOnce(() =>
        jsonResponse({
          ...linksPayload,
          page: 2,
        }),
      )

    const { user } = renderRoute(<LinksPage />, {
      path: '/jobs/:jobId/links',
      route: '/jobs/5/links',
      showLocation: true,
    })

    await screen.findByText('Read more')
    await user.click(screen.getByRole('button', { name: 'Next' }))

    await waitFor(() => expect(screen.getByTestId('location-search')).toHaveTextContent('page=2'))
  })

  test('quick filters set the expected query params', async () => {
    vi.spyOn(globalThis, 'fetch')
      .mockImplementationOnce(() => jsonResponse(linksPayload))
      .mockImplementationOnce(() => jsonResponse(linksPayload))

    const { user } = renderRoute(<LinksPage />, {
      path: '/jobs/:jobId/links',
      route: '/jobs/5/links',
      showLocation: true,
    })

    await screen.findByText('Read more')
    await user.click(screen.getByRole('button', { name: 'To canonicalized' }))

    await waitFor(() => expect(screen.getByTestId('location-search')).toHaveTextContent('to_canonicalized=true'))
  })

  test('exports the current filtered view', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementationOnce(() => jsonResponse(linksPayload))

    renderRoute(<LinksPage />, {
      path: '/jobs/:jobId/links',
      route: '/jobs/5/links?redirect_chain=true&to_canonicalized=true',
    })

    await screen.findByText('Read more')
    expect(screen.getByRole('link', { name: 'Export current view CSV' })).toHaveAttribute(
      'href',
      expect.stringContaining('redirect_chain=true'),
    )
  })

  test('changes sorting from the table header', async () => {
    vi.spyOn(globalThis, 'fetch')
      .mockImplementationOnce(() => jsonResponse(linksPayload))
      .mockImplementationOnce(() => jsonResponse(linksPayload))

    const { user } = renderRoute(<LinksPage />, {
      path: '/jobs/:jobId/links',
      route: '/jobs/5/links',
      showLocation: true,
    })

    await screen.findByText('Read more')
    await user.click(screen.getByRole('button', { name: 'Sort by Anchor text' }))

    await waitFor(() => expect(screen.getByTestId('location-search')).toHaveTextContent('sort_by=anchor_text'))
    expect(screen.getByTestId('location-search')).toHaveTextContent('sort_order=asc')
  })
})
