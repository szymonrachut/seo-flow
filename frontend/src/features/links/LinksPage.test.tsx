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
      created_at: '2026-03-13T12:00:00Z',
    },
  ],
  page: 1,
  page_size: 25,
  total_items: 40,
  total_pages: 2,
}

describe('LinksPage', () => {
  test('renders the links view', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementationOnce(() => jsonResponse(linksPayload))

    renderRoute(<LinksPage />, {
      path: '/jobs/:jobId/links',
      route: '/jobs/5/links',
    })

    expect(screen.getByText('Link graph for job #5')).toBeInTheDocument()
    expect(await screen.findByText('Read more')).toBeInTheDocument()
    expect(within(screen.getByRole('table')).getByText('Yes')).toBeInTheDocument()
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
})
